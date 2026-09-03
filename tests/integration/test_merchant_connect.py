import pytest
from httpx import ASGITransport, AsyncClient
from apps.api.main import app


@pytest.mark.asyncio
async def test_connect_merchant_api_endpoint():
    """Validates 1-Click Merchant Connect and Tenant Provisioning."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        payload = {
            "business_name": "Zenith EdTech India",
            "gateway": "RAZORPAY",
            "api_key": "rzp_live_abc123",
            "api_secret": "sec_secret_xyz789",
            "mode": "SHADOW",
        }
        res = await client.post("/api/v1/auth/connect-merchant", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "MERCHANT_CONNECTED"
        assert "tenant_zenith_edtech" in data["tenant_id"]
        assert "whsec_" in data["webhook_secret"]
        assert data["operating_mode"] == "SHADOW"
        assert data["shadow_mode_active"] is True
        assert "/api/v1/webhooks/ingest" in data["webhook_url"]


@pytest.mark.asyncio
async def test_connect_portal_html_page_rendering():
    """Validates that GET /connect serves the interactive Merchant Onboarding Studio."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/connect")
        assert res.status_code == 200
        assert "text/html" in res.headers["content-type"]
        assert "Connect Your Payment Gateway" in res.text
        assert "bizName" in res.text
        assert "operatingMode" in res.text
