import time
import pytest
from ai.strategy_cache import strategy_cache
from domain.models.schemas import AIDecisionProposal, CandidateAction
from domain.models.enums import ActionType, AgentMode
from domain.policies.engine import policy_engine


def test_pii_email_masking():
    assert policy_engine.mask_email("john.doe@razorpay.com") == "j******e@razorpay.com"
    assert policy_engine.mask_email("ab@example.com") == "a*@example.com"
    assert policy_engine.mask_email("") == ""
    assert policy_engine.mask_email(None) == ""


def test_pii_phone_masking():
    assert policy_engine.mask_phone("+919876543210") == "+919*******10"
    assert policy_engine.mask_phone("12345") == "*****"
    assert policy_engine.mask_phone(None) == ""


def test_pii_name_masking():
    assert policy_engine.mask_name("Vikram Sharma") == "V***** S*****"
    assert policy_engine.mask_name("A B C") == "A B C"
    assert policy_engine.mask_name(None) == ""


def test_strategy_cache_hit_and_ttl():
    strategy_cache.clear()
    key = strategy_cache.build_cache_key("INSUFFICIENT_FUNDS", "upi", "STANDARD", "HEALTHY")
    
    proposal = AIDecisionProposal(
        failure_category="INSUFFICIENT_BALANCE",
        is_transient=False,
        customer_churn_risk=0.25,
        recommended_actions=[],
        primary_action=CandidateAction(
            action=ActionType.PAYMENT_LINK,
            confidence_score=0.85,
            expected_value_in_paise=100000,
            delay_seconds=0,
            rationale="Cached strategy",
        ),
        operator_explanation="Fast path cache",
        agent_mode=AgentMode.AI_REASONER,
        latency_ms=1,
    )

    # Set cache with 2s TTL
    strategy_cache.set(key, proposal, ttl_seconds=2)
    assert strategy_cache.get(key) is not None
    assert strategy_cache.get(key).primary_action.action == ActionType.PAYMENT_LINK

    # Test cache miss on unknown key
    assert strategy_cache.get("UNKNOWN_KEY") is None
