import pytest
from httpx import ASGITransport, AsyncClient
from apps.api.main import app
from services.multi_psp import multi_psp_router


@pytest.mark.asyncio
async def test_state_graph_transitions():
    """Validates dynamic customer journey state transitions and next-best-action computation."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        login_res = await client.post("/api/v1/auth/login", json={"username": "ops", "password": "revive-ops-2026"})
        token = login_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Step 1: Initial failure to salary disclosure
        req = {
            "current_state": "NUDGE_DELIVERED",
            "event_trigger": "SALARY_DATE_DISCLOSED",
            "metadata": {"salary_day": 5, "customer_name": "Rohan Verma"},
        }
        res = await client.post("/api/v1/intel/state-graph/transition", json=req, headers=headers)
        assert res.status_code == 200
        data = res.json()
        assert data["current_state"] == "LIQUIDITY_DISCLOSED"
        assert data["next_best_action"]["action"] == "SCHEDULE_SALARY_CYCLE_SWEEP"
        assert data["next_best_action"]["suppress_interim_nudges"] is True


@pytest.mark.asyncio
async def test_multi_dimensional_recovery_scorer():
    """Validates P(Pay), P(Churn), and Expected Net Value (EV in ₹) optimization."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        login_res = await client.post("/api/v1/auth/login", json={"username": "ops", "password": "revive-ops-2026"})
        token = login_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        req = {
            "amount_in_rupees": 10000.0,
            "bank_health_score": 0.95,
            "customer_tenure_months": 14,
            "historic_defaults": 1,
            "salary_day_near": True,
        }
        res = await client.post("/api/v1/intel/recovery-score", json=req, headers=headers)
        assert res.status_code == 200
        data = res.json()
        assert 0 <= data["overall_recovery_score"] <= 100
        assert "p_pay_now" in data["probabilities"]
        assert "p_pay_on_salary_cycle" in data["probabilities"]
        assert "p_accept_partial_split" in data["probabilities"]
        assert "p_churn_risk" in data["probabilities"]
        assert "PARTIAL_WATERFALL_SLICING" in data["expected_value_matrix_rupees"]


@pytest.mark.asyncio
async def test_multi_psp_normalization_razorpay_and_stripe():
    """Validates universal multi-PSP normalization for both Razorpay and Stripe."""
    # 1. Razorpay normalization
    rzp_raw = {
        "event": "payment.failed",
        "event_id": "evt_rzp_test_001",
        "payload": {
            "payment": {
                "entity": {
                    "id": "pay_rzp_987",
                    "amount": 500000,
                    "currency": "INR",
                    "contact": "+919876543210",
                    "email": "user@rzp.in",
                    "bank": "HDFC",
                }
            }
        }
    }
    rzp_norm = multi_psp_router.normalize_webhook("RAZORPAY", rzp_raw)
    assert rzp_norm.psp == "RAZORPAY"
    assert rzp_norm.payment_id == "pay_rzp_987"
    assert rzp_norm.amount_in_paise == 500000

    # 2. Stripe normalization
    stripe_raw = {
        "id": "evt_stripe_test_002",
        "type": "invoice.payment_failed",
        "data": {
            "object": {
                "id": "in_stripe_555",
                "customer": "cus_stripe_111",
                "customer_email": "user@stripe.com",
                "amount_due": 499900,
                "currency": "inr",
            }
        }
    }
    stripe_norm = multi_psp_router.normalize_webhook("STRIPE", stripe_raw)
    assert stripe_norm.psp == "STRIPE"
    assert stripe_norm.payment_id == "in_stripe_555"
    assert stripe_norm.amount_in_paise == 499900


@pytest.mark.asyncio
async def test_enterprise_cfo_command_center():
    """Validates real-time Enterprise CFO Command Center pipeline metrics."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        login_res = await client.post("/api/v1/auth/login", json={"username": "ops", "password": "revive-ops-2026"})
        token = login_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        res = await client.get("/api/v1/intel/command-center", headers=headers)
        assert res.status_code == 200
        data = res.json()
        assert "pipeline" in data
        assert "total_at_risk_rupees" in data["pipeline"]
        assert "bank_health_radar" in data
        assert "HDFC" in data["bank_health_radar"]
        assert "autonomous_decision_breakdown" in data
        assert "PARTIAL_WATERFALL_ACTIVE" in data["autonomous_decision_breakdown"]
