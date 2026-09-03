import hashlib
import hmac
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.settings import get_settings
from domain.models.entities import OperatorEntity
from services.db import get_db


PBKDF_ITERATIONS = 120_000


def hash_password(password: str, salt: Optional[str] = None) -> str:
    salt = salt or secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), PBKDF_ITERATIONS)
    return f"{salt}${dk.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        salt, digest = stored.split("$", 1)
    except ValueError:
        return False
    candidate = hash_password(password, salt)
    return hmac.compare_digest(candidate, stored)


@dataclass
class OperatorContext:
    id: str
    username: str
    role: str


def create_access_token(operator: OperatorEntity) -> str:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    payload = {
        "sub": operator.id,
        "username": operator.username,
        "role": operator.role,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=settings.jwt_expire_minutes)).timestamp()),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict:
    settings = get_settings()
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token") from exc


async def bootstrap_default_operator(db: AsyncSession) -> None:
    settings = get_settings()
    result = await db.execute(select(OperatorEntity).where(OperatorEntity.username == settings.operator_username))
    existing = result.scalars().first()
    if existing:
        return
    operator = OperatorEntity(
        username=settings.operator_username,
        password_hash=hash_password(settings.operator_password),
        role=settings.operator_role,
    )
    db.add(operator)
    await db.flush()


async def get_optional_operator(
    authorization: Optional[str] = Header(default=None),
    db: AsyncSession = Depends(get_db),
) -> Optional[OperatorContext]:
    if not authorization or not authorization.lower().startswith("bearer "):
        return None
    token = authorization.split(" ", 1)[1].strip()
    payload = decode_token(token)
    result = await db.execute(select(OperatorEntity).where(OperatorEntity.id == payload.get("sub")))
    operator = result.scalars().first()
    if not operator:
        return None
    return OperatorContext(id=operator.id, username=operator.username, role=operator.role)


async def require_operator(
    authorization: Optional[str] = Header(default=None),
    db: AsyncSession = Depends(get_db),
) -> OperatorContext:
    settings = get_settings()
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization.split(" ", 1)[1].strip()
        payload = decode_token(token)
        result = await db.execute(select(OperatorEntity).where(OperatorEntity.id == payload.get("sub")))
        operator = result.scalars().first()
        if not operator:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Operator not found")
        return OperatorContext(id=operator.id, username=operator.username, role=operator.role)
    if not settings.require_auth:
        return OperatorContext(id="system", username="system", role="admin")
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")


# Fine-Grained RBAC Permissions Matrix
ROLE_PERMISSIONS = {
    "admin": ["*"],
    "risk_admin": ["cases:read", "cases:write", "policies:write", "sentinel:write", "dlq:read", "dlq:replay", "audit:export"],
    "operator": ["cases:read", "cases:approve", "dlq:read", "dlq:replay", "audit:export"],
    "auditor": ["cases:read", "audit:export", "metrics:read"],
    "viewer": ["cases:read", "metrics:read"],
}


def has_permission(role: str, permission: str) -> bool:
    perms = ROLE_PERMISSIONS.get(role, [])
    return "*" in perms or permission in perms


def require_admin(operator: OperatorContext = Depends(require_operator)) -> OperatorContext:
    if operator.role not in ("admin", "operator"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient role")
    return operator


def require_permission(permission: str):
    """Dependency factory enforcing fine-grained enterprise RBAC scopes."""
    def _dependency(operator: OperatorContext = Depends(require_operator)) -> OperatorContext:
        if not has_permission(operator.role, permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Missing required permission: '{permission}' (Your role: '{operator.role}')",
            )
        return operator
    return _dependency


async def require_chaos(operator: OperatorContext = Depends(require_operator)) -> OperatorContext:
    settings = get_settings()
    if not settings.allow_chaos:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Chaos lab is disabled in this environment")
    if settings.require_auth and operator.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin role required for chaos lab")
    return operator
