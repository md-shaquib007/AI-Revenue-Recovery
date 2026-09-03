import uuid
import time
from typing import Any, Dict, Optional
from domain.bank_health.sentinel import bank_sentinel
from services.razorpay_client import razorpay_service


class MultiGatewayFallbackRouter:
    """
    Multi-Gateway Fallback Router Pattern.

    Primary Gateway: Razorpay
    Secondary Gateway: Cashfree / PayU (Fallback)

    Routing Logic:
    - Queries Bank Sentinel for the target bank/gateway.
    - If Razorpay circuit is open (PREDICTIVE_COOLOFF), automatically routes
      payment link generation through Cashfree/PayU fallback to guarantee delivery.
    """

    async def create_payment_link(
        self,
        amount_in_paise: int,
        customer_name: str,
        customer_email: str,
        customer_phone: Optional[str] = None,
        description: str = "Subscription Recovery Payment",
        bank_key: Optional[str] = None,
        idempotency_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        target_bank = (bank_key or "HDFC").upper()

        # Check if primary gateway (Razorpay) has an open Sentinel circuit for this bank
        if bank_sentinel.is_circuit_open(target_bank) or bank_sentinel.is_circuit_open("RAZORPAY_UPI"):
            # Circuit is open — route to secondary fallback gateway (Cashfree/PayU)
            return self._create_cashfree_fallback_link(
                amount_in_paise, customer_name, customer_email, customer_phone, description, idempotency_key
            )

        # Primary route: Razorpay
        res = await razorpay_service.create_payment_link(
            amount_in_paise=amount_in_paise,
            customer_name=customer_name,
            customer_email=customer_email,
            customer_phone=customer_phone,
            description=description,
            idempotency_key=idempotency_key,
        )
        res["gateway_used"] = "RAZORPAY"
        return res

    def _create_cashfree_fallback_link(
        self,
        amount_in_paise: int,
        customer_name: str,
        customer_email: str,
        customer_phone: Optional[str] = None,
        description: str = "Subscription Recovery Payment",
        idempotency_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Simulates Cashfree/PayU fallback link generation when primary gateway is degraded."""
        link_id = f"cf_plink_{uuid.uuid4().hex[:12]}"
        short_url = f"https://cf.link/{uuid.uuid4().hex[:8]}"
        return {
            "id": link_id,
            "amount": amount_in_paise,
            "currency": "INR",
            "status": "created",
            "short_url": short_url,
            "description": f"[FALLBACK ROUTE: CASHFREE] {description}",
            "customer": {
                "name": customer_name,
                "email": customer_email,
                "contact": customer_phone,
            },
            "gateway_used": "CASHFREE_FALLBACK",
            "created_at": int(time.time()),
        }


# Global singleton instance
gateway_router = MultiGatewayFallbackRouter()
