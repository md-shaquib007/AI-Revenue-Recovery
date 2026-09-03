from datetime import datetime

from ai.oracle import (
    case_matches_spec,
    circadian_multiplier,
    is_quiet_hours,
    parse_copilot_query,
    seconds_until_send_window,
    simulate_twin,
    to_ist,
)
from domain.models.enums import CustomerTier, FailureCode, PaymentMethod, PaymentStatus, RecoveryState
from domain.models.schemas import CustomerSchema, PaymentSchema
from domain.state_machine.recovery_fsm import RecoveryStateMachine


def _customer(**kwargs):
    base = dict(
        id="cust_1",
        name="Ananya Sharma",
        email="ananya@example.com",
        phone="+919876543210",
        tier=CustomerTier.STANDARD,
        contact_token_bucket=2,
        opted_out=False,
    )
    base.update(kwargs)
    return CustomerSchema(**base)


def _payment(**kwargs):
    base = dict(
        id="pay_1",
        order_id="order_1",
        customer_id="cust_1",
        amount_in_paise=150000,
        status=PaymentStatus.FAILED,
        method=PaymentMethod.CARD,
        failure_code=FailureCode.INSUFFICIENT_FUNDS,
        created_at=datetime(2026, 8, 22, 6, 0, 0),
    )
    base.update(kwargs)
    return PaymentSchema(**base)


def test_ist_offset_and_quiet_hours():
    midnight_ist = datetime(2026, 8, 21, 18, 30, 0)
    assert to_ist(midnight_ist).hour == 0
    assert is_quiet_hours(midnight_ist) is True
    assert seconds_until_send_window(midnight_ist) == 10 * 3600

    ten_ist = datetime(2026, 8, 22, 4, 30, 0)
    assert to_ist(ten_ist).hour == 10
    assert is_quiet_hours(ten_ist) is False
    assert seconds_until_send_window(ten_ist) == 0
    assert circadian_multiplier(datetime(2026, 8, 21, 14, 30, 0)) == 1.0  # 20:00 IST peak


def test_twin_ranks_contact_above_wait_for_nsf():
    twin = simulate_twin(_payment(), _customer(), bank_health=0.98, now=datetime(2026, 8, 22, 14, 30, 0))
    assert twin["winner"]["action"] in ("PAYMENT_LINK", "METHOD_SWITCH")
    assert twin["lift_vs_wait_rupees"] >= 0
    actions = {s["action"] for s in twin["strategies"]}
    assert "WAIT" in actions and "SMART_RETRY" in actions


def test_opt_out_blocks_contact_in_twin():
    twin = simulate_twin(
        _payment(),
        _customer(opted_out=True),
        bank_health=0.98,
        now=datetime(2026, 8, 22, 14, 30, 0),
    )
    contact = [s for s in twin["strategies"] if s["action"] in ("PAYMENT_LINK", "METHOD_SWITCH")]
    assert all(not s["policy_allowed"] for s in contact)


def test_fraud_twin_does_not_prefer_retry():
    twin = simulate_twin(
        _payment(failure_code=FailureCode.FRAUD_SUSPECTED),
        _customer(),
        bank_health=0.99,
        now=datetime(2026, 8, 22, 14, 30, 0),
    )
    assert twin["winner"]["action"] != "SMART_RETRY"


def test_copilot_parser_high_value_and_3ds():
    spec = parse_copilot_query("show stuck high-value 3DS cases")
    assert spec["active_only"] is True
    assert spec["high_value"] is True
    assert spec["failure"] == FailureCode.BAD_REQUEST_AUTHENTICATION_FAILED.value
    assert case_matches_spec(
        {
            "state": "IN_GRACE_WINDOW",
            "amount_in_rupees": 75000,
            "failure_code": FailureCode.BAD_REQUEST_AUTHENTICATION_FAILED.value,
            "customer": {"tier": "STANDARD", "tokens_remaining": 2},
        },
        spec,
    )
    assert not case_matches_spec(
        {
            "state": "RECOVERED",
            "amount_in_rupees": 75000,
            "failure_code": FailureCode.BAD_REQUEST_AUTHENTICATION_FAILED.value,
            "customer": {"tier": "STANDARD", "tokens_remaining": 2},
        },
        spec,
    )


def test_link_sent_can_reschedule():
    assert RecoveryStateMachine.can_transition(RecoveryState.LINK_SENT, RecoveryState.SCHEDULED_RETRY)
    assert RecoveryStateMachine.can_transition(RecoveryState.LINK_SENT, RecoveryState.LINK_SENT)
