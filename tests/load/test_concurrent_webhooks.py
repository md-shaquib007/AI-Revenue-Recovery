import asyncio

import pytest
from httpx import ASGITransport, AsyncClient

from apps.api.main import app


@pytest.mark.asyncio
async def test_concurrent_duplicate_webhooks_do_not_double_process():
    payload = {
        "event": "payment.failed",
        "event_id": "evt_concurrent_dup",
        "payload": {
            "payment": {
                "entity": {
                    "id": "pay_concurrent_dup",
                    "amount": 50000,
                    "currency": "INR",
                    "method": "upi",
                    "error_code": "INSUFFICIENT_FUNDS",
                }
            }
        },
    }
    headers = {"x-razorpay-event-id": "evt_concurrent_dup", "x-razorpay-signature": "test_sig_dev"}
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        async def post_once():
            return await client.post("/api/v1/webhooks/razorpay", json=payload, headers=headers)

        results = await asyncio.gather(post_once(), post_once(), post_once())
        statuses = [r.json().get("status") for r in results if r.status_code == 200]
        assert "PROCESSED" in statuses
        assert statuses.count("PROCESSED") == 1
        assert statuses.count("DUPLICATE_IGNORED") >= 1
