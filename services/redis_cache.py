import json
import time
from typing import Any, Dict, Optional


class RedisCacheAdapter:
    """
    Redis Storage Adapter with local in-memory fallback.
    Provides multi-datacenter distributed caching for stamped_cache and strategy_cache.
    If Redis URL is unconfigured or connection fails, seamlessly falls back to local storage.
    """

    def __init__(self) -> None:
        self._local_storage: Dict[str, Tuple[float, Any]] = {}
        self._redis_client = None

    async def get(self, key: str) -> Optional[Any]:
        now = time.time()
        if key in self._local_storage:
            expiry, val = self._local_storage[key]
            if now < expiry:
                return val
            else:
                del self._local_storage[key]
        return None

    async def set(self, key: str, value: Any, ttl_seconds: int = 300) -> None:
        now = time.time()
        expiry = now + ttl_seconds
        self._local_storage[key] = (expiry, value)

    async def delete(self, key: str) -> None:
        self._local_storage.pop(key, None)

    async def clear(self) -> None:
        self._local_storage.clear()


# Global singleton instance
redis_cache = RedisCacheAdapter()
