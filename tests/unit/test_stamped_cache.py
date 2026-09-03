import asyncio
import time
import pytest
from services.stamped_cache import AsyncSingleflight, StampedCache, stamped_cached


@pytest.mark.asyncio
async def test_singleflight_request_coalescing():
    """
    Simulates 100 concurrent requests for the exact same key.
    Verifies that the underlying async function executes EXACTLY ONCE.
    """
    singleflight = AsyncSingleflight()
    execution_count = 0

    async def slow_db_query():
        nonlocal execution_count
        await asyncio.sleep(0.05)  # 50ms simulated DB query
        execution_count += 1
        return "db_result_v1"

    # Launch 100 parallel workers
    tasks = [
        singleflight.execute("query_key_1", slow_db_query)
        for _ in range(100)
    ]
    results = await asyncio.gather(*tasks)

    # All 100 callers receive the exact same result
    assert all(r == "db_result_v1" for r in results)
    # The DB query executed strictly 1 time
    assert execution_count == 1


def test_stamped_cache_xfetch_early_recomputation():
    cache = StampedCache()

    # Store entry with 1s TTL and 0.1s delta
    cache.set("key_1", "val_1", delta_seconds=0.1, ttl_seconds=1.0, swr_grace_seconds=5.0)

    # Immediately after setting, entry is fresh (no recomputation)
    val, needs_recompute = cache.get("key_1", beta=0.0)  # beta=0 turns off random factor
    assert val == "val_1"
    assert needs_recompute is False


@pytest.mark.asyncio
async def test_stamped_cached_decorator():
    call_count = 0

    @stamped_cached(ttl=2.0, swr_grace=5.0, key_prefix="test_dec")
    async def get_user_data(user_id: str):
        nonlocal call_count
        await asyncio.sleep(0.02)
        call_count += 1
        return f"user_{user_id}_profile"

    # 20 concurrent callers
    results = await asyncio.gather(*[get_user_data("42") for _ in range(20)])
    assert all(r == "user_42_profile" for r in results)
    assert call_count == 1
