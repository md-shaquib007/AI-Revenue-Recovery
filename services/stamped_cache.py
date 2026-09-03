import asyncio
import functools
import math
import random
import time
from typing import Any, Callable, Dict, Optional, Tuple, TypeVar
from apps.api.settings import get_settings

T = TypeVar("T")


class AsyncSingleflight:
    """
    Singleflight Request Coalescing Engine.
    Ensures that for any key, only ONE execution of an async function is in-flight.
    Duplicate concurrent requests for the same key await the single in-flight execution
    and receive the exact same result, preventing thundering herd spikes on the DB.
    """

    def __init__(self) -> None:
        self._in_flight: Dict[str, asyncio.Future] = {}
        self._lock = asyncio.Lock()

    async def execute(self, key: str, fn: Callable[[], Any]) -> Any:
        async with self._lock:
            if key in self._in_flight:
                future = self._in_flight[key]
                # Lock released while awaiting shared in-flight execution
            else:
                loop = asyncio.get_running_loop()
                future = loop.create_future()
                self._in_flight[key] = future
                # Start execution as the leader
                asyncio.create_task(self._worker(key, fn, future))

        return await future

    async def _worker(self, key: str, fn: Callable[[], Any], future: asyncio.Future) -> None:
        try:
            res = await fn()
            if not future.done():
                future.set_result(res)
        except Exception as exc:
            if not future.done():
                future.set_exception(exc)
        finally:
            async with self._lock:
                self._in_flight.pop(key, None)


class StampedCacheEntry:
    def __init__(self, value: Any, delta_seconds: float, ttl_seconds: float, swr_grace_seconds: float = 30.0) -> None:
        self.value = value
        self.delta = max(0.001, delta_seconds)
        self.ttl = ttl_seconds
        self.swr_grace = swr_grace_seconds
        self.computed_at = time.time()

    @property
    def hard_expires_at(self) -> float:
        return self.computed_at + self.ttl + self.swr_grace

    def should_recompute_early(self, beta: float = 1.0) -> bool:
        """
        XFetch Probabilistic Early Expiration Algorithm (Vattani et al., MIT):
        now - (delta * beta * ln(rand())) > (computed_at + ttl)
        As time approaches (computed_at + ttl), probability of background recomputation → 100%.
        """
        now = time.time()
        rand_val = random.random() or 0.0001
        threshold = self.computed_at + self.ttl + (self.delta * beta * math.log(rand_val))
        return now > threshold


class StampedCache:
    """
    Stampede-Proof Cache Engine combining Singleflight Coalescing,
    XFetch Probabilistic Early Expiration, and Stale-While-Revalidate (SWR).
    """

    def __init__(self) -> None:
        self._cache: Dict[str, StampedCacheEntry] = {}
        self.singleflight = AsyncSingleflight()

    def get(self, key: str, beta: float = 1.0) -> Tuple[Optional[Any], bool]:
        """
        Returns (cached_value, needs_recompute).
        - If key missing or past hard expiry (ttl + swr_grace): returns (None, True)
        - If key valid but should recompute early via XFetch: returns (value, True)
        - If key fresh: returns (value, False)
        """
        now = time.time()
        if key not in self._cache:
            return None, True

        entry = self._cache[key]
        if now >= entry.hard_expires_at:
            del self._cache[key]
            return None, True

        needs_recompute = entry.should_recompute_early(beta)
        return entry.value, needs_recompute

    def set(self, key: str, value: Any, delta_seconds: float, ttl_seconds: float, swr_grace_seconds: float = 30.0) -> None:
        self._cache[key] = StampedCacheEntry(value, delta_seconds, ttl_seconds, swr_grace_seconds)

    def clear(self) -> None:
        self._cache.clear()


# Global singleton instance
stamped_cache = StampedCache()


def stamped_cached(
    ttl: Optional[float] = None,
    swr_grace: Optional[float] = None,
    key_prefix: str = "cache",
):
    """
    Decorator for async functions to apply Stamped Caching + Singleflight Coalescing.
    """
    def decorator(fn: Callable[..., Any]):
        @functools.wraps(fn)
        async def wrapper(*args, **kwargs):
            settings = get_settings()
            if not settings.stamped_cache_enabled:
                return await fn(*args, **kwargs)

            effective_ttl = ttl or settings.stamped_cache_default_ttl
            effective_swr = swr_grace or settings.stamped_cache_swr_grace
            beta = settings.stamped_cache_beta

            # Build deterministic cache key
            key_parts = [key_prefix, fn.__name__]
            if args:
                key_parts.extend([str(a) for a in args])
            if kwargs:
                key_parts.extend([f"{k}={v}" for k, v in sorted(kwargs.items())])
            cache_key = ":".join(key_parts)

            cached_val, needs_recompute = stamped_cache.get(cache_key, beta=beta)
            if cached_val is not None and not needs_recompute:
                return cached_val

            # Execute via singleflight request coalescing to prevent thundering herd
            async def compute():
                start = time.perf_counter()
                val = await fn(*args, **kwargs)
                delta = time.perf_counter() - start
                stamped_cache.set(cache_key, val, delta, effective_ttl, effective_swr)
                return val

            if cached_val is not None and needs_recompute:
                # Stale-While-Revalidate: trigger background recomputation without blocking caller
                asyncio.create_task(stamped_cache.singleflight.execute(cache_key, compute))
                return cached_val

            # Hard miss: block and coalesce
            return await stamped_cache.singleflight.execute(cache_key, compute)

        return wrapper
    return decorator
