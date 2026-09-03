import os

os.environ["APP_ENV"] = "test"
os.environ["WORKER_ENABLED"] = "false"
os.environ["AUTH_REQUIRED"] = "false"
os.environ["CHAOS_ENABLED"] = "true"
os.environ["RATE_LIMIT_ENABLED"] = "false"
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./revive_test.db"
os.environ["JWT_SECRET"] = "test-secret"

from apps.api.settings import get_settings

get_settings.cache_clear()

import pytest
from sqlalchemy import text

from domain.models.entities import Base
from services.db import engine, init_db


@pytest.fixture(autouse=True)
async def setup_and_clean_test_database():
    """Ensures a clean database state with latest schema for each test."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        for table in reversed(Base.metadata.sorted_tables):
            await conn.execute(text(f"DELETE FROM {table.name}"))
    yield
