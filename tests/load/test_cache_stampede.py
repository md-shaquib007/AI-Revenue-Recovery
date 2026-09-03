import asyncio
import pytest
from httpx import ASGITransport, AsyncClient
from apps.api.main import app


@pytest.mark.asyncio
async def test_intel_pulse_cache_stampede_protection():
    """
    Simulates 50 concurrent hits to GET /api/v1/intel/pulse on a cold system.
    Verifies that singleflight coalescing processes all 50 requests cleanly without errors
    or database pool exhaustion.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        tasks = [client.get("/api/v1/intel/pulse") for _ in range(50)]
        results = await asyncio.gather(*tasks)

        assert all(r.status_code == 200 for r in results)
        first_json = results[0].json()
        assert "funnel" in first_json
        assert "circadian_multiplier" in first_json
        assert all(r.json() == first_json for r in results)
