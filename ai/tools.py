from typing import Any, Dict, List
from pydantic import BaseModel, Field
from domain.models.enums import ActionType, FailureCode, PaymentMethod


class ToolDefinition(BaseModel):
    name: str
    description: str
    parameters: Dict[str, Any]


REVIVE_ALLOWED_TOOLS: List[ToolDefinition] = [
    ToolDefinition(
        name="get_payment_context",
        description="Retrieves the verified payment entity, failure code, amount, and payment method.",
        parameters={
            "type": "object",
            "properties": {"payment_id": {"type": "string", "description": "The Razorpay payment ID"}},
            "required": ["payment_id"],
        },
    ),
    ToolDefinition(
        name="get_bank_health_status",
        description="Retrieves the live health and stability score (0.0 to 1.0) of the acquiring bank or UPI gateway.",
        parameters={
            "type": "object",
            "properties": {"entity_key": {"type": "string", "description": "Bank/gateway key e.g. HDFC, SBI, RAZORPAY_UPI"}},
            "required": ["entity_key"],
        },
    ),
    ToolDefinition(
        name="calculate_expected_recovery_value",
        description="Computes the expected recovered value in paise: P(recovery) * Amount - Intervention Cost - Fatigue Penalty.",
        parameters={
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": [a.value for a in ActionType]},
                "amount_in_paise": {"type": "integer"},
                "confidence": {"type": "number"},
                "channel_cost_paise": {"type": "integer", "default": 200},
            },
            "required": ["action", "amount_in_paise", "confidence"],
        },
    ),
    ToolDefinition(
        name="propose_action_plan",
        description="Submits the candidate recovery plan with ranking and explanation to the Policy Engine.",
        parameters={
            "type": "object",
            "properties": {
                "primary_action": {"type": "string", "enum": [a.value for a in ActionType]},
                "confidence_score": {"type": "number"},
                "delay_seconds": {"type": "integer"},
                "channel": {"type": "string"},
                "rationale": {"type": "string"},
            },
            "required": ["primary_action", "confidence_score", "delay_seconds", "rationale"],
        },
    ),
]
