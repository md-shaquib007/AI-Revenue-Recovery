import uuid
from typing import Any, Dict, Optional
from domain.models.schemas import CustomerSchema, PaymentSchema


class VoiceAIAgentService:
    """
    Futuristic Conversational Voice AI Debt Concierge.
    Generates ultra-low latency, empathetic Hindi/English voice call dialogues
    and negotiates dynamic partial payment splits within strict policy engine limits.
    """

    SCRIPTS = {
        "hinglish": {
            "greeting": "Namaste {name} ji, main REVIVE AI concierge bol raha hoon from {merchant_name}.",
            "issue_framing": "Aapka subscription payment of ₹{amount:,.0f} complete nahi ho paya tha.",
            "empathy_nudge": "Hum samajhte hain salary ya cash flow ki wajah se delay ho sakta hai.",
            "negotiation_pitch": "Kya aap abhi ₹{partial_amount:,.0f} deduct karwana chahenge taaki service chalti rahe, aur baaki ₹{balance_amount:,.0f} aapke salary date par?",
            "confirmation": "Bahut badhiya! Maine aapke WhatsApp par 1-click UPI link bhej diya hai. Aap wahan se tap karke complete kar sakte hain.",
        },
        "english": {
            "greeting": "Hello {name}, this is the REVIVE payment concierge calling from {merchant_name}.",
            "issue_framing": "We noticed an issue with your recent payment of ₹{amount:,.0f}.",
            "empathy_nudge": "We completely understand that billing delays happen due to bank timing or payroll cycles.",
            "negotiation_pitch": "Would you like to settle just ₹{partial_amount:,.0f} today to keep your account active, and clear the remaining ₹{balance_amount:,.0f} on your salary day?",
            "confirmation": "Wonderful! We've dispatched a secure 1-click UPI payment link to your WhatsApp. Thank you!",
        },
    }

    @classmethod
    def generate_call_simulation(
        cls,
        customer: CustomerSchema,
        payment: PaymentSchema,
        language: str = "hinglish",
        merchant_name: str = "PrimeTech Enterprise",
    ) -> Dict[str, Any]:
        lang_key = language.lower() if language.lower() in cls.SCRIPTS else "hinglish"
        script_template = cls.SCRIPTS[lang_key]

        total_amount = payment.amount_in_paise / 100.0
        partial_slice = round(total_amount * 0.33, 2)
        balance_due = round(total_amount - partial_slice, 2)

        name = customer.name.split()[0] if customer.name else "Customer"

        dialogue_turns = [
            {"speaker": "AI_AGENT", "text": script_template["greeting"].format(name=name, merchant_name=merchant_name)},
            {"speaker": "AI_AGENT", "text": script_template["issue_framing"].format(amount=total_amount)},
            {"speaker": "CUSTOMER", "text": "Haan actually account mein thoda issue tha, salary abhi aayi nahi hai." if lang_key == "hinglish" else "Yes, I was waiting on my client payment to clear."},
            {"speaker": "AI_AGENT", "text": script_template["empathy_nudge"]},
            {"speaker": "AI_AGENT", "text": script_template["negotiation_pitch"].format(partial_amount=partial_slice, balance_amount=balance_due)},
            {"speaker": "CUSTOMER", "text": "Haan yeh theek hai, link bhej do." if lang_key == "hinglish" else "That sounds great, please send the link."},
            {"speaker": "AI_AGENT", "text": script_template["confirmation"]},
        ]

        call_id = f"vcall_{uuid.uuid4().hex[:10]}"
        return {
            "call_id": call_id,
            "status": "COMPLETED_AGREED",
            "language": lang_key,
            "customer_phone": customer.phone or "+919876543210",
            "customer_name": customer.name,
            "sentiment_score": 0.88,  # Highly positive resolution sentiment
            "agreed_action": "PARTIAL_WATERFALL_SPLIT",
            "agreed_partial_rupees": partial_slice,
            "remaining_balance_rupees": balance_due,
            "whatsapp_link_dispatched": f"https://rzp.io/i/{uuid.uuid4().hex[:8]}",
            "full_dialogue": dialogue_turns,
        }


voice_agent_service = VoiceAIAgentService()
