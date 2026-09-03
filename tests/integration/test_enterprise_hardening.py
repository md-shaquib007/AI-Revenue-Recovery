import pytest
from httpx import ASGITransport, AsyncClient
from apps.api.logging import sanitize_pii_value
from apps.api.main import app
from services.db import AsyncSessionLocal
from domain.models.entities import WebhookEventEntity
from datetime import datetime


def test_pii_realtime_log_redaction():
    """Validates real-time zero-leak regex scrubbing for enterprise compliance (SOC2/DPDP)."""
    raw_data = {
        "customer_email": "john.doe@enterprise.com",
        "customer_phone": "+91-9876543210",
        "card_number": "4111 2222 3333 4567",
        "pan_number": "ABCDE1234F",
        "aadhaar": "1234 5678 9012",
        "nested": {
            "contact": "9876543210",
            "email": "sarah@company.co.in",
        }
    }
    sanitized = sanitize_pii_value(raw_data)
    
    assert "john.doe" not in sanitized["customer_email"]
    assert "@enterprise.com" in sanitized["customer_email"]
    assert "9876543210" not in sanitized["customer_phone"]
    assert "4111" not in sanitized["card_number"]
    assert "4567" in sanitized["card_number"]
    assert "ABCDE" not in sanitized["pan_number"]
    assert "1234" not in sanitized["aadhaar"]
    assert "9012" in sanitized["aadhaar"]


@pytest.mark.asyncio
async def test_enterprise_batch_webhook_ingestion():
    """Validates high-throughput batch webhook ingestion endpoint."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        batch_payload = [
            {
                "event": "payment.failed",
                "event_id": f"evt_batch_test_{i}",
                "payload": {
                    "payment": {
                        "entity": {
                            "id": f"pay_batch_test_{i}",
                            "amount": 250000,
                            "currency": "INR",
                            "status": "failed",
                            "error_code": "BAD_REQUEST_PAYMENT_TIMED_OUT",
                            "bank": "HDFC",
                            "created_at": 1725350000,
                        }
                    }
                }
            }
            for i in range(5)
        ]
        resp = await client.post("/api/v1/webhooks/batch", json=batch_payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "BATCH_COMPLETE"
        assert data["total_events"] == 5
        assert data["success_count"] >= 1


@pytest.mark.asyncio
async def test_dlq_queue_and_replay_lifecycle():
    """Validates DLQ listing and 1-click Ops replay recovery endpoint."""
    # 1. Manually insert a poisoned/dead-letter event into DB
    async with AsyncSessionLocal() as session:
        dead_event = WebhookEventEntity(
            id="evt_poison_pill_001",
            event_id="evt_poison_pill_001",
            event_type="payment.failed",
            payload={
                "event": "payment.failed",
                "payload": {
                    "payment": {
                        "entity": {
                            "id": "pay_poison_recovered_001",
                            "amount": 499900,
                            "currency": "INR",
                            "status": "failed",
                            "error_code": "BAD_REQUEST_PAYMENT_TIMED_OUT",
                            "bank": "ICICI",
                        }
                    }
                }
            },
            signature="test_sig_dev",
            status="DEAD_LETTER",
            last_error="Transient database deadlock simulated during peak traffic",
            received_at=datetime.utcnow(),
        )
        session.add(dead_event)
        await session.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Login to get operator token
        login_res = await client.post("/api/v1/auth/login", json={"username": "ops", "password": "revive-ops-2026"})
        token = login_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # 2. Query DLQ list
        dlq_res = await client.get("/api/v1/ops/dlq", headers=headers)
        assert dlq_res.status_code == 200
        dlq_items = dlq_res.json()
        assert any(item["event_id"] == "evt_poison_pill_001" for item in dlq_items)

        # 3. 1-Click Replay dead-letter event
        replay_res = await client.post("/api/v1/ops/dlq/evt_poison_pill_001/replay", headers=headers)
        assert replay_res.status_code == 200
        replay_data = replay_res.json()
        assert replay_data["status"] == "REPLAYED"
        assert replay_data["original_event_id"] == "evt_poison_pill_001"
