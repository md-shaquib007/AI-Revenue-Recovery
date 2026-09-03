from domain.bank_health.matrix import BankHealthMatrix
from domain.models.enums import FailureCode, PaymentMethod


def test_bank_health_baseline():
    matrix = BankHealthMatrix()
    assert matrix.get_health_score("HDFC") >= 0.95
    assert matrix.get_health_score("SBI") >= 0.90


def test_bank_downtime_injection_and_recovery():
    matrix = BankHealthMatrix()
    matrix.inject_downtime("HDFC", duration_minutes=10, degraded_score=0.25)
    assert matrix.get_health_score("HDFC") == 0.25

    # Test delay calculation during downtime
    delay = matrix.calculate_smart_delay(FailureCode.GATEWAY_ERROR, PaymentMethod.UPI, bank_name="HDFC")
    assert delay == 1800  # 30 min cooloff during severe outage

    # Recovery
    matrix.recover_entity("HDFC")
    assert matrix.get_health_score("HDFC") == 1.0


def test_smart_delay_for_3ds_dropout():
    matrix = BankHealthMatrix()
    delay = matrix.calculate_smart_delay(FailureCode.BAD_REQUEST_AUTHENTICATION_FAILED, PaymentMethod.CARD)
    assert delay == 480  # 8 min grace window
