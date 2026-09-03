import time
from domain.bank_health.matrix import bank_health_matrix
from ai.oracle import contact_delay_seconds, churn_risk as oracle_churn
from apps.api.settings import get_settings
from services.bank_resolver import infer_bank_key
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


class DeterministicFallbackEngine:
    """
    Zero-Downtime Deterministic Fallback Engine.
    Executes if the AI model fails, times out, or during chaos injection.
    """

    @staticmethod
    def calculate_expected_value(
        amount_paise: int,
        confidence: float,
        channel_cost_paise: int = 150,
        friction_penalty_paise: int = 500,
    ) -> int:
        """EV = P(recovery) * Amount - ActionCost - FrictionPenalty"""
        raw_ev = (confidence * amount_paise) - channel_cost_paise - friction_penalty_paise
        return max(0, int(raw_ev))

    def evaluate(self, payment: PaymentSchema, customer: CustomerSchema) -> AIDecisionProposal:
        start_time = time.perf_counter()

        bank_key = infer_bank_key(
            {"notes": payment.notes, "method": payment.method.value if payment.method else None},
            payment.method.value if payment.method else None,
        )
        bank_health = bank_health_matrix.get_health_score(bank_key)

        smart_delay = bank_health_matrix.calculate_smart_delay(
            payment.failure_code, payment.method, bank_name=bank_key
        )

        # Strategy Selection Matrix
        candidate_actions = []

        if payment.failure_code in [FailureCode.GATEWAY_ERROR, FailureCode.BANK_DOWNTIME, FailureCode.NETWORK_ERROR]:
            conf = 0.88 if bank_health > 0.7 else 0.45
            ev = self.calculate_expected_value(payment.amount_in_paise, conf, channel_cost_paise=0, friction_penalty_paise=0)
            primary = CandidateAction(
                action=ActionType.SMART_RETRY if bank_health > 0.7 else ActionType.WAIT,
                confidence_score=conf,
                expected_value_in_paise=ev,
                delay_seconds=smart_delay,
                channel="silent_api",
                rationale=f"Transient infrastructure issue (Bank health: {bank_health:.2f}). Scheduled auto-retry after cooloff.",
            )
            candidate_actions.append(primary)
            category = "TRANSIENT_INFRASTRUCTURE"
            is_transient = True

        elif payment.failure_code == FailureCode.BAD_REQUEST_AUTHENTICATION_FAILED:
            # 3DS OTP dropout
            conf = 0.78
            ev = self.calculate_expected_value(payment.amount_in_paise, conf, channel_cost_paise=0, friction_penalty_paise=0)
            primary = CandidateAction(
                action=ActionType.WAIT,
                confidence_score=conf,
                expected_value_in_paise=ev,
                delay_seconds=480,  # 8 min grace window
                channel="silent_grace",
                rationale="3DS Authentication dropped. Grace window opened for organic customer retry.",
            )
            candidate_actions.append(primary)
            category = "CUSTOMER_DROP_OFF"
            is_transient = True

        elif payment.failure_code == FailureCode.INSUFFICIENT_FUNDS:
            conf = 0.65
            ev = self.calculate_expected_value(payment.amount_in_paise, conf, channel_cost_paise=250, friction_penalty_paise=400)
            primary = CandidateAction(
                action=ActionType.PAYMENT_LINK,
                confidence_score=conf,
                expected_value_in_paise=ev,
                delay_seconds=0,
                channel="whatsapp",
                communication_copy=f"Hi {customer.name}, your subscription payment of ₹{payment.amount_in_paise / 100:,.2f} could not be processed. Tap here to complete it securely: {{payment_link}}",
                rationale="Insufficient balance on card. Issued 1-click Razorpay payment link via WhatsApp.",
            )
            candidate_actions.append(primary)
            category = "BALANCE_DEFICIT"
            is_transient = False

        elif payment.failure_code == FailureCode.CARD_EXPIRED:
            conf = 0.72
            ev = self.calculate_expected_value(payment.amount_in_paise, conf, channel_cost_paise=250, friction_penalty_paise=300)
            primary = CandidateAction(
                action=ActionType.PAYMENT_LINK,
                confidence_score=conf,
                expected_value_in_paise=ev,
                delay_seconds=0,
                channel="sms",
                communication_copy=f"Your card for order {payment.order_id or payment.id} has expired. Update your payment method in 1 click: {{payment_link}}",
                rationale="Card expired. Generated Razorpay payment link for customer to authenticate new card/UPI.",
            )
            candidate_actions.append(primary)
            category = "EXPIRED_INSTRUMENT"
            is_transient = False

        elif payment.failure_code == FailureCode.TRANSACTION_LIMIT_EXCEEDED:
            conf = 0.68
            ev = self.calculate_expected_value(payment.amount_in_paise, conf, channel_cost_paise=200, friction_penalty_paise=300)
            primary = CandidateAction(
                action=ActionType.METHOD_SWITCH,
                confidence_score=conf,
                expected_value_in_paise=ev,
                delay_seconds=0,
                channel="whatsapp",
                communication_copy=f"Hi {customer.name}, daily limit reached. Pay via Netbanking or Card: {{payment_link}}",
                rationale="Velocity limit. Switch rail.",
            )
            candidate_actions.append(primary)
            category = "VELOCITY_LIMIT_BREACH"
            is_transient = False

        elif payment.failure_code in [FailureCode.CARD_BLOCKED, FailureCode.ACCOUNT_FROZEN]:
            conf = 0.60
            ev = self.calculate_expected_value(payment.amount_in_paise, conf, channel_cost_paise=180, friction_penalty_paise=220)
            primary = CandidateAction(
                action=ActionType.METHOD_SWITCH,
                confidence_score=conf,
                expected_value_in_paise=ev,
                delay_seconds=0,
                channel="whatsapp",
                communication_copy=f"Hi {customer.name}, please complete ₹{payment.amount_in_paise / 100:,.2f} via UPI: {{payment_link}}",
                rationale="Dead instrument. Forced method switch; no auto-retry.",
            )
            candidate_actions.append(primary)
            category = "DEAD_INSTRUMENT"
            is_transient = False

        elif payment.failure_code == FailureCode.FRAUD_SUSPECTED:
            conf = 0.30
            ev = self.calculate_expected_value(payment.amount_in_paise, conf, channel_cost_paise=0, friction_penalty_paise=0)
            primary = CandidateAction(
                action=ActionType.HUMAN_ESCALATION,
                confidence_score=conf,
                expected_value_in_paise=ev,
                delay_seconds=0,
                channel="ops_queue",
                rationale="Fraud-suspected. Deterministic fallback refuses auto-contact.",
            )
            candidate_actions.append(primary)
            category = "FRAUD_HOLD"
            is_transient = False

        else:
            # Default fallback
            conf = 0.50
            ev = self.calculate_expected_value(payment.amount_in_paise, conf)
            primary = CandidateAction(
                action=ActionType.WAIT,
                confidence_score=conf,
                expected_value_in_paise=ev,
                delay_seconds=300,
                channel="silent_api",
                rationale="Unclassified failure code. Holding in 5-minute observation window.",
            )
            candidate_actions.append(primary)
            category = "UNCLASSIFIED_ERROR"
            is_transient = True

        delay = contact_delay_seconds(enabled=get_settings().use_circadian_send)
        if delay > 0 and primary.action in (ActionType.PAYMENT_LINK, ActionType.METHOD_SWITCH):
            primary.delay_seconds = delay
            primary.rationale = f"{primary.rationale} Quiet-hours deferral until 10:00 IST ({delay}s)."

        elapsed_ms = int((time.perf_counter() - start_time) * 1000)

        return AIDecisionProposal(
            failure_category=category,
            is_transient=is_transient,
            customer_churn_risk=oracle_churn(customer),
            recommended_actions=candidate_actions,
            primary_action=primary,
            operator_explanation=f"[Deterministic Fallback Engine] Evaluated payment {payment.id} using rule tables. Recommended action: {primary.action.value} with delay {primary.delay_seconds}s.",
            agent_mode=AgentMode.DETERMINISTIC_FALLBACK,
            latency_ms=elapsed_ms,
            tokens_used=0,
        )


deterministic_fallback_engine = DeterministicFallbackEngine()
