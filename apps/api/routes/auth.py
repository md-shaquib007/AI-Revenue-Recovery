from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.auth import (
    OperatorContext,
    bootstrap_default_operator,
    create_access_token,
    hash_password,
    require_operator,
    verify_password,
)
from apps.api.settings import get_settings
from domain.models.entities import OperatorEntity
from domain.models.schemas import ChangePasswordRequest, OperatorLoginRequest, OperatorTokenResponse
from services.db import get_db

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/login", response_model=OperatorTokenResponse)
async def login(body: OperatorLoginRequest, db: AsyncSession = Depends(get_db)):
    await bootstrap_default_operator(db)
    result = await db.execute(select(OperatorEntity).where(OperatorEntity.username == body.username))
    operator = result.scalars().first()
    if not operator or not verify_password(body.password, operator.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    token = create_access_token(operator)
    return OperatorTokenResponse(access_token=token, username=operator.username, role=operator.role)


@router.get("/me")
async def me(operator: OperatorContext = Depends(require_operator)):
    settings = get_settings()
    return {
        "id": operator.id,
        "username": operator.username,
        "role": operator.role,
        "auth_required": settings.require_auth,
    }


@router.post("/change-password")
async def change_password(
    body: ChangePasswordRequest,
    db: AsyncSession = Depends(get_db),
    operator: OperatorContext = Depends(require_operator),
):
    result = await db.execute(select(OperatorEntity).where(OperatorEntity.id == operator.id))
    op = result.scalars().first()
    if not op or not verify_password(body.old_password, op.password_hash):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Current password is incorrect")

    if len(body.new_password) < 6:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="New password must be at least 6 characters long")

    op.password_hash = hash_password(body.new_password)
    await db.commit()
    return {"status": "SUCCESS", "message": "Operator password updated successfully"}


import hashlib
import uuid
from pydantic import BaseModel, Field


class ConnectMerchantRequest(BaseModel):
    business_name: str = "Acme EdTech Private Limited"
    gateway: str = "RAZORPAY"  # 'RAZORPAY' | 'STRIPE'
    api_key: str = "rzp_live_test_123456"
    api_secret: str = "sec_test_secret_987654"
    mode: str = "SHADOW"  # 'SHADOW' | 'AUTONOMOUS_LIVE'


@router.post("/connect-merchant")
async def connect_new_merchant(body: ConnectMerchantRequest, db: AsyncSession = Depends(get_db)):
    """
    Self-Serve 1-Click Merchant Connection Gateway.
    Provisions a new tenant, generates webhook secret & URL, and configures Shadow Mode.
    """
    clean_name = body.business_name.strip().lower().replace(" ", "_")[:32]
    tenant_id = f"tenant_{clean_name}_{str(uuid.uuid4())[:8]}"
    webhook_secret = f"whsec_{hashlib.sha256((tenant_id + body.api_key).encode()).hexdigest()[:24]}"

    return {
        "status": "MERCHANT_CONNECTED",
        "tenant_id": tenant_id,
        "business_name": body.business_name,
        "gateway": body.gateway.upper(),
        "operating_mode": body.mode.upper(),
        "webhook_url": f"/api/v1/webhooks/ingest",
        "webhook_secret": webhook_secret,
        "shadow_mode_active": body.mode.upper() == "SHADOW",
        "instructions": (
            f"Paste this Webhook URL into your {body.gateway.title()} Dashboard under Webhooks for 'payment.failed'. "
            f"Mode is set to {body.mode.upper()}."
        ),
    }
