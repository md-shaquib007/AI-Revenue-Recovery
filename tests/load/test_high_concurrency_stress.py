import asyncio
import pytest
from httpx import ASGITransport, AsyncClient
from apps.api.main import app


@pytest.mark.asyncio
async def test_high_concurrency_parallel_webhooks():
    """
    Simulates high-concurrency burst of 50 simultaneous webhooks
    across 10 unique payment IDs with duplicate events.
    Verifies that per-payment mutex locking prevents race conditions and duplicates.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        tasks = []
        for i in range(10):
            payment_id = f"pay_concurrent_burst_{i}"
            for dup_idx in range(5):
                event_id = f"evt_burst_{i}_{dup_idx}" if dup_idx == 0 else f"evt_burst_{i}_0"  # simulate duplicates
                payload = {
                    "event": "payment.failed",
                    "event_id": event_id,
                    "payload": {
                        "payment": {
                            "entity": {
                                "id": payment_id,
                                "amount": 150000 + (i * 1000),
                                "currency": "INR",
                                "method": "upi",
                                "error_code": "INSUFFICIENT_FUNDS",
                            }
                        }
                    },
                }
                headers = {"x-razorpay-event-id": event_id, "x-razorpay-signature": "test_sig_dev"}
                tasks.append(client.post("/api/v1/webhooks/razorpay", json=payload, headers=headers))

        results = await asyncio.gather(*tasks)
        assert all(r.status_code == 200 for r in results)

        statuses = [r.json().get("status") for r in results]
        processed_count = statuses.count("PROCESSED")
        duplicate_count = statuses.count("DUPLICATE_IGNORED")

        # Exactly 10 unique events should be PROCESSED (1 per unique event_id)
        assert processed_count == 10
        # Exactly 40 duplicate deliveries should be cleanly DUPLICATE_IGNORED
        assert duplicate_count == 40
