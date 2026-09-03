import pytest
from services.mock_razorpay import mock_razorpay
from services.razorpay_client import razorpay_service


@pytest.mark.asyncio
async def test_mock_charge_subscription():
    res = mock_razorpay.charge_subscription("sub_test_12345", 50000)
    assert res["subscription_id"] == "sub_test_12345"
    assert res["amount"] == 50000
    assert res["status"] == "charged"


@pytest.mark.asyncio
async def test_razorpay_service_charge_subscription():
    res = await razorpay_service.charge_subscription(
        subscription_id="sub_test_67890",
        amount_in_paise=150000,
        idempotency_key="idem_sub_test_001",
    )
    assert res["subscription_id"] == "sub_test_67890"
    assert res["amount"] == 150000

    # Test idempotency (same key returns identical response)
    res2 = await razorpay_service.charge_subscription(
        subscription_id="sub_test_67890",
        amount_in_paise=150000,
        idempotency_key="idem_sub_test_001",
    )
    assert res2 == res
