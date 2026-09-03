import pytest
from httpx import ASGITransport, AsyncClient
from apps.api.main import app
from services.simulator import portfolio_simulator


@pytest.mark.asyncio
async def test_portfolio_simulator_service_math():
    """Validates mathematical correctness of counterfactual portfolio simulation."""
    res = portfolio_simulator.simulate_portfolio(
        monthly_failed_volume_rupees=10_000_000.0,  # ₹1 Crore
        average_ticket_size_rupees=5_000.0,
        gateway="RAZORPAY",
        industry="SAAS",
    )
    summary = res["cfo_executive_summary"]
    assert summary["baseline_recovery_rate_pct"] == "31.2%"
    assert summary["revive_simulated_recovery_rate_pct"] == "71.6%"
    assert summary["net_incremental_monthly_arr_rupees"] > 4_000_000.0
    assert summary["net_incremental_annual_arr_rupees"] > 48_000_000.0
    assert len(res["strategy_breakdown"]) == 4


@pytest.mark.asyncio
async def test_simulate_portfolio_api_endpoint():
    """Validates the POST /api/v1/intel/simulate-portfolio endpoint with auth."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        login_res = await client.post("/api/v1/auth/login", json={"username": "ops", "password": "revive-ops-2026"})
        token = login_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        payload = {
            "monthly_failed_volume_rupees": 5000000.0,
            "average_ticket_size_rupees": 2500.0,
            "gateway": "STRIPE",
            "industry": "EDTECH",
        }
        res = await client.post("/api/v1/intel/simulate-portfolio", json=payload, headers=headers)
        assert res.status_code == 200
        data = res.json()
        assert "cfo_executive_summary" in data
        assert "strategy_breakdown" in data
        assert "estimated_roi_multiple" in data["cfo_executive_summary"]


@pytest.mark.asyncio
async def test_simulator_html_page_rendering():
    """Validates that GET /simulator serves the interactive HTML simulation studio."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/simulator")
        assert res.status_code == 200
        assert "text/html" in res.headers["content-type"]
        assert "Revenue Recovery Portfolio Simulator" in res.text
        assert "volSlider" in res.text
