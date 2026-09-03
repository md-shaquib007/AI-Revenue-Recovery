import pytest
from httpx import ASGITransport, AsyncClient
from apps.api.main import app


@pytest.mark.asyncio
async def test_futuristic_voice_ai_agent_simulation():
    """Validates bilingual Conversational Voice AI Debt Concierge simulation."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Login
        login_res = await client.post("/api/v1/auth/login", json={"username": "ops", "password": "revive-ops-2026"})
        token = login_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Simulate Hinglish Voice Call
        req_payload = {
            "customer_name": "Vikram Malhotra",
            "customer_phone": "+919876543210",
            "amount_in_rupees": 10000.0,
            "language": "hinglish",
            "tier": "VIP",
        }
        res = await client.post("/api/v1/intel/voice-call/simulate", json=req_payload, headers=headers)
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "COMPLETED_AGREED"
        assert data["agreed_action"] == "PARTIAL_WATERFALL_SPLIT"
        assert data["agreed_partial_rupees"] == 3300.0
        assert data["remaining_balance_rupees"] == 6700.0
        assert len(data["full_dialogue"]) >= 5
        assert "rzp.io" in data["whatsapp_link_dispatched"]


@pytest.mark.asyncio
async def test_futuristic_churn_rescue_evaluation():
    """Validates Autonomous Churn Rescue: 14-day holiday pause & micro-tier plan downsell."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        login_res = await client.post("/api/v1/auth/login", json={"username": "ops", "password": "revive-ops-2026"})
        token = login_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        req_payload = {
            "customer_name": "Ananya Roy",
            "tier": "VIP",
            "amount_in_rupees": 4999.0,
            "consecutive_failures": 2,
        }
        res = await client.post("/api/v1/intel/churn-rescue/evaluate", json=req_payload, headers=headers)
        assert res.status_code == 200
        data = res.json()
        assert data["rescue_recommended"] is True
        assert "smart_holiday_pause" in data["strategies"]
        assert "micro_tier_downsell" in data["strategies"]
        assert data["strategies"]["micro_tier_downsell"]["discount_pct"] >= 50
        assert data["preserved_ltv_rupees"] > 0


@pytest.mark.asyncio
async def test_scientific_lift_metrics_endpoint():
    """Validates Scientific A/B Lift metrics and 10% holdout control reporting."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        login_res = await client.post("/api/v1/auth/login", json={"username": "ops", "password": "revive-ops-2026"})
        token = login_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        res = await client.get("/api/v1/intel/lift-metrics", headers=headers)
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "STATISTICALLY_SIGNIFICANT"
        assert "10% Control" in data["holdout_ratio"]
        assert "incremental_recovered_arr_rupees" in data["summary"]
        assert data["summary"]["incremental_recovered_arr_rupees"] > 0
        assert "cfo_roi_narrative" in data
