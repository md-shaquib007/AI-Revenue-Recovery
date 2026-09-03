import json
from typing import Optional

import httpx

from apps.api.logging import log_event
from apps.api.settings import get_settings
from domain.models.enums import ActionType, AgentMode
from domain.models.schemas import AIDecisionProposal, CandidateAction, CustomerSchema, PaymentSchema
from ai.prompts import RECOVERY_DIAGNOSIS_PROMPT_TEMPLATE, REVIVE_SYSTEM_PROMPT


async def try_llm_proposal(
    payment: PaymentSchema,
    customer: CustomerSchema,
    bank_key: str,
    bank_health: float,
) -> Optional[AIDecisionProposal]:
    """Optional LLM proposal via LiteLLM / OpenAI API. Returns None on failure or missing config."""
    settings = get_settings()
    if not settings.openai_api_key and not settings.openai_base_url:
        return None

    prompt = RECOVERY_DIAGNOSIS_PROMPT_TEMPLATE.format(
        payment_id=payment.id,
        amount_in_rupees=payment.amount_in_paise / 100,
        amount_in_paise=payment.amount_in_paise,
        method=payment.method.value if payment.method else "unknown",
        failure_code=payment.failure_code.value if payment.failure_code else "UNKNOWN",
        failure_description=payment.failure_description or "",
        bank_key=bank_key,
        bank_health_score=bank_health,
        customer_id=customer.id,
        customer_tier=customer.tier.value,
        lifetime_recovered_rupees=customer.lifetime_recovered_paise / 100,
        tokens_remaining=customer.contact_token_bucket,
        opted_out=customer.opted_out,
    )
    payload = {
        "model": settings.openai_model,
        "temperature": 0.1,
        "max_tokens": 180,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": REVIVE_SYSTEM_PROMPT},
            {"role": "user", "content": prompt + "\nReturn JSON with keys: failure_category, is_transient, primary_action, confidence_score, delay_seconds, channel, rationale, communication_copy, operator_explanation."},
        ],
    }
    api_key = settings.openai_api_key or "sk-litellm-proxy"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    try:
        async with httpx.AsyncClient(timeout=4.0) as client:
            resp = await client.post(settings.llm_endpoint_url, json=payload, headers=headers)
            resp.raise_for_status()
            body = resp.json()
        content = body["choices"][0]["message"]["content"]
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()
        data = json.loads(content.strip())
        usage = body.get("usage") or {}
        tokens = int(usage.get("total_tokens") or 0)
        action = ActionType(data.get("primary_action", "WAIT"))
        conf = float(data.get("confidence_score", 0.5))
        primary = CandidateAction(
            action=action,
            confidence_score=max(0.0, min(1.0, conf)),
            expected_value_in_paise=max(0, int(conf * payment.amount_in_paise)),
            delay_seconds=int(data.get("delay_seconds") or 0),
            channel=data.get("channel") or "silent_api",
            communication_copy=data.get("communication_copy"),
            rationale=data.get("rationale") or "LLM proposal",
        )
        return AIDecisionProposal(
            failure_category=str(data.get("failure_category") or "LLM_DIAGNOSIS"),
            is_transient=bool(data.get("is_transient", True)),
            recommended_actions=[primary],
            primary_action=primary,
            operator_explanation=str(data.get("operator_explanation") or primary.rationale),
            agent_mode=AgentMode.AI_REASONER,
            tokens_used=tokens,
        )
    except Exception as exc:
        log_event("warning", "llm_proposal_failed", error=str(exc))
        return None
