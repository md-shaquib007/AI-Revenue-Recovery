import pytest
from ai.agent import ai_recovery_agent
from ai.bandit import ContextualBanditEngine, contextual_bandit
from domain.models.enums import CustomerTier, FailureCode


def test_bandit_prior_initialization():
    engine = ContextualBanditEngine()
    alpha, beta = engine.get_priors(FailureCode.INSUFFICIENT_FUNDS, "HDFC", CustomerTier.STANDARD)
    # NSF initializes at B(2, 4) -> mean 2/6 = 0.333
    assert alpha == 2.0
    assert beta == 4.0
    mean_p = engine.predict_recovery_probability(FailureCode.INSUFFICIENT_FUNDS, "HDFC", CustomerTier.STANDARD)
    assert mean_p == 0.333


def test_bandit_outcome_learning():
    engine = ContextualBanditEngine()
    fc = FailureCode.INSUFFICIENT_FUNDS
    bank = "SBI"
    tier = CustomerTier.VIP

    initial_p = engine.predict_recovery_probability(fc, bank, tier)

    # Record 5 consecutive successes
    for _ in range(5):
        engine.record_outcome(fc, bank, tier, recovered=True)

    updated_p = engine.predict_recovery_probability(fc, bank, tier)
    assert updated_p > initial_p


def test_bandit_thompson_sample_bounds():
    engine = ContextualBanditEngine()
    sample_p = engine.predict_recovery_probability(
        FailureCode.GATEWAY_ERROR, "ICICI", CustomerTier.ENTERPRISE, sample=True
    )
    assert 0.05 <= sample_p <= 0.95


def test_agent_blends_bandit_p_into_ev():
    ev_raw = ai_recovery_agent.calculate_expected_value(
        amount_paise=100000,
        confidence=0.80,
        failure_code=FailureCode.GATEWAY_ERROR,
        bank_key="HDFC",
        customer_tier=CustomerTier.STANDARD,
    )
    assert ev_raw > 0


def test_bandit_recency_decay():
    engine = ContextualBanditEngine()
    fc = FailureCode.GATEWAY_ERROR
    bank = "AXIS"
    tier = CustomerTier.STANDARD

    # Record 10 failures during an outage
    for _ in range(10):
        engine.record_outcome(fc, bank, tier, recovered=False, decay_factor=1.0)
    low_p = engine.predict_recovery_probability(fc, bank, tier)

    # Now apply decay on subsequent updates as the outage resolves
    for _ in range(5):
        engine.record_outcome(fc, bank, tier, recovered=True, decay_factor=0.90)
    recovered_p = engine.predict_recovery_probability(fc, bank, tier)

    assert recovered_p > low_p
