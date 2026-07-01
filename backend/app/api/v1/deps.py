"""
Shared FastAPI dependencies for API v1.

Provides injectable database sessions, Redis clients, and settings.
"""

from collections.abc import AsyncGenerator
from typing import Optional

import redis.asyncio as aioredis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.infrastructure.cache.redis_client import get_redis as _get_redis
from app.infrastructure.database.session import get_db as _get_db


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield an async SQLAlchemy session — delegates to infrastructure."""
    async for session in _get_db():
        yield session


async def get_redis() -> AsyncGenerator[Optional[aioredis.Redis], None]:
    """Yield the Redis client (may be None if Redis is down)."""
    async for client in _get_redis():
        yield client


def get_settings_dep() -> Settings:
    """Return the cached Settings singleton."""
    return get_settings()
