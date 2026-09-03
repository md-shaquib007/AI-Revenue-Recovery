from datetime import datetime, timedelta

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from apps.api.main import app
from domain.models.entities import RecoveryCaseEntity
from domain.models.enums import RecoveryState
from services.db import AsyncSessionLocal


@pytest.mark.asyncio
async def test_worker_fires_due_scheduled_retry():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        payload = {
            "event": "payment.failed",
            "event_id": "evt_worker_001",
            "payload": {
                "payment": {
                    "entity": {
                        "id": "pay_worker_001",
                        "amount": 88000,
                        "currency": "INR",
                        "method": "upi",
                        "error_code": "GATEWAY_ERROR",
                    }
                }
            },
        }
        resp = await client.post(
            "/api/v1/webhooks/razorpay",
            json=payload,
            headers={"x-razorpay-event-id": "evt_worker_001", "x-razorpay-signature": "test_sig_dev"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["details"]["state"] in ("SCHEDULED_RETRY", "IN_GRACE_WINDOW", "LINK_SENT")
        case_id = data["details"]["case_id"]

        async with AsyncSessionLocal() as session:
            case = (
                await session.execute(select(RecoveryCaseEntity).where(RecoveryCaseEntity.id == case_id))
            ).scalars().first()
            assert case is not None
            case.next_action_at = datetime.utcnow() - timedelta(seconds=5)
            if case.state == RecoveryState.LINK_SENT.value:
                case.state = RecoveryState.SCHEDULED_RETRY.value
            await session.commit()

        tick = await client.post("/api/v1/recovery/worker/tick")
        assert tick.status_code == 200
        body = tick.json()
        assert case_id in body.get("processed", [])
