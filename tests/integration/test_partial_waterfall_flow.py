import pytest
from datetime import datetime
from httpx import ASGITransport, AsyncClient
from services.mock_razorpay import mock_razorpay
from apps.api.main import app


@pytest.mark.asyncio
async def test_partial_waterfall_10k_recovery_lifecycle():
    """
    Validates the end-to-end Partial Waterfall Recovery flow:
    1. A customer's ₹10,000 EMI/subscription payment fails with INSUFFICIENT_FUNDS.
    2. REVIVE generates a flexible Razorpay link (accept_partial=True, min=33%).
    3. Customer makes a partial payment of ₹3,500.
    4. REVIVE transitions case to PARTIALLY_RECOVERED and computes salary day sweep.
    5. Customer clears the remaining ₹6,500 balance.
    6. REVIVE transitions case to RECOVERED with full ARR secured.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Ingest ₹10,000 NSF failure
        fail_payload = {
            "event": "payment.failed",
            "event_id": "evt_partial_10k_001",
            "payload": {
                "payment": {
                    "entity": {
                        "id": "pay_partial_10k_001",
                        "order_id": "order_partial_10k_001",
                        "amount": 1000000,  # ₹10,000
                        "currency": "INR",
                        "status": "failed",
                        "error_code": "INSUFFICIENT_FUNDS",
                        "error_description": "Account balance insufficient",
                        "method": "upi",
                        "bank": "HDFC",
                        "created_at": 1725350000,
                    }
                }
            },
        }
        body_str = str(fail_payload).replace("'", '"')
        sig = mock_razorpay.generate_webhook_signature(body_str)
        headers = {"x-razorpay-signature": sig, "Content-Type": "application/json"}

        r_fail = await client.post("/api/v1/webhooks/razorpay", content=body_str, headers=headers)
        assert r_fail.status_code == 200
        case_id = r_fail.json()["details"]["case_id"]
        assert case_id is not None

        # 2. Customer pays partial slice of ₹3,500 via Payment Link
        partial_payload = {
            "event": "payment_link.paid",
            "event_id": "evt_partial_plink_001",
            "payload": {
                "payment_link": {
                    "entity": {
                        "id": "plink_partial_001",
                        "amount": 1000000,
                        "amount_paid": 350000,  # ₹3,500 paid
                        "status": "partially_paid",
                        "notes": {"case_id": case_id},
                    }
                }
            },
        }
        body_part_str = str(partial_payload).replace("'", '"')
        sig_part = mock_razorpay.generate_webhook_signature(body_part_str)
        headers_part = {"x-razorpay-signature": sig_part, "Content-Type": "application/json"}

        r_part = await client.post("/api/v1/webhooks/razorpay", content=body_part_str, headers=headers_part)
        assert r_part.status_code == 200
        part_details = r_part.json()["details"]
        assert part_details["status"] == "PARTIALLY_RECOVERED"
        assert part_details["total_recovered"] == 350000
        assert part_details["balance_due"] == 650000
        assert "next_salary_sweep" in part_details

        # 3. Customer pays remaining balance of ₹6,500 on salary day
        settle_payload = {
            "event": "payment_link.paid",
            "event_id": "evt_partial_plink_002",
            "payload": {
                "payment_link": {
                    "entity": {
                        "id": "plink_partial_001",
                        "amount": 1000000,
                        "amount_paid": 650000,  # Remaining ₹6,500 paid
                        "status": "paid",
                        "notes": {"case_id": case_id},
                    }
                }
            },
        }
        body_set_str = str(settle_payload).replace("'", '"')
        sig_set = mock_razorpay.generate_webhook_signature(body_set_str)
        headers_set = {"x-razorpay-signature": sig_set, "Content-Type": "application/json"}

        r_set = await client.post("/api/v1/webhooks/razorpay", content=body_set_str, headers=headers_set)
        assert r_set.status_code == 200
        set_details = r_set.json()["details"]
        assert set_details["status"] == "RECOVERED"
        assert set_details["total_recovered"] == 1000000
        assert set_details["balance_due"] == 0
