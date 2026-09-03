import pytest
from httpx import ASGITransport, AsyncClient
from apps.api.main import app
from services.mock_razorpay import mock_razorpay


@pytest.mark.asyncio
async def test_healthcheck():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"


@pytest.mark.asyncio
async def test_webhook_payment_failed_flow():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        payload = {
            "event": "payment.failed",
            "event_id": "evt_test_integ_001",
            "payload": {
                "payment": {
                    "entity": {
                        "id": "pay_test_integ_001",
                        "amount": 299900,
                        "currency": "INR",
                        "method": "card",
                        "error_code": "INSUFFICIENT_FUNDS",
                        "error_description": "Card balance is low",
                    }
                }
            },
        }
        resp = await client.post(
            "/api/v1/webhooks/razorpay",
            json=payload,
            headers={"x-razorpay-event-id": "evt_test_integ_001", "x-razorpay-signature": "test_sig_dev"},
        )
        assert resp.status_code == 200
        res_data = resp.json()
        assert res_data["status"] == "PROCESSED"
        assert res_data["details"]["state"] == "LINK_SENT"
        assert "payment_link_id" in res_data["details"]["decision"]


@pytest.mark.asyncio
async def test_webhook_duplicate_rejection():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        payload = {
            "event": "payment.failed",
            "event_id": "evt_test_dup_001",
            "payload": {
                "payment": {
                    "entity": {
                        "id": "pay_test_dup_001",
                        "amount": 100000,
                        "currency": "INR",
                        "method": "upi",
                    }
                }
            },
        }
        # First call
        resp1 = await client.post(
            "/api/v1/webhooks/razorpay",
            json=payload,
            headers={"x-razorpay-event-id": "evt_test_dup_001", "x-razorpay-signature": "test_sig_dev"},
        )
        assert resp1.status_code == 200

        # Duplicate call
        resp2 = await client.post(
            "/api/v1/webhooks/razorpay",
            json=payload,
            headers={"x-razorpay-event-id": "evt_test_dup_001", "x-razorpay-signature": "test_sig_dev"},
        )
        assert resp2.status_code == 200
        assert resp2.json()["status"] == "DUPLICATE_IGNORED"
