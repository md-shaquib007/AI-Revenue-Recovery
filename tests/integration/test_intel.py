import pytest
from httpx import ASGITransport, AsyncClient

from apps.api.main import app


@pytest.mark.asyncio
async def test_pulse_and_copilot_and_twin():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        payload = {
            "event": "payment.failed",
            "event_id": "evt_intel_001",
            "payload": {
                "payment": {
                    "entity": {
                        "id": "pay_intel_001",
                        "amount": 88000,
                        "currency": "INR",
                        "method": "card",
                        "error_code": "INSUFFICIENT_FUNDS",
                        "email": "ananya@example.com",
                        "notes": {"customer_name": "Ananya Sharma"},
                    }
                }
            },
        }
        created = await client.post(
            "/api/v1/webhooks/razorpay",
            json=payload,
            headers={"x-razorpay-event-id": "evt_intel_001", "x-razorpay-signature": "test_sig_dev"},
        )
        assert created.status_code == 200
        case_id = created.json()["details"]["case_id"]

        pulse = await client.get("/api/v1/intel/pulse")
        assert pulse.status_code == 200
        body = pulse.json()
        assert "funnel" in body
        assert "circadian_curve" in body
        assert len(body["circadian_curve"]) == 24
        assert "ist_now" in body

        twin = await client.get(f"/api/v1/intel/cases/{case_id}/twin")
        assert twin.status_code == 200
        assert twin.json()["winner"]["action"]
        assert "strategies" in twin.json()

        copilot = await client.post("/api/v1/intel/copilot", json={"query": "summary"})
        assert copilot.status_code == 200
        assert copilot.json()["intent"] == "summary"

        search = await client.get("/api/v1/recovery/cases?q=Ananya")
        assert search.status_code == 200
        assert search.json()["count"] >= 1


@pytest.mark.asyncio
async def test_refund_cancels_active_recovery():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        failed = {
            "event": "payment.failed",
            "event_id": "evt_refund_src",
            "payload": {
                "payment": {
                    "entity": {
                        "id": "pay_refund_001",
                        "amount": 120000,
                        "currency": "INR",
                        "method": "upi",
                        "error_code": "INSUFFICIENT_FUNDS",
                    }
                }
            },
        }
        created = await client.post(
            "/api/v1/webhooks/razorpay",
            json=failed,
            headers={"x-razorpay-event-id": "evt_refund_src", "x-razorpay-signature": "test_sig_dev"},
        )
        assert created.status_code == 200

        refund = {
            "event": "refund.processed",
            "event_id": "evt_refund_001",
            "payload": {
                "payment": {
                    "entity": {
                        "id": "pay_refund_001",
                        "amount": 120000,
                        "currency": "INR",
                    }
                }
            },
        }
        resp = await client.post(
            "/api/v1/webhooks/razorpay",
            json=refund,
            headers={"x-razorpay-event-id": "evt_refund_001", "x-razorpay-signature": "test_sig_dev"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "CANCELLED"
