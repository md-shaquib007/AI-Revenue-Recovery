import re
from datetime import datetime, timedelta
from typing import List, Optional
from domain.models.enums import (
    ActionType,
    CustomerTier,
    FailureCode,
    PaymentStatus,
    RiskTier,
)
from domain.models.schemas import (
    CandidateAction,
    CustomerSchema,
    PaymentSchema,
    PolicyCheckItem,
    PolicyEvaluationResult,
)


# Lazy import to avoid circular dependency — sentinel is domain-level
def _get_sentinel():
    from domain.bank_health.sentinel import bank_sentinel
    return bank_sentinel



class PolicyEngine:
    """
    Deterministic Financial & Behavioral Safety Engine.
    The immutable firewall that validates or vetoes AI recommendations.
    """

    HIGH_VALUE_THRESHOLD_PAISE = 5_000_000  # ₹50,000.00
    MAX_CONTACTS_WINDOW_HOURS = 48
    MAX_CONTACTS_PER_WINDOW = 2

    # Suspicious prompt injection patterns in user-controlled metadata
    PROMPT_INJECTION_PATTERNS = [
        re.compile(r"ignore\s+(all\s+)?(previous\s+)?instructions", re.IGNORECASE),
        re.compile(r"system\s*prompt", re.IGNORECASE),
        re.compile(r"issue\s+(full\s+)?refund", re.IGNORECASE),
        re.compile(r"admin\s+override", re.IGNORECASE),
        re.compile(r"drop\s+table", re.IGNORECASE),
        re.compile(r"authorize\s+zero\s+charge", re.IGNORECASE),
    ]

    def contacts_in_window(self, customer: CustomerSchema, now: Optional[datetime] = None) -> int:
        """Count outbound contacts inside the rolling fatigue window."""
        now = now or datetime.utcnow()
        cutoff = now - timedelta(hours=self.MAX_CONTACTS_WINDOW_HOURS)
        count = 0
        for ts in customer.contact_timestamps or []:
            if ts >= cutoff:
                count += 1
        return count

    def remaining_tokens(self, customer: CustomerSchema, now: Optional[datetime] = None) -> int:
        used = self.contacts_in_window(customer, now)
        return max(0, min(customer.contact_token_bucket, self.MAX_CONTACTS_PER_WINDOW - used))

    def sanitize_untrusted_input(self, text: Optional[str]) -> str:
        """Sanitizes user-provided payment notes or descriptions against prompt injection."""
        if not text:
            return ""
        sanitized = text
        for pattern in self.PROMPT_INJECTION_PATTERNS:
            if pattern.search(sanitized):
                sanitized = pattern.sub("[REDACTED_SECURITY_POLICY]", sanitized)
        return sanitized

    @staticmethod
    def mask_email(email: Optional[str]) -> str:
        """Masks email for PII protection (e.g. j****@example.com)."""
        if not email or "@" not in email:
            return email or ""
        name, domain = email.split("@", 1)
        if len(name) <= 2:
            masked_name = name[0] + "*"
        else:
            masked_name = name[0] + "*" * (len(name) - 2) + name[-1]
        return f"{masked_name}@{domain}"

    @staticmethod
    def mask_phone(phone: Optional[str]) -> str:
        """Masks phone number for PII protection (e.g. +91 98****3210)."""
        if not phone:
            return ""
        clean = phone.strip()
        if len(clean) < 6:
            return "*" * len(clean)
        return clean[:4] + "*" * (len(clean) - 6) + clean[-2:]

    @staticmethod
    def mask_name(name: Optional[str]) -> str:
        """Masks customer name for PII compliance (e.g. A**** S****)."""
        if not name:
            return ""
        parts = name.strip().split()
        masked_parts = []
        for p in parts:
            if len(p) <= 1:
                masked_parts.append(p)
            else:
                masked_parts.append(p[0] + "*" * (len(p) - 1))
        return " ".join(masked_parts)

    def evaluate(
        self,
        payment: PaymentSchema,
        customer: CustomerSchema,
        proposed_action: CandidateAction,
        is_already_captured: bool = False,
        bank_key: Optional[str] = None,
    ) -> PolicyEvaluationResult:
        """
        Runs the deterministic safety checklist on the AI's proposed action.
        bank_key: Optional gateway/bank identifier for Sentinel Circuit Override (Rule 7).
        """
        checks: List[PolicyCheckItem] = []
        approved_action = proposed_action.action
        requires_human = False
        override_reason: Optional[str] = None

        # Rule 7: Sentinel Predictive Circuit Override (checked first — highest priority)
        # If the bank sentinel has detected incipient outage velocity for this bank,
        # veto SMART_RETRY immediately to protect subscription retry caps.
        if bank_key and approved_action == ActionType.SMART_RETRY:
            sentinel = _get_sentinel()
            if sentinel.is_circuit_open(bank_key):
                checks.append(
                    PolicyCheckItem(
                        rule_name="SENTINEL_CIRCUIT_OVERRIDE",
                        passed=False,
                        detail=(
                            f"Predictive Bank Sentinel detected high failure velocity on {bank_key.upper()}. "
                            "SMART_RETRY vetoed to protect subscription retry caps. Forcing WAIT cooloff."
                        ),
                    )
                )
                approved_action = ActionType.WAIT
                override_reason = f"Sentinel circuit open: {bank_key.upper()} is in predictive cooloff."
            else:
                checks.append(
                    PolicyCheckItem(
                        rule_name="SENTINEL_CIRCUIT_OVERRIDE",
                        passed=True,
                        detail=f"Bank Sentinel: {bank_key.upper()} stable. SMART_RETRY permitted.",
                    )
                )

        # Rule 1: Zero Action on Captured Payment
        if is_already_captured or payment.status == PaymentStatus.CAPTURED:
            checks.append(
                PolicyCheckItem(
                    rule_name="NO_OP_ON_CAPTURED",
                    passed=True,
                    detail="Payment is already captured. Active recovery cancelled immediately.",
                )
            )
            return PolicyEvaluationResult(
                is_allowed=True,
                policy_checks=checks,
                approved_action=ActionType.CANCEL_RECOVERY,
                override_reason="Payment captured during triage.",
                requires_human_approval=False,
            )

        # Rule 2: Customer Opt-Out Verification
        if customer.opted_out and proposed_action.action in [ActionType.PAYMENT_LINK, ActionType.METHOD_SWITCH]:
            checks.append(
                PolicyCheckItem(
                    rule_name="OPT_OUT_GUARD",
                    passed=False,
                    detail="Customer has opted out of outbound recovery messages.",
                )
            )
            return PolicyEvaluationResult(
                is_allowed=False,
                policy_checks=checks,
                approved_action=ActionType.DO_NOT_CONTACT,
                override_reason="Customer opted out of notifications.",
                requires_human_approval=False,
            )
        else:
            checks.append(
                PolicyCheckItem(
                    rule_name="OPT_OUT_GUARD",
                    passed=True,
                    detail="Customer consent is active.",
                )
            )

        # Rule 3: Customer Fatigue / Contact Rate Limiting (48h sliding window)
        if proposed_action.action in [ActionType.PAYMENT_LINK, ActionType.METHOD_SWITCH]:
            window_count = self.contacts_in_window(customer)
            tokens_left = min(
                customer.contact_token_bucket,
                self.MAX_CONTACTS_PER_WINDOW - window_count,
            )
            if customer.contact_token_bucket <= 0 or window_count >= self.MAX_CONTACTS_PER_WINDOW:
                checks.append(
                    PolicyCheckItem(
                        rule_name="FATIGUE_TOKEN_BUDGET",
                        passed=False,
                        detail=(
                            f"Customer communication budget exhausted "
                            f"({window_count} pings in last {self.MAX_CONTACTS_WINDOW_HOURS}h, "
                            f"max {self.MAX_CONTACTS_PER_WINDOW})."
                        ),
                    )
                )
                approved_action = ActionType.WAIT
                override_reason = "Customer contact budget exhausted. Switched to delayed auto-retry."
            else:
                checks.append(
                    PolicyCheckItem(
                        rule_name="FATIGUE_TOKEN_BUDGET",
                        passed=True,
                        detail=f"Tokens remaining: {tokens_left}; contacts in 48h window: {window_count}.",
                    )
                )

        # Rule 4: High Value Financial Guardrail (Human in the loop)
        if payment.amount_in_paise >= self.HIGH_VALUE_THRESHOLD_PAISE:
            if proposed_action.confidence_score < 0.85:
                checks.append(
                    PolicyCheckItem(
                        rule_name="HIGH_VALUE_SAFETY_GATE",
                        passed=False,
                        detail=f"High-value invoice (₹{payment.amount_in_paise / 100:,.2f}) with confidence {proposed_action.confidence_score:.2f} < 0.85 requires human authorization.",
                    )
                )
                approved_action = ActionType.HUMAN_ESCALATION
                requires_human = True
                override_reason = "High-value invoice requires Human Ops sign-off."
            else:
                checks.append(
                    PolicyCheckItem(
                        rule_name="HIGH_VALUE_SAFETY_GATE",
                        passed=True,
                        detail=f"High-value invoice satisfied high confidence threshold ({proposed_action.confidence_score:.2f} >= 0.85).",
                    )
                )

        # Rule 5: Terminal Failure Mode Check
        if payment.failure_code in [FailureCode.CARD_BLOCKED, FailureCode.ACCOUNT_FROZEN, FailureCode.FRAUD_SUSPECTED]:
            if proposed_action.action == ActionType.SMART_RETRY:
                checks.append(
                    PolicyCheckItem(
                        rule_name="TERMINAL_FAILURE_CHECK",
                        passed=False,
                        detail=f"Cannot retry on terminal failure code {payment.failure_code}. Forcing alternative payment link.",
                    )
                )
                approved_action = ActionType.PAYMENT_LINK
                override_reason = "Auto-retry blocked on permanently invalid card/account."
            else:
                checks.append(
                    PolicyCheckItem(
                        rule_name="TERMINAL_FAILURE_CHECK",
                        passed=True,
                        detail="Action conforms to terminal failure handling.",
                    )
                )

        # Rule 6: Communication Copy Sanitization
        sanitized_copy = self.sanitize_untrusted_input(proposed_action.communication_copy)
        if sanitized_copy != proposed_action.communication_copy:
            checks.append(
                PolicyCheckItem(
                    rule_name="PROMPT_INJECTION_CLEANSED",
                    passed=True,
                    detail="Potentially malicious prompt injection detected and stripped from communication text.",
                )
            )

        return PolicyEvaluationResult(
            is_allowed=True,
            policy_checks=checks,
            approved_action=approved_action,
            override_reason=override_reason,
            requires_human_approval=requires_human,
            sanitized_copy=sanitized_copy,
        )

    def validate_offer_budget(self, amount_paise: int, discount_rupees: float, customer_tier: CustomerTier) -> bool:
        """
        Policy Rule: Max Offer Budget Guard.
        Dynamic micro-discounts are capped at 5% of invoice value and max ₹500.
        """
        amount_rupees = amount_paise / 100.0
        if discount_rupees <= 0:
            return True
        max_allowed = min(500.0, amount_rupees * 0.05)
        return discount_rupees <= max_allowed + 0.01


# Global singleton instance
policy_engine = PolicyEngine()
