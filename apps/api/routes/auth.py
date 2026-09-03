from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.auth import (
    OperatorContext,
    bootstrap_default_operator,
    create_access_token,
    require_operator,
    verify_password,
)
from apps.api.settings import get_settings
from domain.models.entities import OperatorEntity
from domain.models.schemas import OperatorLoginRequest, OperatorTokenResponse
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
