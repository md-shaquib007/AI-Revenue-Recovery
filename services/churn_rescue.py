from datetime import datetime, timedelta
from typing import Any, Dict, Optional
from domain.models.schemas import CustomerSchema, PaymentSchema


class AutonomousChurnRescueEngine:
    """
    Futuristic Churn Rescue Engine:
    Stops involuntary subscription cancellations during customer financial hardship
    via Dynamic 14-Day Holiday Pauses and Micro-Tier Plan Downsells.
    """

    DOWNSELL_TIER_MAPPING = {
        "ENTERPRISE": {"downsell_plan": "PRO_BUSINESS", "original_price_in_rupees": 19999, "downsell_price_in_rupees": 4999, "discount_pct": 75},
        "VIP": {"downsell_plan": "STARTER_PRO", "original_price_in_rupees": 4999, "downsell_price_in_rupees": 1499, "discount_pct": 70},
        "STANDARD": {"downsell_plan": "ESSENTIAL_LITE", "original_price_in_rupees": 1999, "downsell_price_in_rupees": 499, "discount_pct": 75},
    }

    @classmethod
    def evaluate_rescue_strategy(
        cls,
        customer: CustomerSchema,
        payment: PaymentSchema,
        consecutive_failures: int = 2,
    ) -> Dict[str, Any]:
        tier = customer.tier.value if hasattr(customer.tier, "value") else str(customer.tier)
        amount_rupees = payment.amount_in_paise / 100.0
        
        downsell_info = cls.DOWNSELL_TIER_MAPPING.get(tier, cls.DOWNSELL_TIER_MAPPING["STANDARD"])
        pause_until = datetime.utcnow() + timedelta(days=14)

        # Estimate Preserved Lifetime Value (6 months at downsell price vs. $0 on cancellation)
        downsell_price = downsell_info["downsell_price_in_rupees"]
        preserved_ltv_rupees = downsell_price * 6.0

        should_offer_rescue = consecutive_failures >= 2 or amount_rupees >= 3000

        return {
            "rescue_recommended": should_offer_rescue,
            "consecutive_failures": consecutive_failures,
            "original_amount_rupees": amount_rupees,
            "strategies": {
                "smart_holiday_pause": {
                    "action": "PAUSE_SUBSCRIPTION_14_DAYS",
                    "resume_date": pause_until.strftime("%d %b %Y"),
                    "headline": "Need time? Take a 14-day holiday pause on us with zero data loss.",
                    "benefit": "Keep all your data & access active while you sort out your cash flow.",
                },
                "micro_tier_downsell": {
                    "action": "DOWNSELL_PLAN",
                    "target_plan": downsell_info["downsell_plan"],
                    "original_price_rupees": amount_rupees,
                    "discounted_price_rupees": downsell_price,
                    "discount_pct": downsell_info["discount_pct"],
                    "headline": f"Switch to {downsell_info['downsell_plan']} for just ₹{downsell_price}/mo (Save {downsell_info['discount_pct']}%)",
                    "benefit": "Retain core workspace features at a fraction of the cost.",
                },
            },
            "preserved_ltv_rupees": preserved_ltv_rupees,
            "recommended_action": "MICRO_TIER_DOWNSELL" if amount_rupees >= 4000 else "SMART_HOLIDAY_PAUSE",
        }


churn_rescue_engine = AutonomousChurnRescueEngine()
