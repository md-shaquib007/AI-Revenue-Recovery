import os
import time
from typing import Optional
from domain.bank_health.matrix import bank_health_matrix
from domain.models.enums import (
    ActionType,
    AgentMode,
    CustomerTier,
    FailureCode,
    PaymentMethod,
)
from domain.models.schemas import (
    AIDecisionProposal,
    CandidateAction,
    CustomerSchema,
    PaymentSchema,
)
from ai.fallback import deterministic_fallback_engine
from ai.llm_adapter import try_llm_proposal
from ai.oracle import contact_delay_seconds, churn_risk as oracle_churn
from apps.api.settings import get_settings
from services.bank_resolver import infer_bank_key


from ai.bandit import contextual_bandit


class AIRecoveryAgent:
    """
    Autonomous AI Reasoning Agent for Razorpay Revenue Recovery.
    Performs multi-factor diagnostics, computes expected value (EV),
    generates contextual communication copy, and produces full audit explanations.
    """

    def __init__(self):
        self._llm_outage_simulated = False

    def simulate_llm_outage(self, is_down: bool = True):
        """Used for chaos engineering tests to simulate LLM API failure."""
        self._llm_outage_simulated = is_down

    def calculate_expected_value(
        self,
        amount_paise: int,
        confidence: float,
        channel_cost_paise: int = 150,
        friction_penalty_paise: int = 400,
        failure_code: Optional[FailureCode] = None,
        bank_key: Optional[str] = None,
        customer_tier: Optional[CustomerTier] = None,
    ) -> int:
        """
        Expected Value Theorem with Contextual Bandit Calibration:
        EV = (P_blended * InvoiceAmount) - ActionCost - CustomerChurnPenalty
        Where P_blended = 0.6 * P_agent_confidence + 0.4 * P_bandit_learned
        """
        p_learned = contextual_bandit.predict_recovery_probability(failure_code, bank_key, customer_tier)
        p_blended = (0.6 * confidence) + (0.4 * p_learned)
        raw_ev = (p_blended * amount_paise) - channel_cost_paise - friction_penalty_paise
        return max(0, int(raw_ev))

    async def reason(
        self,
        payment: PaymentSchema,
        customer: CustomerSchema,
    ) -> AIDecisionProposal:
        """
        Executes the reasoning loop.
        If an LLM outage is simulated or unhandled error occurs, smoothly
        falls back to DeterministicFallbackEngine.
        """
        start_time = time.perf_counter()
        settings = get_settings()
        if self._llm_outage_simulated:
            fallback = deterministic_fallback_engine.evaluate(payment, customer)
            fallback.operator_explanation = (
                "[CHAOS LAB NOTICE: LLM Outage Simulated] AI service was unreachable; "
                "Deterministic Fallback Engine executed safely with 0 downtime."
            )
            return fallback

        bank_key = infer_bank_key(
            {"notes": payment.notes, "method": payment.method.value if payment.method else None},
            payment.method.value if payment.method else None,
        )
        bank_health = bank_health_matrix.get_health_score(bank_key)
        health_band = "HEALTHY" if bank_health >= 0.75 else "DEGRADED"

        # 1. Hot Strategy Cache lookup for sub-millisecond evaluation
        cache_key = None
        if settings.strategy_cache_enabled:
            from ai.strategy_cache import strategy_cache
            cache_key = strategy_cache.build_cache_key(
                payment.failure_code.value if payment.failure_code else None,
                payment.method.value if payment.method else None,
                customer.tier.value,
                health_band,
            )
            cached = strategy_cache.get(cache_key)
            if cached is not None:
                # Clone and adjust for current payment amount
                ev = self.calculate_expected_value(payment.amount_in_paise, cached.primary_action.confidence_score)
                cached_action = cached.primary_action.model_copy()
                cached_action.expected_value_in_paise = ev
                clone = cached.model_copy(update={"primary_action": cached_action, "latency_ms": 1})
                return clone

        # 2. Strict Latency Budget on external LLM call
        try:
            import asyncio
            llm_proposal = await asyncio.wait_for(
                try_llm_proposal(payment, customer, bank_key, bank_health),
                timeout=settings.ai_timeout_seconds,
            )
            if llm_proposal is not None:
                llm_proposal.latency_ms = int((time.perf_counter() - start_time) * 1000)
                return llm_proposal
        except Exception:
            # Latency budget exceeded or LLM error; proceed to deterministic reasoning
            pass

        candidate_actions = []

        # Complex reasoning by failure category
        if payment.failure_code in [FailureCode.GATEWAY_ERROR, FailureCode.BANK_DOWNTIME, FailureCode.NETWORK_ERROR]:
            is_transient = True
            category = "INFRASTRUCTURE_GATEWAY_OUTAGE"
            smart_delay = bank_health_matrix.calculate_smart_delay(payment.failure_code, payment.method, bank_key)

            if bank_health < 0.7:
                conf = 0.40
                act_type = ActionType.WAIT
                rationale = f"Acquiring gateway {bank_key} is exhibiting high failure rates (Health: {bank_health:.2f}). Pausing retries for {smart_delay}s to avoid burning merchant limits."
            else:
                conf = 0.89
                act_type = ActionType.SMART_RETRY
                rationale = f"Bank gateway {bank_key} health is stable ({bank_health:.2f}). Scheduled automatic retry in {smart_delay}s."

            ev = self.calculate_expected_value(payment.amount_in_paise, conf, channel_cost_paise=0, friction_penalty_paise=0)
            primary = CandidateAction(
                action=act_type,
                confidence_score=conf,
                expected_value_in_paise=ev,
                delay_seconds=smart_delay,
                channel="silent_api",
                rationale=rationale,
            )
            candidate_actions.append(primary)

        elif payment.failure_code == FailureCode.BAD_REQUEST_AUTHENTICATION_FAILED:
            # 3DS OTP dropout: Grace window non-action
            is_transient = True
            category = "AUTH_3DS_DROPOUT"
            conf = 0.82
            ev = self.calculate_expected_value(payment.amount_in_paise, conf, channel_cost_paise=0, friction_penalty_paise=0)
            primary = CandidateAction(
                action=ActionType.WAIT,
                confidence_score=conf,
                expected_value_in_paise=ev,
                delay_seconds=480,
                channel="silent_grace",
                rationale="Customer dropped out during 3DS OTP entry. Initiated 8-minute silent Grace Window; awaiting organic customer retry or late webhook.",
            )
            candidate_actions.append(primary)

        elif payment.failure_code == FailureCode.INSUFFICIENT_FUNDS:
            is_transient = False
            category = "INSUFFICIENT_BALANCE"
            # If VIP customer, give higher confidence and premium messaging
            conf = 0.74 if customer.tier in [CustomerTier.VIP, CustomerTier.ENTERPRISE] else 0.58
            ev = self.calculate_expected_value(payment.amount_in_paise, conf, channel_cost_paise=200, friction_penalty_paise=300)
            
            first_name = customer.name.split()[0] if customer.name else "Customer"
            copy = f"Hello {first_name}, your payment of ₹{payment.amount_in_paise / 100:,.2f} for order {payment.order_id or payment.id} was declined due to insufficient funds. Complete your payment with 1-click via Razorpay: {{payment_link}}"
            
            primary = CandidateAction(
                action=ActionType.PAYMENT_LINK,
                confidence_score=conf,
                expected_value_in_paise=ev,
                delay_seconds=0,
                channel="whatsapp",
                communication_copy=copy,
                rationale="Card balance insufficient. Dispatched personalized 1-click Razorpay payment link via WhatsApp with instant retry options.",
            )
            candidate_actions.append(primary)

        elif payment.failure_code == FailureCode.CARD_EXPIRED:
            is_transient = False
            category = "EXPIRED_PAYMENT_INSTRUMENT"
            conf = 0.76
            ev = self.calculate_expected_value(payment.amount_in_paise, conf, channel_cost_paise=150, friction_penalty_paise=250)
            
            first_name = customer.name.split()[0] if customer.name else "Customer"
            copy = f"Hi {first_name}, your saved card on file has expired. Please update your payment method or pay via UPI/Card: {{payment_link}}"

            primary = CandidateAction(
                action=ActionType.PAYMENT_LINK,
                confidence_score=conf,
                expected_value_in_paise=ev,
                delay_seconds=0,
                channel="sms",
                communication_copy=copy,
                rationale="Card expired. Sent Razorpay multi-method payment link to update tokenized card or pay via UPI.",
            )
            candidate_actions.append(primary)

        elif payment.failure_code == FailureCode.TRANSACTION_LIMIT_EXCEEDED:
            is_transient = False
            category = "VELOCITY_LIMIT_BREACH"
            conf = 0.70
            ev = self.calculate_expected_value(payment.amount_in_paise, conf, channel_cost_paise=200, friction_penalty_paise=300)
            primary = CandidateAction(
                action=ActionType.METHOD_SWITCH,
                confidence_score=conf,
                expected_value_in_paise=ev,
                delay_seconds=0,
                channel="whatsapp",
                communication_copy=f"Hi {customer.name}, your bank daily UPI limit was reached for ₹{payment.amount_in_paise / 100:,.2f}. Tap here to pay via Netbanking or Credit Card: {{payment_link}}",
                rationale="Bank transaction limit exceeded. Recommended immediate switch to Netbanking/Card.",
            )
            candidate_actions.append(primary)

        elif payment.failure_code in [FailureCode.CARD_BLOCKED, FailureCode.ACCOUNT_FROZEN]:
            is_transient = False
            category = "DEAD_INSTRUMENT"
            conf = 0.62
            ev = self.calculate_expected_value(payment.amount_in_paise, conf, channel_cost_paise=180, friction_penalty_paise=220)
            first_name = customer.name.split()[0] if customer.name else "Customer"
            primary = CandidateAction(
                action=ActionType.METHOD_SWITCH,
                confidence_score=conf,
                expected_value_in_paise=ev,
                delay_seconds=0,
                channel="whatsapp",
                communication_copy=(
                    f"Hi {first_name}, your saved payment method could not be charged. "
                    f"Complete ₹{payment.amount_in_paise / 100:,.2f} via UPI or another card: {{payment_link}}"
                ),
                rationale="Instrument is permanently invalid. Switching rail to UPI/alternate card instead of retrying the dead token.",
            )
            candidate_actions.append(primary)

        elif payment.failure_code == FailureCode.FRAUD_SUSPECTED:
            is_transient = False
            category = "FRAUD_HOLD"
            conf = 0.35
            ev = self.calculate_expected_value(payment.amount_in_paise, conf, channel_cost_paise=0, friction_penalty_paise=0)
            primary = CandidateAction(
                action=ActionType.HUMAN_ESCALATION,
                confidence_score=conf,
                expected_value_in_paise=ev,
                delay_seconds=0,
                channel="ops_queue",
                rationale="Fraud-suspected failure must not auto-retry or auto-message. Escalated to Human Ops.",
            )
            candidate_actions.append(primary)

        else:
            is_transient = True
            category = "GENERAL_EXCEPTION"
            conf = 0.50
            ev = self.calculate_expected_value(payment.amount_in_paise, conf)
            primary = CandidateAction(
                action=ActionType.WAIT,
                confidence_score=conf,
                expected_value_in_paise=ev,
                delay_seconds=300,
                channel="silent_api",
                rationale="Unclassified failure. Holding in 5-minute observation window.",
            )
            candidate_actions.append(primary)

        delay = contact_delay_seconds(enabled=get_settings().use_circadian_send)
        if delay > 0 and primary.action in (ActionType.PAYMENT_LINK, ActionType.METHOD_SWITCH):
            primary.delay_seconds = delay
            primary.rationale = (
                f"{primary.rationale} Quiet-hours deferral: outbound held {delay}s until 10:00 IST."
            )

        elapsed_ms = int((time.perf_counter() - start_time) * 1000)

        explanation = (
            f"Diagnosed {category} (Transient: {is_transient}). Evaluated expected value "
            f"₹{primary.expected_value_in_paise / 100:,.2f} with confidence {primary.confidence_score * 100:.1f}%. "
            f"Strategy: {primary.action.value} ({primary.rationale})."
        )

        proposal = AIDecisionProposal(
            failure_category=category,
            is_transient=is_transient,
            customer_churn_risk=oracle_churn(customer),
            recommended_actions=candidate_actions,
            primary_action=primary,
            operator_explanation=explanation,
            agent_mode=AgentMode.AI_REASONER,
            latency_ms=elapsed_ms,
            tokens_used=0,
        )

        if settings.strategy_cache_enabled and cache_key:
            from ai.strategy_cache import strategy_cache
            strategy_cache.set(cache_key, proposal, settings.strategy_cache_ttl_seconds)

        return proposal


# Global singleton instance
ai_recovery_agent = AIRecoveryAgent()
