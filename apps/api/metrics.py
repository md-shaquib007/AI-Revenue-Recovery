from collections import defaultdict
from threading import Lock


class AppMetrics:
    """Process-local counters for /metrics (Prometheus text format)."""

    def __init__(self) -> None:
        self._lock = Lock()
        self.counters = defaultdict(int)

    def inc(self, name: str, amount: int = 1) -> None:
        with self._lock:
            self.counters[name] += amount

    def snapshot(self) -> dict:
        with self._lock:
            return dict(self.counters)

    def prometheus(self) -> str:
        lines = [
            "# HELP revive_webhook_received_total Webhooks accepted for processing",
            "# TYPE revive_webhook_received_total counter",
            f"revive_webhook_received_total {self.counters.get('webhook_received', 0)}",
            "# HELP revive_webhook_duplicate_total Duplicate webhook deliveries ignored",
            "# TYPE revive_webhook_duplicate_total counter",
            f"revive_webhook_duplicate_total {self.counters.get('webhook_duplicate', 0)}",
            "# HELP revive_webhook_failed_total Webhooks that entered the dead-letter path",
            "# TYPE revive_webhook_failed_total counter",
            f"revive_webhook_failed_total {self.counters.get('webhook_failed', 0)}",
            "# HELP revive_worker_ticks_total Recovery worker loop iterations",
            "# TYPE revive_worker_ticks_total counter",
            f"revive_worker_ticks_total {self.counters.get('worker_ticks', 0)}",
            "# HELP revive_worker_actions_total Recovery actions executed by the worker",
            "# TYPE revive_worker_actions_total counter",
            f"revive_worker_actions_total {self.counters.get('worker_actions', 0)}",
            "# HELP revive_policy_veto_total Policy firewall overrides of AI proposals",
            "# TYPE revive_policy_veto_total counter",
            f"revive_policy_veto_total {self.counters.get('policy_veto', 0)}",
            "# HELP revive_rate_limited_total Requests rejected by rate limiter",
            "# TYPE revive_rate_limited_total counter",
            f"revive_rate_limited_total {self.counters.get('rate_limited', 0)}",
            "# HELP revive_strategy_cache_hits_total Strategy cache hits",
            "# TYPE revive_strategy_cache_hits_total counter",
            f"revive_strategy_cache_hits_total {self.counters.get('strategy_cache_hits', 0)}",
            "# HELP revive_audit_verifications_total Audit chain integrity verifications",
            "# TYPE revive_audit_verifications_total counter",
            f"revive_audit_verifications_total {self.counters.get('audit_verifications', 0)}",
            "# HELP revive_shadow_sim_pivots_total Shadow Simulator auto-pivots executed",
            "# TYPE revive_shadow_sim_pivots_total counter",
            f"revive_shadow_sim_pivots_total {self.counters.get('shadow_sim_pivot', 0)}",
            "# HELP revive_sentinel_cooloffs_total Predictive Sentinel cooloff overrides",
            "# TYPE revive_sentinel_cooloffs_total counter",
            f"revive_sentinel_cooloffs_total {self.counters.get('sentinel_cooloff', 0)}",
            "# HELP revive_offer_engine_applied_total Dynamic Micro-Incentive offers applied",
            "# TYPE revive_offer_engine_applied_total counter",
            f"revive_offer_engine_applied_total {self.counters.get('offer_engine_applied', 0)}",
        ]
        return "\n".join(lines) + "\n"


metrics = AppMetrics()
