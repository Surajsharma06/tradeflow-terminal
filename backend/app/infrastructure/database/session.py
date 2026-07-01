"""
Async SQLAlchemy database session management.

Creates the async engine, session factory, and provides the ``get_db``
FastAPI dependency that yields a scoped async session per request.
"""

import logging
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""

    pass


# ── Engine & Session Factory (lazily initialised) ────────────────────

_engine = None
_async_session_factory = None


def _get_engine():
    """Create or return the cached async engine."""
    global _engine
    if _engine is None:
        settings = get_settings()
        url = settings.database_url
        is_sqlite = url.startswith("sqlite")
        kwargs = {"echo": settings.db_echo}
        if not is_sqlite:
            kwargs.update({
                "pool_size": settings.db_pool_size,
                "max_overflow": settings.db_max_overflow,
                "pool_timeout": settings.db_pool_timeout,
                "pool_pre_ping": True,
            })
        _engine = create_async_engine(url, **kwargs)
        logger.info("Async SQLAlchemy engine created (%s)", "SQLite" if is_sqlite else "PostgreSQL")
    return _engine


def _get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Create or return the cached session factory."""
    global _async_session_factory
    if _async_session_factory is None:
        _async_session_factory = async_sessionmaker(
            bind=_get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
        )
    return _async_session_factory


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency that yields an async database session.

    The session is automatically closed after the request completes.
    Rolls back on exception.

    Yields:
        AsyncSession: A scoped SQLAlchemy async session.
    """
    session_factory = _get_session_factory()
    async with session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db() -> None:
    """
    Initialise the database — create all tables if they don't exist.

    Should be called once at application startup.
    """
    engine = _get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables initialised")


async def close_db() -> None:
    """Dispose the engine connection pool on shutdown."""
    global _engine, _async_session_factory
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _async_session_factory = None
        logger.info("Database engine disposed")
