import math
import random
from typing import Any, Dict, Optional, Tuple
from domain.models.enums import CustomerTier, FailureCode


class ContextualBanditEngine:
    """
    Contextual Multi-Armed Bandit Engine for Dynamic Expected Value (EV) Calibration.

    Uses Thompson Sampling with Beta distributions B(α, β) per contextual segment:
        segment_key = (failure_code, bank_key, customer_tier)

    Continuous Online Learning:
    - On payment.captured (success): α += 1
    - On payment.failed (unrecovered): β += 1

    Calculates:
    - Mean recovery probability: E[P] = α / (α + β)
    - Thompson Sample probability P_sampled ~ Beta(α, β)
    """

    def __init__(self) -> None:
        # Segment key -> [alpha, beta]
        # Baseline prior B(2, 3) gives mean P = 0.40 with moderate variance
        self._beta_priors: Dict[str, Tuple[float, float]] = {}

    def _segment_key(
        self,
        failure_code: Optional[FailureCode],
        bank_key: Optional[str],
        customer_tier: Optional[CustomerTier],
    ) -> str:
        fc = failure_code.value if failure_code else "UNKNOWN"
        bk = (bank_key or "HDFC").upper()
        ct = customer_tier.value if customer_tier else "STANDARD"
        return f"{fc}:{bk}:{ct}"

    def get_priors(
        self,
        failure_code: Optional[FailureCode],
        bank_key: Optional[str],
        customer_tier: Optional[CustomerTier],
    ) -> Tuple[float, float]:
        key = self._segment_key(failure_code, bank_key, customer_tier)
        if key not in self._beta_priors:
            # Domain-informed priors:
            # NSF/Balance failures start lower (α=2, β=4 -> mean 0.33)
            # Transient / Bank errors start higher (α=4, β=2 -> mean 0.67)
            if failure_code == FailureCode.INSUFFICIENT_FUNDS:
                self._beta_priors[key] = (2.0, 4.0)
            elif failure_code in (FailureCode.BAD_REQUEST_AUTHENTICATION_FAILED, FailureCode.GATEWAY_ERROR):
                self._beta_priors[key] = (4.0, 2.0)
            else:
                self._beta_priors[key] = (3.0, 3.0)
        return self._beta_priors[key]

    def record_outcome(
        self,
        failure_code: Optional[FailureCode],
        bank_key: Optional[str],
        customer_tier: Optional[CustomerTier],
        recovered: bool,
        decay_factor: float = 0.98,
    ) -> Dict[str, Any]:
        """
        Updates the segment's Beta distribution upon receiving a recovery outcome.
        Applies an exponential recency decay factor (default 0.98) to ensure that
        transient bank outages do not permanently suppress future recovery probabilities.
        """
        key = self._segment_key(failure_code, bank_key, customer_tier)
        alpha, beta = self.get_priors(failure_code, bank_key, customer_tier)

        # Apply exponential recency decay with a floor of 1.0
        if 0.0 < decay_factor < 1.0:
            alpha = max(1.0, alpha * decay_factor)
            beta = max(1.0, beta * decay_factor)

        if recovered:
            alpha += 1.0
        else:
            beta += 1.0

        self._beta_priors[key] = (alpha, beta)
        mean_p = round(alpha / (alpha + beta), 3)

        return {
            "segment_key": key,
            "alpha": round(alpha, 3),
            "beta": round(beta, 3),
            "learned_mean_p": mean_p,
            "samples_observed": max(1, int(alpha + beta - 5.0)),
        }

    def predict_recovery_probability(
        self,
        failure_code: Optional[FailureCode],
        bank_key: Optional[str],
        customer_tier: Optional[CustomerTier],
        sample: bool = False,
    ) -> float:
        """
        Returns estimated P(recovery) for EV calculation.
        If sample=True, draws a Thompson sample from Beta(α, β).
        Otherwise returns mean E[P] = α / (α + β).
        """
        alpha, beta = self.get_priors(failure_code, bank_key, customer_tier)
        if sample:
            p_draw = random.betavariate(alpha, beta)
            return round(max(0.05, min(0.95, p_draw)), 3)

        return round(alpha / (alpha + beta), 3)


# Global singleton instance
contextual_bandit = ContextualBanditEngine()
