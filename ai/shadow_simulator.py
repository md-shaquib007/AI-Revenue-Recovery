import math
import random
from typing import Any, Dict, List, Optional
from domain.models.enums import ActionType, CustomerTier, FailureCode, PaymentMethod
from domain.models.schemas import CustomerSchema, PaymentSchema


class ShadowPersona:
    def __init__(self, name: str, weight: float, sensitivity: float, preferred_channel: str):
        self.name = name
        self.weight = weight
        self.sensitivity = sensitivity  # 0.0 (tolerant) to 1.0 (easily frustrated)
        self.preferred_channel = preferred_channel

    def evaluate_action(self, action: ActionType, failure_code: Optional[FailureCode] = None) -> float:
        """
        Returns persona acceptance score (0.0 to 1.0) for a proposed action.
        Higher = more willing to pay through this channel/method.
        """
        if action == ActionType.WAIT:
            # High tolerance for waiting on 3DS or bank issues
            return 0.95 if failure_code in (FailureCode.BAD_REQUEST_AUTHENTICATION_FAILED, FailureCode.GATEWAY_ERROR) else 0.70

        elif action == ActionType.PAYMENT_LINK:
            # Prefers direct link if balance or card expired
            return 0.88 if failure_code in (FailureCode.INSUFFICIENT_FUNDS, FailureCode.CARD_EXPIRED) else 0.65

        elif action == ActionType.SMART_RETRY:
            # Low friction only if retry is background/silent — sensitive personas hate surprise charges
            return 0.90 if self.sensitivity < 0.6 else 0.42

        elif action == ActionType.METHOD_SWITCH:
            return 0.78 if failure_code == FailureCode.CARD_BLOCKED else 0.55

        elif action == ActionType.HUMAN_ESCALATION:
            # VIP users appreciate white-glove; others find it invasive
            return 0.85 if self.sensitivity < 0.35 else 0.55

        elif action == ActionType.DO_NOT_CONTACT:
            # Respected by all — no friction possible
            return 1.0

        return 0.50


# 5 core archetypes — cycled to fill 50 synthetic personas
SYNTHETIC_PERSONAS = [
    ShadowPersona("Salary-Day Sensitive",  weight=0.25, sensitivity=0.4,  preferred_channel="PAYMENT_LINK"),
    ShadowPersona("3DS Frustrated",         weight=0.20, sensitivity=0.8,  preferred_channel="WAIT"),
    ShadowPersona("VIP Enterprise",         weight=0.15, sensitivity=0.2,  preferred_channel="HUMAN_ESCALATION"),
    ShadowPersona("Budget Conscious",       weight=0.20, sensitivity=0.5,  preferred_channel="PAYMENT_LINK"),
    ShadowPersona("Mobile UPI Native",      weight=0.20, sensitivity=0.3,  preferred_channel="METHOD_SWITCH"),
]

# Candidate actions that can be scored for friction comparison
_SCOREABLE_ACTIONS = [
    ActionType.PAYMENT_LINK,
    ActionType.SMART_RETRY,
    ActionType.WAIT,
    ActionType.METHOD_SWITCH,
    ActionType.HUMAN_ESCALATION,
]


class MultiAgentShadowSimulator:
    """
    Autonomous Multi-Agent Shadow Simulator.

    Simulates 50 parallel prospective customer shadow personas reacting to
    candidate actions BEFORE the policy engine or system executes, calculating
    friction and consensus so the recovery loop can make better routing decisions.

    Key upgrade: Uses a seeded RNG (payment_id + action) so simulations are
    **deterministic per payment** — identical results on replay, audit-safe.
    """

    def _run_sim(
        self,
        payment: PaymentSchema,
        customer: CustomerSchema,
        proposed_action: ActionType,
        rng: random.Random,
    ) -> Dict[str, Any]:
        failure_code = payment.failure_code
        persona_scores: List[Dict[str, Any]] = []
        weighted_score_sum = 0.0
        total_weight = 0.0
        high_friction_count = 0

        for idx in range(50):
            base_persona = SYNTHETIC_PERSONAS[idx % len(SYNTHETIC_PERSONAS)]
            # Deterministic micro-variance seeded by payment+action
            jitter = (rng.random() - 0.5) * 0.15
            score = max(0.0, min(1.0, base_persona.evaluate_action(proposed_action, failure_code) + jitter))

            if score < 0.45:
                high_friction_count += 1

            persona_scores.append({
                "persona_id": f"persona_{idx + 1:02d}",
                "archetype": base_persona.name,
                "score": round(score, 3),
                "channel": base_persona.preferred_channel,
            })

            weighted_score_sum += score * base_persona.weight
            total_weight += base_persona.weight

        consensus_score = round((weighted_score_sum / max(0.001, total_weight)) * 100, 1)
        friction_score = round((high_friction_count / 50.0) * 100, 1)
        return consensus_score, friction_score, high_friction_count, persona_scores

    def simulate(
        self,
        payment: PaymentSchema,
        customer: CustomerSchema,
        proposed_action: ActionType,
    ) -> Dict[str, Any]:
        """
        Simulates 50 customer personas against the proposed action.
        Returns consensus, friction, persona samples, and whether a pivot is recommended.
        The simulation is deterministic: same payment_id + action → same result.
        """
        # Seed RNG: deterministic per (payment_id, action) pair → audit-safe
        seed = hash(f"{payment.id}:{proposed_action.value}") & 0xFFFF_FFFF
        rng = random.Random(seed)

        consensus_score, friction_score, high_friction_count, persona_scores = self._run_sim(
            payment, customer, proposed_action, rng
        )

        recommended_pivot = None
        if friction_score > 45.0 and proposed_action not in (ActionType.WAIT, ActionType.DO_NOT_CONTACT):
            # Find the lowest-friction alternative
            alt = self.best_alternative_action(payment, customer, exclude=proposed_action)
            if alt:
                recommended_pivot = alt.value

        return {
            "consensus_index_pct": consensus_score,
            "friction_score_pct": friction_score,
            "high_friction_personas_count": high_friction_count,
            "recommended_pivot": recommended_pivot,
            "personas_sample": persona_scores[:8],
            "total_simulated_personas": 50,
            "seed": seed,
        }

    def best_alternative_action(
        self,
        payment: PaymentSchema,
        customer: CustomerSchema,
        exclude: Optional[ActionType] = None,
    ) -> Optional[ActionType]:
        """
        Scores all candidate actions and returns the one with the lowest friction score.
        Used to auto-pivot when the proposed action exceeds the friction threshold.
        """
        best_action: Optional[ActionType] = None
        best_friction = 100.0

        for action in _SCOREABLE_ACTIONS:
            if action == exclude:
                continue
            seed = hash(f"{payment.id}:{action.value}") & 0xFFFF_FFFF
            rng = random.Random(seed)
            _, friction, _, _ = self._run_sim(payment, customer, action, rng)
            if friction < best_friction:
                best_friction = friction
                best_action = action

        return best_action


# Global singleton instance
shadow_simulator = MultiAgentShadowSimulator()
