import pytest
from ai.copy_rag import copy_rag
from domain.bank_health.sentinel import BankSentinelPredictor, bank_sentinel
from domain.models.enums import FailureCode
from services.gateway_adapter import MultiGatewayFallbackRouter
from services.redis_cache import redis_cache
from services.whatsapp_service import whatsapp_service


@pytest.mark.asyncio
async def test_redis_cache_adapter():
    await redis_cache.set("test_key_001", "revive_cached_val", ttl_seconds=60)
    val = await redis_cache.get("test_key_001")
    assert val == "revive_cached_val"

    await redis_cache.delete("test_key_001")
    assert await redis_cache.get("test_key_001") is None


@pytest.mark.asyncio
async def test_multi_gateway_fallback_router_primary():
    # Clear any previous test circuit state on global sentinel
    bank_sentinel._circuit_state.clear()

    router = MultiGatewayFallbackRouter()
    res = await router.create_payment_link(
        amount_in_paise=50000,
        customer_name="Test Customer",
        customer_email="test@example.com",
        bank_key="HDFC",
    )
    assert res["gateway_used"] == "RAZORPAY"
    assert res["amount"] == 50000


@pytest.mark.asyncio
async def test_multi_gateway_fallback_router_secondary_fallback():
    # Inject 15 failure events into sentinel for SBI to trigger circuit open
    for _ in range(15):
        bank_sentinel.record_event("SBI", is_failure=True)
    bank_sentinel.evaluate_predictive_circuit("SBI")

    router = MultiGatewayFallbackRouter()
    res = await router.create_payment_link(
        amount_in_paise=75000,
        customer_name="Fallback Customer",
        customer_email="fallback@example.com",
        bank_key="SBI",
    )
    # Circuit is open for SBI -> Gateway router falls back to Cashfree
    assert res["gateway_used"] == "CASHFREE_FALLBACK"
    assert "CASHFREE" in res["description"]


def test_whatsapp_service_upi_deep_link():
    link = whatsapp_service.generate_upi_deep_link(
        payee_vpa="merchant@razorpay",
        payee_name="Merchant",
        amount_in_rupees=250.0,
        transaction_ref="tx_test_123",
    )
    assert link.startswith("upi://pay?")
    assert "pa=merchant%40razorpay" in link
    assert "am=250.00" in link

    payload = whatsapp_service.build_whatsapp_template_payload(
        customer_phone="+919876543210",
        customer_name="Vikram",
        amount_in_rupees=250.0,
        short_url="https://rzp.io/i/test",
        upi_deep_link=link,
    )
    assert payload["messaging_product"] == "whatsapp"
    assert payload["to"] == "+919876543210"


def test_semantic_copy_rag():
    match = copy_rag.retrieve_best_copy(FailureCode.INSUFFICIENT_FUNDS)
    assert match["copy_id"] == "copy_nsf_001"
    assert "save ₹50" in match["copy_headline"]
    assert match["similarity_score"] > 0.5
