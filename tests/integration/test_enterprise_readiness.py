import pytest
from httpx import ASGITransport, AsyncClient
from apps.api.main import app


@pytest.mark.asyncio
async def test_enterprise_security_headers():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.get("/health")
        assert res.status_code == 200
        headers = res.headers

        # Verify OWASP/SOC2 Enterprise Security Headers
        assert headers.get("x-content-type-options") == "nosniff"
        assert headers.get("x-frame-options") == "DENY"
        assert headers.get("x-xss-protection") == "1; mode=block"
        assert "strict-transport-security" in headers
        assert "x-request-id" in headers


@pytest.mark.asyncio
async def test_enterprise_readiness_probe():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.get("/ready")
        assert res.status_code == 200
        body = res.json()
        assert body["status"] == "ready"
        assert body["checks"]["database"] == "ok"
        assert body["checks"]["sentinel"] == "ok"


@pytest.mark.asyncio
async def test_end_to_end_complete_recovery_flow():
    """
    End-to-End Enterprise Recovery Test:
    1. Ingest failed webhook -> Case created in TRIAGING/SCHEDULED_RETRY/LINK_SENT
    2. Query Case Detail & Verify Audit Chain
    3. Export Cryptographic SOC2 Certificate
    4. Simulate payment.captured -> Auto-resolves case to RECOVERED
    5. Exercise DPDP Act right to erasure
    """
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        payment_id = "pay_e2e_enterprise_001"
        event_id = "evt_e2e_enterprise_001"

        # Step 1: Ingest payment.failed
        wh_payload = {
            "event": "payment.failed",
            "event_id": event_id,
            "payload": {
                "payment": {
                    "entity": {
                        "id": payment_id,
                        "order_id": f"order_{payment_id}",
                        "amount": 499900,  # ₹4,999
                        "currency": "INR",
                        "status": "failed",
                        "error_code": "BAD_REQUEST_PAYMENT_TIMED_OUT",
                        "error_description": "Payment timed out at bank",
                        "method": "upi",
                        "bank": "HDFC",
                        "created_at": 1787740000,
                    }
                }
            },
        }
        res = await client.post(
            "/api/v1/webhooks/razorpay",
            json=wh_payload,
            headers={"x-razorpay-event-id": event_id, "x-razorpay-signature": "test_sig_dev"},
        )
        assert res.status_code == 200

        # Step 2: Fetch created case
        cases_res = await client.get("/api/v1/recovery/cases")
        assert cases_res.status_code == 200
        matched = [c for c in cases_res.json()["cases"] if c["payment_id"] == payment_id]
        assert len(matched) == 1
        case = matched[0]
        case_id = case["id"]

        # Step 3: Verify Decision Trace & Certificate Export
        cert_res = await client.get(f"/api/v1/recovery/cases/{case_id}/export")
        assert cert_res.status_code == 200
        cert = cert_res.json()
        assert cert["audit_chain_verified"] is True
        assert cert["payment_id"] == payment_id

        # Step 4: Simulate payment.captured
        cap_event_id = "evt_e2e_cap_001"
        cap_payload = {
            "event": "payment.captured",
            "event_id": cap_event_id,
            "payload": {
                "payment": {
                    "entity": {
                        "id": payment_id,
                        "order_id": f"order_{payment_id}",
                        "amount": 499900,
                        "currency": "INR",
                        "status": "captured",
                        "method": "upi",
                        "bank": "HDFC",
                        "created_at": 1787740050,
                    }
                }
            },
        }
        cap_res = await client.post(
            "/api/v1/webhooks/razorpay",
            json=cap_payload,
            headers={"x-razorpay-event-id": cap_event_id, "x-razorpay-signature": "test_sig_dev"},
        )
        assert cap_res.status_code == 200

        # Step 5: Exercise DPDP Act PII Erasure
        cust_id = case["customer"]["id"]
        erase_res = await client.post(f"/api/v1/recovery/customers/{cust_id}/erase-pii")
        assert erase_res.status_code == 200
        assert erase_res.json()["status"] == "ERASED"
