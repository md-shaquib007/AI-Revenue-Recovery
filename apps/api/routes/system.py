from fastapi import APIRouter

from ai.agent import ai_recovery_agent
from apps.api.settings import get_settings

router = APIRouter(tags=["System"])


@router.get("/system/status")
async def system_status():
    settings = get_settings()
    return {
        "service": settings.app_name,
        "version": settings.app_version,
        "app_env": settings.app_env,
        "auth_required": settings.require_auth,
        "chaos_enabled": settings.allow_chaos,
        "worker_enabled": settings.worker_enabled,
        "llm_configured": bool(settings.openai_api_key),
        "llm_outage_simulated": ai_recovery_agent._llm_outage_simulated,
        "axiom": "AI proposes. Policy decides. Systems execute.",
        "circadian_send": settings.use_circadian_send,
        "link_followup_seconds": settings.followup_seconds,
    }
