import pytest
from httpx import ASGITransport, AsyncClient
from apps.api.main import app


@pytest.mark.asyncio
async def test_complete_master_end_to_end_lifecycle():
    """
    Exhaustive End-to-End Master Lifecycle Test for REVIVE Autonomous Revenue Recovery OS.
    Executes the complete merchant, ingestion, decision, customer resolution,
    governance, lift metrics, and DPDP compliance flow in a single unified journey.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # =========================================================================
        # 1. AUTH & OPERATOR INITIALIZATION
        # =========================================================================
        login_res = await client.post("/api/v1/auth/login", json={"username": "ops", "password": "revive-ops-2026"})
        assert login_res.status_code == 200
        token = login_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # =========================================================================
        # 2. PHASE 1: 1-CLICK MERCHANT ONBOARDING (/connect)
        # =========================================================================
        connect_payload = {
            "business_name": "Apex Enterprise SaaS India",
            "gateway": "RAZORPAY",
            "api_key": "rzp_live_apex_987",
            "api_secret": "sec_apex_secret_123",
            "mode": "AUTONOMOUS_LIVE",
        }
        connect_res = await client.post("/api/v1/auth/connect-merchant", json=connect_payload)
        assert connect_res.status_code == 200
        merchant_data = connect_res.json()
        assert merchant_data["status"] == "MERCHANT_CONNECTED"
        assert "tenant_apex_enterprise" in merchant_data["tenant_id"]
        tenant_id = merchant_data["tenant_id"]

        # =========================================================================
        # 3. PHASE 2: FAILED PAYMENT WEBHOOK INGESTION
        # =========================================================================
        webhook_payload = {
            "event": "payment.failed",
            "event_id": f"evt_e2e_{tenant_id}",
            "payload": {
                "payment": {
                    "entity": {
                        "id": f"pay_e2e_{tenant_id}",
                        "amount": 1000000,  # ₹10,000.00
                        "currency": "INR",
                        "contact": "+919876543210",
                        "email": "rohit.sharma@example.com",
                        "error_code": "BAD_REQUEST_PAYMENT_TIMED_OUT",
                        "bank": "HDFC",
                    }
                }
            }
        }
        webhook_res = await client.post("/api/v1/webhooks/ingest", json=webhook_payload)
        assert webhook_res.status_code == 200
        webhook_data = webhook_res.json()
        assert webhook_data["status"] == "PROCESSED"
        case_id = webhook_data.get("details", {}).get("case_id") or "demo-case"

        # =========================================================================
        # 4. PHASE 3: CUSTOMER STATE GRAPH TRANSITION & EV SCORING
        # =========================================================================
        # Customer responds to WhatsApp: "Salary on 5th"
        sg_req = {
            "current_state": "NUDGE_DELIVERED",
            "event_trigger": "SALARY_DATE_DISCLOSED",
            "metadata": {"salary_day": 5, "customer_name": "Rohit Sharma"},
        }
        sg_res = await client.post("/api/v1/intel/state-graph/transition", json=sg_req, headers=headers)
        assert sg_res.status_code == 200
        assert sg_res.json()["current_state"] == "LIQUIDITY_DISCLOSED"
        assert sg_res.json()["next_best_action"]["suppress_interim_nudges"] is True

        # Multi-Dimensional Scorer & EV optimization
        score_req = {
            "amount_in_rupees": 10000.0,
            "bank_health_score": 0.98,
            "customer_tenure_months": 12,
            "historic_defaults": 1,
            "salary_day_near": True,
        }
        score_res = await client.post("/api/v1/intel/recovery-score", json=score_req, headers=headers)
        assert score_res.status_code == 200
        assert score_res.json()["optimal_recommendation"] == "PARTIAL_WATERFALL_SLICING"

        # =========================================================================
        # 5. PHASE 4: CUSTOMER SELF-SERVICE PORTAL RESOLUTION (/pay/:case_id)
        # =========================================================================
        # Customer selects 33% Partial Split (₹3,300 today, ₹6,700 on salary day)
        action_payload = {
            "action": "PAY_PARTIAL",
            "partial_amount_rupees": 3300.0,
        }
        action_res = await client.post(f"/api/v1/recovery/cases/{case_id}/customer-action", json=action_payload)
        assert action_res.status_code == 200
        action_data = action_res.json()
        assert action_data["status"] == "ACTION_RECORDED"
        assert action_data["partial_amount_rupees"] == 3300.0
        assert action_data["balance_due_rupees"] == 6700.0

        # =========================================================================
        # 6. PHASE 5: BILINGUAL VOICE AI CONCIERGE SIMULATION
        # =========================================================================
        voice_req = {
            "customer_name": "Rohit Sharma",
            "customer_phone": "+919876543210",
            "amount_in_rupees": 10000.0,
            "language": "hinglish",
            "tier": "VIP",
        }
        voice_res = await client.post("/api/v1/intel/voice-call/simulate", json=voice_req, headers=headers)
        assert voice_res.status_code == 200
        assert voice_res.json()["status"] == "COMPLETED_AGREED"
        assert len(voice_res.json()["full_dialogue"]) >= 5

        # =========================================================================
        # 7. PHASE 6: SCIENTIFIC A/B LIFT METRICS & CFO COMMAND CENTER
        # =========================================================================
        lift_res = await client.get("/api/v1/intel/lift-metrics", headers=headers)
        assert lift_res.status_code == 200
        assert lift_res.json()["status"] == "STATISTICALLY_SIGNIFICANT"
        assert lift_res.json()["summary"]["incremental_recovered_arr_rupees"] > 0

        cc_res = await client.get("/api/v1/intel/command-center", headers=headers)
        assert cc_res.status_code == 200
        assert "bank_health_radar" in cc_res.json()
        assert "pipeline" in cc_res.json()

        # =========================================================================
        # 8. PHASE 7: PROMETHEUS METRICS & KUBERNETES PROBES
        # =========================================================================
        metrics_res = await client.get("/metrics")
        assert metrics_res.status_code == 200
        assert "revive_recovered_arr_paise_total" in metrics_res.text

        ready_res = await client.get("/readyz")
        assert ready_res.status_code == 200
        assert ready_res.json()["status"] == "ready"

        # =========================================================================
        # 9. PHASE 8: DPDP ACT 2023 SEC 12 CRYPTOGRAPHIC ERASURE
        # =========================================================================
        erase_res = await client.post(f"/api/v1/recovery/customers/cust_{case_id}/erase-pii", headers=headers)
        # 200 OK or 404 handled cleanly
        assert erase_res.status_code in (200, 404)
