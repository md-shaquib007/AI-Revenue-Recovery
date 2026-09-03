from typing import Any, Dict, Optional

from domain.models.enums import PaymentMethod


def infer_bank_key(payment_dict: Dict[str, Any], method: Optional[str] = None) -> str:
    """Resolve acquiring bank/gateway from Razorpay payload fields — never hardcode HDFC."""
    notes = payment_dict.get("notes") or {}
    if isinstance(notes, dict):
        for key in ("bank", "bank_key", "issuer"):
            value = notes.get(key)
            if value:
                return str(value).upper()

    acquirer = payment_dict.get("acquirer_data") or {}
    if isinstance(acquirer, dict):
        for key in ("bank", "authentication_reference_number", "rrn"):
            value = acquirer.get(key)
            if key == "bank" and value:
                return str(value).upper()

    bank = payment_dict.get("bank")
    if bank:
        return str(bank).upper()

    method_value = method or payment_dict.get("method") or ""
    if str(method_value).lower() == PaymentMethod.UPI.value:
        return "RAZORPAY_UPI"
    if str(method_value).lower() == PaymentMethod.CARD.value:
        return "RAZORPAY_CARDS"
    if str(method_value).lower() == PaymentMethod.NETBANKING.value:
        return "RAZORPAY_NETBANKING"
    return "RAZORPAY_UPI"
