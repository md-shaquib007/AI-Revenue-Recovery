import asyncio
import json
import time
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.logging import log_event
from apps.api.settings import get_settings
from domain.models.schemas import WebhookPayload
from services.correlation_engine import correlation_engine
from services.db import get_db
from services.razorpay_client import razorpay_service

router = APIRouter(prefix="/webhooks", tags=["Webhooks"])


@router.post("/simulate", status_code=status.HTTP_200_OK)
async def simulate_webhook_event(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """1-Click UI Simulator endpoint: signs the payload internally and processes the scenario."""
    settings = get_settings()
    data = await request.json()
    body_str = json.dumps(data)
    import hashlib
    import hmac

    sig = hmac.new(
        settings.razorpay_webhook_secret.encode("utf-8"),
        body_str.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    event_id = data.get("event_id") or f"sim_evt_{int(time.time() * 1000)}"
    event_type = data.get("event", "payment.failed")

    status_code, result = await correlation_engine.process_webhook(
        db=db,
        event_id=event_id,
        event_type=event_type,
        payload_data=data,
        signature=sig,
    )
    return {
        "status": status_code,
        "processed_event_id": event_id,
        "details": result,
    }


@router.post("/razorpay", status_code=status.HTTP_200_OK)
@router.post("/ingest", status_code=status.HTTP_200_OK)
async def handle_razorpay_webhook(
    request: Request,
    x_razorpay_signature: str | None = Header(default=None),
    x_razorpay_event_id: str = Header(default=""),
    db: AsyncSession = Depends(get_db),
):
    settings = get_settings()
    raw_body = await request.body()
    body_str = raw_body.decode("utf-8")
    signature = x_razorpay_signature or ""

    is_valid = bool(signature) and razorpay_service.verify_signature(body_str, signature)
    bypass = (settings.allow_hmac_bypass or settings.allow_chaos) and signature in ("test_sig_dev", "none", "")
    if not is_valid and not bypass:
        log_event("warning", "webhook_hmac_rejected", has_signature=bool(signature))
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Razorpay Webhook HMAC Signature",
        )

    try:
        data = json.loads(body_str)
        parsed = WebhookPayload.model_validate(
            {
                "event": data.get("event", "payment.failed"),
                "event_id": x_razorpay_event_id or data.get("event_id") or "",
                "payload": data.get("payload") or data,
                "account_id": data.get("account_id"),
                "contains": data.get("contains") or [],
                "created_at": data.get("created_at"),
            }
        )
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid JSON payload")

    # Enterprise Replay Attack Defense (Timestamp Gate)
    webhook_timestamp = data.get("created_at")
    if webhook_timestamp and settings.enforce_replay_window:
        now = int(time.time())
        if abs(now - int(webhook_timestamp)) > settings.webhook_replay_tolerance_seconds:
            log_event("warning", "webhook_replay_rejected", age=abs(now - int(webhook_timestamp)))
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Webhook timestamp outside acceptable replay window tolerance",
            )

    event_id = x_razorpay_event_id or parsed.event_id or data.get("event_id") or f"evt_{hash(body_str)}"
    event_type = str(parsed.event)

    try:
        status_code, result = await correlation_engine.process_webhook(
            db=db,
            event_id=event_id,
            event_type=event_type,
            payload_data=data,
            signature=signature or "none",
        )
    except Exception as exc:
        log_event("error", "webhook_processing_failed", event_id=event_id, error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Webhook processing failed; queued for retry",
        ) from exc

    return {
        "status": status_code,
        "processed_event_id": event_id,
        "details": result,
    }


@router.post("/batch", status_code=status.HTTP_200_OK)
async def handle_batch_webhooks(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Enterprise High-Throughput Batch Webhook Ingestion Endpoint.
    Accepts arrays of up to 1,000 failure events for bulk flash-sale / subscription renewals.
    Processes concurrently using bounded worker semaphores to protect DB pool integrity.
    """
    settings = get_settings()
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid JSON array payload")

    events = body if isinstance(body, list) else body.get("events", [])
    if not isinstance(events, list) or len(events) == 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Batch must be a non-empty array")

    if len(events) > 1000:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Batch size exceeds limit of 1,000 events")

    semaphore = asyncio.Semaphore(20)
    results = []

    async def _process_single(evt: Dict[str, Any], idx: int) -> Dict[str, Any]:
        async with semaphore:
            evt_id = evt.get("event_id") or f"batch_{int(time.time()*1000)}_{idx}"
            evt_type = evt.get("event", "payment.failed")
            sig = evt.get("signature") or "test_sig_dev"
            try:
                st, res = await correlation_engine.process_webhook(
                    db=db,
                    event_id=evt_id,
                    event_type=evt_type,
                    payload_data=evt,
                    signature=sig,
                )
                return {"event_id": evt_id, "status": st, "details": res}
            except Exception as e:
                return {"event_id": evt_id, "status": "ERROR", "error": str(e)}

    tasks = [_process_single(evt, idx) for idx, evt in enumerate(events)]
    processed_results = await asyncio.gather(*tasks, return_exceptions=False)

    success_count = sum(1 for r in processed_results if r.get("status") in ("PROCESSED", "DUPLICATE_IGNORED"))
    error_count = len(processed_results) - success_count

    return {
        "status": "BATCH_COMPLETE",
        "total_events": len(processed_results),
        "success_count": success_count,
        "error_count": error_count,
        "results": processed_results[:50],  # Return first 50 results in response summary
    }
