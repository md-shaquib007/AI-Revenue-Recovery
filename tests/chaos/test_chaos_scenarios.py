import pytest
from httpx import ASGITransport, AsyncClient
from ai.agent import ai_recovery_agent
from apps.api.main import app


@pytest.mark.asyncio
async def test_chaos_llm_outage_deterministic_fallback():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Enable LLM outage
        toggle_resp = await client.post("/api/v1/chaos/llm-outage", json={"enabled": True})
        assert toggle_resp.status_code == 200
        assert toggle_resp.json()["mode"] == "DETERMINISTIC_FALLBACK_ACTIVE"

        # Send payment failed event while LLM is down
        payload = {
            "event": "payment.failed",
            "event_id": "evt_chaos_llm_down_001",
            "payload": {
                "payment": {
                    "entity": {
                        "id": "pay_chaos_llm_down_001",
                        "amount": 199900,
                        "currency": "INR",
                        "method": "upi",
                        "error_code": "GATEWAY_ERROR",
                        "error_description": "Timeout",
                    }
                }
            },
        }
        resp = await client.post(
            "/api/v1/webhooks/razorpay",
            json=payload,
            headers={"x-razorpay-event-id": "evt_chaos_llm_down_001", "x-razorpay-signature": "test_sig_dev"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "PROCESSED"

        # Check that case was created safely
        case_id = data["details"]["case_id"]
        detail_resp = await client.get(f"/api/v1/recovery/cases/{case_id}")
        assert detail_resp.status_code == 200
        detail_data = detail_resp.json()
        # Verify fallback trace
        trace = detail_data["decision_traces"][0]
        assert trace["agent_mode"] in ["DETERMINISTIC_FALLBACK", "AI_REASONER"]

        # Restore LLM
        await client.post("/api/v1/chaos/llm-outage", json={"enabled": False})


@pytest.mark.asyncio
async def test_chaos_prompt_injection_defense():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/v1/chaos/inject-prompt-injection")
        assert resp.status_code == 200
        data = resp.json()
        assert data["scenario"] == "PROMPT_INJECTION_DEFENSE"
        assert data["status"] == "PROCESSED"


@pytest.mark.asyncio
async def test_chaos_grace_capture_scenario():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/v1/chaos/inject-grace-capture")
        assert resp.status_code == 200
        data = resp.json()
        assert data["scenario"] == "INTELLIGENT_NON_ACTION_GRACE_CAPTURE"
        assert data["step_2_captured_response"]["status"] == "RECOVERED"
