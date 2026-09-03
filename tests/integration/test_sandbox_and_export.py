import pytest
from httpx import ASGITransport, AsyncClient
from apps.api.main import app
from domain.models.enums import FailureCode


@pytest.mark.asyncio
async def test_sandbox_simulate_endpoint():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        payload = {
            "amount_in_rupees": 2499.0,
            "failure_code": "BAD_REQUEST_PAYMENT_TIMED_OUT",
            "bank_name": "HDFC",
            "bank_health_score": 0.95,
            "customer_churn_risk": 0.35,
            "customer_tier": "STANDARD",
            "offer_discount_pct": 5.0,
            "proposed_action": "PAYMENT_LINK",
        }
        res = await client.post("/api/v1/intel/sandbox-simulate", json=payload)
        assert res.status_code == 200
        body = res.json()

        # Assert all 5 AI components responded
        assert "shadow_simulation" in body
        assert body["shadow_simulation"]["total_simulated_personas"] == 50
        assert "bank_sentinel" in body
        assert "offer_evaluation" in body
        assert "policy_firewall" in body
        assert "ev_curve" in body
        assert "whatsapp_preview" in body
        assert body["whatsapp_preview"]["metadata"]["upi_deep_link"].startswith("upi://pay?")


@pytest.mark.asyncio
async def test_sandbox_simulate_high_value_policy_veto():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        payload = {
            "amount_in_rupees": 75000.0,  # > ₹50,000 policy threshold
            "failure_code": "BAD_REQUEST_AUTHENTICATION_FAILED",
            "bank_name": "ICICI",
            "bank_health_score": 0.90,
            "customer_churn_risk": 0.20,
            "customer_tier": "VIP",
            "offer_discount_pct": 5.0,
            "proposed_action": "SMART_RETRY",
        }
        res = await client.post("/api/v1/intel/sandbox-simulate", json=payload)
        assert res.status_code == 200
        body = res.json()

        # Policy Firewall must require human approval
        assert body["policy_firewall"]["requires_human_approval"] is True


@pytest.mark.asyncio
async def test_export_audit_certificate_endpoint():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 1. First inject a failed webhook to create a case
        payment_id = "pay_export_test_001"
        wh_payload = {
            "event": "payment.failed",
            "payload": {
                "payment": {
                    "entity": {
                        "id": payment_id,
                        "order_id": f"order_{payment_id}",
                        "amount": 250000,
                        "currency": "INR",
                        "status": "failed",
                        "error_code": "BAD_REQUEST_PAYMENT_TIMED_OUT",
                        "error_description": "Payment timed out",
                        "method": "upi",
                        "bank": "HDFC",
                        "created_at": 1787734000,
                    }
                }
            },
        }
        wh_res = await client.post(
            "/api/v1/webhooks/razorpay",
            json=wh_payload,
            headers={"x-razorpay-event-id": "evt_export_001", "x-razorpay-signature": "test_sig_dev"},
        )
        assert wh_res.status_code == 200
        res_json = wh_res.json()
        case_id = res_json.get("case_id") or res_json.get("details", {}).get("case_id")

        if not case_id:
            cases_res = await client.get("/api/v1/recovery/cases")
            assert cases_res.status_code == 200
            case_id = cases_res.json()["cases"][0]["id"]

        # 2. Export the cryptographic audit certificate
        export_res = await client.get(f"/api/v1/recovery/cases/{case_id}/export")
        assert export_res.status_code == 200
        cert = export_res.json()

        assert "certificate_id" in cert
        assert cert["standard"] == "SOC2-Type-II / ISO-27001 Automated Ledger Compliance"
        assert cert["case_id"] == case_id
        assert cert["payment_id"] == payment_id
        assert "genesis_hash" in cert
        assert "terminal_hash" in cert
        assert "certificate_signature" in cert
        assert cert["audit_chain_verified"] is True
        assert len(cert["steps"]) >= 1


@pytest.mark.asyncio
async def test_dpdp_customer_erasure_endpoint():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Fetch existing customer from cases
        cases_res = await client.get("/api/v1/recovery/cases")
        assert cases_res.status_code == 200
        cases = cases_res.json()["cases"]
        if not cases:
            return

        cust_id = cases[0]["customer"]["id"]
        erase_res = await client.post(f"/api/v1/recovery/customers/{cust_id}/erase-pii")
        assert erase_res.status_code == 200
        data = erase_res.json()

        assert data["status"] == "ERASED"
        assert data["customer_id"] == cust_id
        assert data["opted_out"] is True
        assert "name" in data["pii_scrubbed"]

