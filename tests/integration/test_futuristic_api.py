import pytest
from httpx import ASGITransport, AsyncClient
from apps.api.main import app


@pytest.mark.asyncio
async def test_futuristic_intel_sentinel_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/v1/intel/sentinel")
        assert resp.status_code == 200
        data = resp.json()
        assert "sentinel_analytics" in data
        assert len(data["sentinel_analytics"]) >= 4
