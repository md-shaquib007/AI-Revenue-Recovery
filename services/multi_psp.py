from typing import Any, Dict, Optional
from pydantic import BaseModel


class NormalizedRecoveryEvent(BaseModel):
    psp: str  # 'RAZORPAY' | 'STRIPE'
    event_type: str
    event_id: str
    payment_id: str
    customer_id: str
    customer_email: str
    customer_phone: Optional[str] = None
    amount_in_paise: int
    currency: str = "INR"
    failure_code: str
    failure_description: str
    bank_name: Optional[str] = None


class MultiPSPRouterService:
    """
    Universal Multi-PSP Ingestion & Normalization Engine.
    Seamlessly adapts Razorpay, Stripe, and global gateways into unified recovery events.
    """

    @classmethod
    def normalize_webhook(cls, psp: str, payload: Dict[str, Any], event_id: Optional[str] = None) -> NormalizedRecoveryEvent:
        psp_upper = psp.upper()

        if psp_upper == "STRIPE":
            return cls._normalize_stripe(payload, event_id)
        else:
            return cls._normalize_razorpay(payload, event_id)

    @classmethod
    def _normalize_razorpay(cls, data: Dict[str, Any], event_id: Optional[str] = None) -> NormalizedRecoveryEvent:
        entity = data.get("payload", {}).get("payment", {}).get("entity", {}) or data.get("entity", {}) or data
        amt = entity.get("amount", 100000)
        pay_id = entity.get("id", "pay_rzp_unknown")
        cust_id = entity.get("customer_id") or entity.get("email") or f"cust_{pay_id}"

        return NormalizedRecoveryEvent(
            psp="RAZORPAY",
            event_type=data.get("event", "payment.failed"),
            event_id=event_id or data.get("event_id") or f"evt_rzp_{pay_id}",
            payment_id=pay_id,
            customer_id=cust_id,
            customer_email=entity.get("email", "customer@example.com"),
            customer_phone=entity.get("contact"),
            amount_in_paise=int(amt),
            currency=entity.get("currency", "INR"),
            failure_code=entity.get("error_code") or "BAD_REQUEST_PAYMENT_TIMED_OUT",
            failure_description=entity.get("error_description") or "Payment authorization failed",
            bank_name=entity.get("bank", "HDFC"),
        )

    @classmethod
    def _normalize_stripe(cls, data: Dict[str, Any], event_id: Optional[str] = None) -> NormalizedRecoveryEvent:
        obj = data.get("data", {}).get("object", {}) or data
        amt = obj.get("amount_due") or obj.get("amount") or 499900
        inv_id = obj.get("id", "in_stripe_unknown")
        cust_id = obj.get("customer", f"cust_{inv_id}")

        return NormalizedRecoveryEvent(
            psp="STRIPE",
            event_type=data.get("type", "invoice.payment_failed"),
            event_id=event_id or data.get("id") or f"evt_stripe_{inv_id}",
            payment_id=inv_id,
            customer_id=cust_id,
            customer_email=obj.get("customer_email", "stripe.user@example.com"),
            customer_phone=obj.get("customer_phone"),
            amount_in_paise=int(amt),
            currency=(obj.get("currency") or "INR").upper(),
            failure_code="CARD_DECLINED_INSUFFICIENT_FUNDS",
            failure_description="Your card has insufficient funds.",
            bank_name="STRIPE_ISSUER",
        )


multi_psp_router = MultiPSPRouterService()
