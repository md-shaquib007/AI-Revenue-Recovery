from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
from domain.bank_health.matrix import bank_health_matrix


class BankSentinelPredictor:
    """
    Predictive Bank Downtime Sentinel.

    Monitors failure velocity (dF/dt) across 3-minute sliding windows to detect
    incipient bank outages BEFORE official announcements, triggering proactive cool-offs.

    Integrated into the core recovery loop:
    - `record_event()` is called on every payment.failed event.
    - `record_success()` is called on every payment.captured — self-heals velocity windows.
    - `is_circuit_open()` is a fast boolean gate for policy firewall and routing.
    """

    def __init__(self):
        # Sliding window event log: entity_key -> List[(timestamp, is_failure)]
        self._events: Dict[str, List[Tuple[datetime, bool]]] = {}
        self._velocity_threshold = 3.5  # Failures/min acceleration threshold
        self._circuit_state: Dict[str, bool] = {}  # entity_key -> True if open

    def record_event(self, entity_key: str, is_failure: bool) -> None:
        """
        Records a payment outcome event for the given bank/gateway entity.
        Call on EVERY payment.failed (is_failure=True) and payment.captured (is_failure=False).
        """
        entity_key = entity_key.upper()
        now = datetime.utcnow()
        if entity_key not in self._events:
            self._events[entity_key] = []

        self._events[entity_key].append((now, is_failure))

        # Prune events older than 5 minutes to keep memory bounded
        cutoff = now - timedelta(minutes=5)
        self._events[entity_key] = [ev for ev in self._events[entity_key] if ev[0] >= cutoff]

    def record_success(self, entity_key: str) -> None:
        """
        Convenience method called on payment.captured.
        Adds a success event to the sliding window so failure velocity self-heals.
        If a circuit was open and velocity drops below threshold, auto-recovers.
        """
        self.record_event(entity_key, is_failure=False)

        # Check if the circuit can be healed now
        entity_key = entity_key.upper()
        if self._circuit_state.get(entity_key):
            analytics = self.evaluate_predictive_circuit(entity_key)
            if not analytics["circuit_triggered"]:
                # Velocity has dropped — recover the bank in the health matrix
                self._circuit_state[entity_key] = False
                bank_health_matrix.recover_entity(entity_key)

    def is_circuit_open(self, entity_key: str) -> bool:
        """
        Fast boolean gate: returns True if this bank/gateway is currently in predictive cooloff.
        Used by correlation_engine and policy_engine for routing decisions without re-evaluating.
        """
        return self._circuit_state.get(entity_key.upper(), False)

    def evaluate_predictive_circuit(self, entity_key: str) -> Dict[str, Any]:
        """
        Calculates failure velocity (dF/dt) and predictive outage probability.
        If acceleration >= threshold, automatically injects a predictive cooloff window
        into the BankHealthMatrix and marks the circuit as open.
        """
        entity_key = entity_key.upper()
        now = datetime.utcnow()
        events = self._events.get(entity_key, [])

        if len(events) < 5:
            return {
                "entity_key": entity_key,
                "predictive_outage_risk_pct": 5.0,
                "failure_velocity_per_min": 0.0,
                "status": "STABLE",
                "circuit_triggered": False,
                "events_analyzed": len(events),
            }

        cutoff_3m = now - timedelta(minutes=3)
        recent_failures = [ev for ev in events if ev[0] >= cutoff_3m and ev[1]]
        recent_successes = [ev for ev in events if ev[0] >= cutoff_3m and not ev[1]]

        velocity = len(recent_failures) / 3.0  # Failures per minute
        # Adjust risk for concurrent successes — partial recovery observed
        success_damping = min(0.4, len(recent_successes) * 0.05)
        adjusted_velocity = max(0.0, velocity - success_damping)
        risk_pct = min(99.0, round(adjusted_velocity * 22.5, 1))
        circuit_triggered = False

        if velocity >= self._velocity_threshold or risk_pct >= 75.0:
            # Predictively inject 20-minute downtime cooloff to protect retry caps
            bank_health_matrix.inject_downtime(entity_key, duration_minutes=20, degraded_score=0.20)
            self._circuit_state[entity_key] = True
            circuit_triggered = True
        else:
            # Mark circuit as closed if velocity has recovered
            self._circuit_state[entity_key] = False

        status = "PREDICTIVE_COOLOFF" if circuit_triggered else ("ELEVATED_RISK" if risk_pct > 40 else "STABLE")

        return {
            "entity_key": entity_key,
            "predictive_outage_risk_pct": risk_pct,
            "failure_velocity_per_min": round(velocity, 2),
            "status": status,
            "circuit_triggered": circuit_triggered,
            "events_analyzed": len(events),
            "recent_failures": len(recent_failures),
            "recent_successes": len(recent_successes),
        }


# Global singleton instance
bank_sentinel = BankSentinelPredictor()
