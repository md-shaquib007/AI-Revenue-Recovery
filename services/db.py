from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from apps.api.settings import get_settings
from domain.models.entities import Base

settings = get_settings()

engine_kwargs = {
    "echo": False,
    "future": True,
    "pool_pre_ping": True,
}

if not settings.is_sqlite:
    engine_kwargs.update({
        "pool_size": settings.db_pool_size,
        "max_overflow": settings.db_max_overflow,
        "pool_timeout": settings.db_pool_timeout,
        "pool_recycle": settings.db_pool_recycle,
    })

engine = create_async_engine(
    settings.normalized_database_url,
    **engine_kwargs,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


import asyncio
from sqlalchemy.exc import OperationalError


from sqlalchemy import text


async def init_db(max_retries: int = 3, retry_delay: float = 0.5):
    """
    Create tables if they do not exist.
    Retries with exponential backoff to smoothly handle Neon serverless compute wakeups.
    """
    for attempt in range(1, max_retries + 1):
        try:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
                # Ensure new columns exist on legacy tables (SQLite + PostgreSQL)
                if settings.is_sqlite:
                    for sql in [
                        "ALTER TABLE customers ADD COLUMN predicted_salary_day INTEGER",
                        "ALTER TABLE recovery_cases ADD COLUMN amount_recovered_paise BIGINT DEFAULT 0",
                        "ALTER TABLE recovery_cases ADD COLUMN balance_due_paise BIGINT",
                        "ALTER TABLE recovery_cases ADD COLUMN partial_payments_count INTEGER DEFAULT 0",
                    ]:
                        try:
                            await conn.execute(text(sql))
                        except Exception:
                            pass
                else:
                    for sql in [
                        "ALTER TABLE customers ADD COLUMN IF NOT EXISTS predicted_salary_day INTEGER",
                        "ALTER TABLE recovery_cases ADD COLUMN IF NOT EXISTS amount_recovered_paise BIGINT DEFAULT 0",
                        "ALTER TABLE recovery_cases ADD COLUMN IF NOT EXISTS balance_due_paise BIGINT",
                        "ALTER TABLE recovery_cases ADD COLUMN IF NOT EXISTS partial_payments_count INTEGER DEFAULT 0",
                    ]:
                        try:
                            await conn.execute(text(sql))
                        except Exception:
                            pass
            break
        except (OperationalError, OSError):
            if attempt == max_retries:
                raise
            await asyncio.sleep(retry_delay * (2 ** (attempt - 1)))


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


@asynccontextmanager
async def session_scope() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
