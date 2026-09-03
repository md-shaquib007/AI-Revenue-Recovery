import json

import pytest
from httpx import ASGITransport, AsyncClient

from apps.api.main import app
from services.mock_razorpay import mock_razorpay


@pytest.mark.asyncio
async def test_invalid_hmac_rejected_even_in_test_when_not_dev_bypass():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        payload = {"event": "payment.failed", "event_id": "evt_bad_sig", "payload": {"payment": {"entity": {"id": "pay_x"}}}}
        resp = await client.post(
            "/api/v1/webhooks/razorpay",
            json=payload,
            headers={"x-razorpay-event-id": "evt_bad_sig", "x-razorpay-signature": "definitely-invalid"},
        )
        assert resp.status_code == 401


@pytest.mark.asyncio
async def test_valid_hmac_accepted():
    transport = ASGITransport(app=app)
    payload = {
        "event": "payment.failed",
        "event_id": "evt_hmac_ok",
        "payload": {
            "payment": {
                "entity": {
                    "id": "pay_hmac_ok",
                    "amount": 19900,
                    "currency": "INR",
                    "method": "card",
                    "error_code": "INSUFFICIENT_FUNDS",
                }
            }
        },
    }
    body = json.dumps(payload)
    signature = mock_razorpay.generate_webhook_signature(body)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/v1/webhooks/razorpay",
            content=body,
            headers={
                "content-type": "application/json",
                "x-razorpay-event-id": "evt_hmac_ok",
                "x-razorpay-signature": signature,
            },
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "PROCESSED"
