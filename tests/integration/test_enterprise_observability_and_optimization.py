import pytest
from httpx import ASGITransport, AsyncClient
from ai.oracle import evaluate_fast_path_heuristic
from apps.api.main import app
from domain.models.enums import FailureCode


@pytest.mark.asyncio
async def test_prometheus_metrics_endpoint():
    """Validates Prometheus OpenTelemetry exporter at /metrics."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/metrics")
        assert res.status_code == 200
        assert "text/plain" in res.headers["content-type"]
        text = res.text
        assert "revive_recovered_arr_paise_total" in text
        assert "revive_active_recovery_cases" in text
        assert "revive_bank_health_score" in text
        assert "revive_llm_cost_savings_tokens_total" in text


@pytest.mark.asyncio
async def test_kubernetes_probes_healthz_and_readyz():
    """Validates liveness and readiness probes for zero-downtime deployment."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Liveness
        res_l = await client.get("/healthz")
        assert res_l.status_code == 200
        assert res_l.json()["status"] == "healthy"

        # Readiness
        res_r = await client.get("/readyz")
        assert res_r.status_code == 200
        assert res_r.json()["status"] == "ready"
        assert res_r.json()["checks"]["database"] == "ok"


def test_llm_fast_path_cost_optimization():
    """Validates sub-millisecond heuristic reasoning and token cost avoidance."""
    # 1. Bank Downtime -> WAIT
    res_down = evaluate_fast_path_heuristic(FailureCode.BANK_DOWNTIME, 10000.0)
    assert res_down["fast_path"] is True
    assert res_down["recommended_action"] == "WAIT"
    assert res_down["token_cost_usd"] == 0.0

    # 2. Insufficient Funds -> PAYMENT_LINK (Partial Waterfall)
    res_nsf = evaluate_fast_path_heuristic(FailureCode.INSUFFICIENT_FUNDS, 10000.0)
    assert res_nsf["fast_path"] is True
    assert res_nsf["recommended_action"] == "PAYMENT_LINK"
    assert res_nsf["token_cost_usd"] == 0.0

    # 3. Card Expired -> PAYMENT_LINK (Card Switch)
    res_exp = evaluate_fast_path_heuristic(FailureCode.CARD_EXPIRED, 4999.0)
    assert res_exp["fast_path"] is True
    assert res_exp["recommended_action"] == "PAYMENT_LINK"
    assert res_exp["token_cost_usd"] == 0.0
