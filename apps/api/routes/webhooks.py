import json
from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.logging import log_event
from apps.api.settings import get_settings
from domain.models.schemas import WebhookPayload
from services.correlation_engine import correlation_engine
from services.db import get_db
from services.razorpay_client import razorpay_service

router = APIRouter(prefix="/webhooks", tags=["Webhooks"])


@router.post("/razorpay", status_code=status.HTTP_200_OK)
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
    bypass = settings.allow_hmac_bypass and signature == "test_sig_dev"
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
        import time
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
