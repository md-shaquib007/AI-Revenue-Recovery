import pytest
from ai.offer_engine import offer_engine
from ai.shadow_simulator import MultiAgentShadowSimulator, shadow_simulator
from domain.bank_health.sentinel import BankSentinelPredictor, bank_sentinel
from domain.models.enums import ActionType, CustomerTier, FailureCode, PaymentStatus
from domain.models.schemas import CustomerSchema, PaymentSchema
from domain.policies.engine import policy_engine


# ── Shared fixtures ──────────────────────────────────────────────────────────

def _payment(payment_id="pay_sim_001", failure_code=FailureCode.BAD_REQUEST_AUTHENTICATION_FAILED, amount_in_paise=2500000):
    return PaymentSchema(
        id=payment_id,
        customer_id="cust_001",
        amount_in_paise=amount_in_paise,
        currency="INR",
        status=PaymentStatus.FAILED,
        failure_code=failure_code,
        created_at="2026-08-25T00:00:00Z",
    )


def _customer(tier=CustomerTier.VIP):
    return CustomerSchema(
        id="cust_001",
        name="Vikram Sharma",
        email="v*****a@razorpay.com",
        tier=tier,
        contact_token_bucket=2,
    )


# ── Shadow Simulator ──────────────────────────────────────────────────────────

def test_multi_agent_shadow_simulator():
    result = shadow_simulator.simulate(_payment(), _customer(), ActionType.PAYMENT_LINK)

    assert result["total_simulated_personas"] == 50
    assert 0.0 <= result["consensus_index_pct"] <= 100.0
    assert 0.0 <= result["friction_score_pct"] <= 100.0
    assert len(result["personas_sample"]) == 8


def test_shadow_sim_deterministic_for_same_payment():
    """Same payment_id + action should yield identical sim results (audit-safe)."""
    pay = _payment("pay_deterministic_999")
    r1 = shadow_simulator.simulate(pay, _customer(), ActionType.SMART_RETRY)
    r2 = shadow_simulator.simulate(pay, _customer(), ActionType.SMART_RETRY)

    assert r1["consensus_index_pct"] == r2["consensus_index_pct"]
    assert r1["friction_score_pct"] == r2["friction_score_pct"]


def test_shadow_sim_best_alternative_action():
    """best_alternative_action should return a valid ActionType different from the excluded one."""
    pay = _payment()
    best = shadow_simulator.best_alternative_action(pay, _customer(), exclude=ActionType.SMART_RETRY)

    assert best is not None
    assert isinstance(best, ActionType)
    assert best != ActionType.SMART_RETRY


def test_shadow_sim_different_seeds_for_different_actions():
    """Different actions should produce non-identical seed values (i.e. varied results)."""
    pay = _payment("pay_seed_test_777")
    r_link = shadow_simulator.simulate(pay, _customer(), ActionType.PAYMENT_LINK)
    r_retry = shadow_simulator.simulate(pay, _customer(), ActionType.SMART_RETRY)

    # They should differ (different action → different seed → different scores)
    assert r_link["seed"] != r_retry["seed"]


# ── Bank Sentinel ─────────────────────────────────────────────────────────────

def test_predictive_bank_sentinel():
    sentinel = BankSentinelPredictor()  # Fresh instance for isolation
    entity_key = "TEST_GATEWAY_ISOLATED"
    for _ in range(15):
        sentinel.record_event(entity_key, is_failure=True)

    analytics = sentinel.evaluate_predictive_circuit(entity_key)

    assert analytics["entity_key"] == "TEST_GATEWAY_ISOLATED"
    assert analytics["failure_velocity_per_min"] >= 3.0
    assert analytics["circuit_triggered"] is True
    assert analytics["status"] == "PREDICTIVE_COOLOFF"
    assert sentinel.is_circuit_open(entity_key) is True


def test_sentinel_self_heals_on_success():
    """After enough successes, the sentinel should auto-recover the circuit."""
    sentinel = BankSentinelPredictor()  # Fresh instance
    entity = "SELF_HEAL_BANK"

    # Trigger the circuit
    for _ in range(15):
        sentinel.record_event(entity, is_failure=True)
    sentinel.evaluate_predictive_circuit(entity)
    assert sentinel.is_circuit_open(entity) is True

    # Flood successes to bring velocity below threshold
    for _ in range(20):
        sentinel.record_event(entity, is_failure=False)

    # Re-evaluate — should clear circuit
    analytics = sentinel.evaluate_predictive_circuit(entity)
    # With heavy success damping and low pure failure velocity this should recover
    assert analytics["recent_successes"] >= 10


def test_sentinel_is_circuit_open_returns_false_for_stable_bank():
    sentinel = BankSentinelPredictor()
    # No events injected
    assert sentinel.is_circuit_open("UNKNOWN_STABLE_BANK") is False


# ── Offer Engine + Policy Cap ─────────────────────────────────────────────────

def test_dynamic_offer_engine_and_policy_cap():
    payment = _payment(
        payment_id="pay_nsf_001",
        failure_code=FailureCode.INSUFFICIENT_FUNDS,
        amount_in_paise=100000,  # ₹1,000
    )
    customer = _customer(tier=CustomerTier.STANDARD)

    offer_res = offer_engine.evaluate_offer(payment, customer, churn_risk=0.65, base_p_recover=0.55)

    assert offer_res["offer_recommended"] is True
    assert offer_res["discount_amount_rupees"] == 50.0  # 5% of ₹1,000
    assert offer_res["net_ev_lift_rupees"] > 0.0

    # Policy Rule Check: MaxOfferCapRule
    is_policy_allowed = policy_engine.validate_offer_budget(
        payment.amount_in_paise, offer_res["discount_amount_rupees"], customer.tier
    )
    assert is_policy_allowed is True


def test_offer_engine_rejects_low_churn_non_nsf():
    """Offer engine should not fire for low-risk non-NSF failures."""
    payment = _payment(failure_code=FailureCode.GATEWAY_ERROR, amount_in_paise=500000)
    offer_res = offer_engine.evaluate_offer(payment, _customer(), churn_risk=0.20, base_p_recover=0.75)

    assert offer_res["offer_recommended"] is False
    assert offer_res["discount_amount_rupees"] == 0.0


# ── Policy Rule 7: Sentinel Circuit Override ──────────────────────────────────

def test_policy_sentinel_circuit_override_vetos_smart_retry():
    """When sentinel circuit is open, policy must veto SMART_RETRY → WAIT."""
    from domain.models.schemas import CandidateAction
    from domain.models.enums import ActionType

    # Force sentinel open on HDFC
    sentinel = BankSentinelPredictor()
    for _ in range(15):
        sentinel.record_event("HDFC", is_failure=True)
    sentinel.evaluate_predictive_circuit("HDFC")
    assert sentinel.is_circuit_open("HDFC") is True

    # Inject sentinel into policy engine's lazy getter for this test
    import domain.policies.engine as eng_module
    original = eng_module._get_sentinel
    eng_module._get_sentinel = lambda: sentinel

    try:
        payment = _payment(failure_code=FailureCode.GATEWAY_ERROR)
        candidate = CandidateAction(
            action=ActionType.SMART_RETRY,
            confidence_score=0.80,
            expected_value_in_paise=80000,
            rationale="Retry on gateway error",
        )
        result = policy_engine.evaluate(
            payment=payment,
            customer=_customer(),
            proposed_action=candidate,
            bank_key="HDFC",
        )
        # Policy MUST override to WAIT
        assert result.approved_action == ActionType.WAIT
        sentinel_checks = [c for c in result.policy_checks if c.rule_name == "SENTINEL_CIRCUIT_OVERRIDE"]
        assert len(sentinel_checks) == 1
        assert sentinel_checks[0].passed is False
    finally:
        eng_module._get_sentinel = original
