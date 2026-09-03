from datetime import datetime, timedelta

from domain.models.enums import ActionType, CustomerTier, FailureCode, PaymentMethod, PaymentStatus
from domain.models.schemas import CandidateAction, CustomerSchema, PaymentSchema
from domain.policies.engine import policy_engine


def _payment():
    return PaymentSchema(
        id="pay_fatigue",
        customer_id="cust_fatigue",
        amount_in_paise=150000,
        status=PaymentStatus.FAILED,
        method=PaymentMethod.CARD,
        failure_code=FailureCode.INSUFFICIENT_FUNDS,
        created_at=datetime.utcnow(),
    )


def _link():
    return CandidateAction(
        action=ActionType.PAYMENT_LINK,
        confidence_score=0.8,
        expected_value_in_paise=100000,
        delay_seconds=0,
        rationale="Send link",
    )


def test_fatigue_window_blocks_third_ping_in_48h():
    now = datetime.utcnow()
    customer = CustomerSchema(
        id="cust_fatigue",
        name="Riya",
        email="riya@example.com",
        tier=CustomerTier.STANDARD,
        contact_token_bucket=2,
        contact_timestamps=[now - timedelta(hours=2), now - timedelta(hours=1)],
    )
    result = policy_engine.evaluate(_payment(), customer, _link())
    assert result.approved_action == ActionType.WAIT
    assert any(c.rule_name == "FATIGUE_TOKEN_BUDGET" and not c.passed for c in result.policy_checks)


def test_fatigue_window_ignores_contacts_older_than_48h():
    now = datetime.utcnow()
    customer = CustomerSchema(
        id="cust_fatigue",
        name="Riya",
        email="riya@example.com",
        tier=CustomerTier.STANDARD,
        contact_token_bucket=2,
        contact_timestamps=[now - timedelta(hours=50)],
    )
    result = policy_engine.evaluate(_payment(), customer, _link())
    assert result.approved_action == ActionType.PAYMENT_LINK
    assert any(c.rule_name == "FATIGUE_TOKEN_BUDGET" and c.passed for c in result.policy_checks)
