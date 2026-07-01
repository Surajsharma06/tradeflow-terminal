"""
Async Redis client for the Trading System.

Manages a connection pool and provides trading-specific cache helpers
for prices, signals, and market data with configurable TTLs.
"""

import json
import logging
from collections.abc import AsyncGenerator
from typing import Any, Optional

import redis.asyncio as aioredis

from app.core.config import get_settings

logger = logging.getLogger(__name__)

_redis_pool: Optional[aioredis.Redis] = None


async def init_redis() -> aioredis.Redis:
    """
    Initialise the global async Redis connection pool.

    Returns:
        The Redis client instance.
    """
    global _redis_pool
    if _redis_pool is not None:
        return _redis_pool

    settings = get_settings()
    try:
        _redis_pool = aioredis.from_url(
            settings.redis_url,
            password=settings.redis_password,
            max_connections=settings.redis_max_connections,
            decode_responses=True,
            socket_connect_timeout=5,
            retry_on_timeout=True,
        )
        # Verify connectivity
        await _redis_pool.ping()
        logger.info("Redis connection established — %s", settings.redis_url)
    except Exception as exc:
        logger.warning("Redis unavailable (%s) — cache will be disabled", exc)
        _redis_pool = None

    return _redis_pool


async def close_redis() -> None:
    """Close the Redis connection pool gracefully."""
    global _redis_pool
    if _redis_pool is not None:
        await _redis_pool.close()
        _redis_pool = None
        logger.info("Redis connection closed")


async def get_redis() -> AsyncGenerator[Optional[aioredis.Redis], None]:
    """
    FastAPI dependency that yields the Redis client.

    If Redis is unavailable the dependency yields ``None`` so endpoints
    can degrade gracefully.

    Yields:
        Optional Redis client instance.
    """
    yield _redis_pool


# ═══════════════════════════════════════════════════════════════════════
# Trading-specific Cache Helpers
# ═══════════════════════════════════════════════════════════════════════

class TradingCache:
    """High-level cache operations for trading data."""

    def __init__(self, redis_client: Optional[aioredis.Redis]):
        self._r = redis_client

    @property
    def available(self) -> bool:
        """Return True if Redis is connected."""
        return self._r is not None

    # ── Prices ───────────────────────────────────────────────────────

    async def cache_price(self, symbol: str, price_data: dict, ttl: int = 10) -> None:
        """Cache latest price for a symbol (default TTL: 10 s)."""
        if not self.available:
            return
        key = f"price:{symbol}"
        await self._r.setex(key, ttl, json.dumps(price_data))

    async def get_cached_price(self, symbol: str) -> Optional[dict]:
        """Retrieve cached price for a symbol."""
        if not self.available:
            return None
        raw = await self._r.get(f"price:{symbol}")
        return json.loads(raw) if raw else None

    # ── Signals ──────────────────────────────────────────────────────

    async def cache_signal(self, signal_id: int, signal_data: dict, ttl: int = 300) -> None:
        """Cache a signal (default TTL: 5 min)."""
        if not self.available:
            return
        await self._r.setex(f"signal:{signal_id}", ttl, json.dumps(signal_data))

    async def get_cached_signal(self, signal_id: int) -> Optional[dict]:
        """Retrieve cached signal by ID."""
        if not self.available:
            return None
        raw = await self._r.get(f"signal:{signal_id}")
        return json.loads(raw) if raw else None

    # ── Market Data ──────────────────────────────────────────────────

    async def cache_market_data(self, key: str, data: Any, ttl: int = 60) -> None:
        """Cache arbitrary market data JSON (default TTL: 60 s)."""
        if not self.available:
            return
        await self._r.setex(f"market:{key}", ttl, json.dumps(data))

    async def get_cached_market_data(self, key: str) -> Optional[Any]:
        """Retrieve cached market data."""
        if not self.available:
            return None
        raw = await self._r.get(f"market:{key}")
        return json.loads(raw) if raw else None

    # ── Generic ──────────────────────────────────────────────────────

    async def set_json(self, key: str, value: Any, ttl: int = 300) -> None:
        """Set any JSON-serialisable value."""
        if not self.available:
            return
        await self._r.setex(key, ttl, json.dumps(value))

    async def get_json(self, key: str) -> Optional[Any]:
        """Get any JSON value by key."""
        if not self.available:
            return None
        raw = await self._r.get(key)
        return json.loads(raw) if raw else None

    async def delete(self, key: str) -> None:
        """Delete a cache key."""
        if self.available:
            await self._r.delete(key)
