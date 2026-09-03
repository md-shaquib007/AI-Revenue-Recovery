import time
from typing import Dict, Optional, Tuple
from domain.models.schemas import AIDecisionProposal


class StrategyCache:
    """
    High-Speed Strategy Template & Decision Cache.
    Allows high-throughput (<1ms) recovery strategy evaluation for recurring
    failure signatures under high concurrency.
    """

    def __init__(self, default_ttl_seconds: int = 3600) -> None:
        self._cache: Dict[str, Tuple[float, AIDecisionProposal]] = {}
        self.default_ttl = default_ttl_seconds

    @staticmethod
    def build_cache_key(
        failure_code: Optional[str],
        payment_method: Optional[str],
        customer_tier: str,
        bank_health_band: str,
    ) -> str:
        return f"{failure_code or 'UNKNOWN'}:{payment_method or 'UNKNOWN'}:{customer_tier}:{bank_health_band}"

    def get(self, cache_key: str) -> Optional[AIDecisionProposal]:
        now = time.time()
        if cache_key in self._cache:
            expires_at, proposal = self._cache[cache_key]
            if now < expires_at:
                return proposal
            del self._cache[cache_key]
        return None

    def set(self, cache_key: str, proposal: AIDecisionProposal, ttl_seconds: Optional[int] = None) -> None:
        ttl = ttl_seconds or self.default_ttl
        self._cache[cache_key] = (time.time() + ttl, proposal)

    def clear(self) -> None:
        self._cache.clear()


# Global singleton instance
strategy_cache = StrategyCache()
