from typing import Any, Dict, Optional
from domain.models.enums import CustomerTier, FailureCode
from domain.models.schemas import CustomerSchema, PaymentSchema


class DynamicOfferEngine:
    """
    Autonomous Dynamic Micro-Incentive Offer Engine.
    For high churn-risk NSF (insufficient balance) payments, evaluates whether
    attaching a 1-click recovery micro-discount (e.g., ₹50 or 5% cashback)
    yields a positive Net Expected Value (EV_offer > EV_standard).
    """

    def evaluate_offer(
        self,
        payment: PaymentSchema,
        customer: CustomerSchema,
        churn_risk: float,
        base_p_recover: float,
    ) -> Dict[str, Any]:
        amount_rupees = payment.amount_in_paise / 100.0

        # Only evaluate offer if failure is NSF/balance or customer churn risk > 50%
        if payment.failure_code not in (FailureCode.INSUFFICIENT_FUNDS, FailureCode.BAD_REQUEST_PAYMENT_TIMED_OUT) and churn_risk < 0.5:
            return {
                "offer_recommended": False,
                "reason": "Standard recovery strategy sufficient (Low churn risk / Non-balance failure)",
                "discount_amount_rupees": 0.0,
                "net_ev_lift_rupees": 0.0,
            }

        # Calculate proposed dynamic discount (5% of invoice capped at max ₹250 for high tier, ₹100 standard)
        cap = 250.0 if customer.tier in (CustomerTier.VIP, CustomerTier.ENTERPRISE) else 100.0
        proposed_discount_rupees = min(cap, round(amount_rupees * 0.05, 2))

        # Expected Value Theorem:
        # Standard EV = (P_base * InvoiceAmount) - ChurnPenalty
        # Offer EV    = (P_boosted * (InvoiceAmount - Discount)) - ChannelCost
        p_boosted = min(0.92, base_p_recover + 0.22)  # Offer boosts immediate payment intent

        standard_ev = (base_p_recover * amount_rupees) - (churn_risk * amount_rupees * 0.35)
        offer_ev = (p_boosted * (amount_rupees - proposed_discount_rupees)) - 1.50

        net_ev_lift = round(offer_ev - standard_ev, 2)
        offer_recommended = net_ev_lift > 5.0 and proposed_discount_rupees >= 10.0

        return {
            "offer_recommended": offer_recommended,
            "discount_amount_rupees": proposed_discount_rupees if offer_recommended else 0.0,
            "discount_pct": 5.0 if offer_recommended else 0.0,
            "boosted_p_recover": round(p_boosted, 3) if offer_recommended else base_p_recover,
            "net_ev_lift_rupees": net_ev_lift,
            "standard_ev_rupees": round(standard_ev, 2),
            "offer_ev_rupees": round(offer_ev, 2),
            "copy_headline": f"Special Offer: Pay now & save ₹{int(proposed_discount_rupees)}" if offer_recommended else None,
        }


# Global singleton instance
offer_engine = DynamicOfferEngine()
