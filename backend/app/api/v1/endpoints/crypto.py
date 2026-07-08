"""
Crypto Analysis endpoints — BTC, ETH, SOL
"""

import asyncio
import logging
import time
from typing import Optional

from fastapi import APIRouter, Query

from app.domain.crypto.engine import analyze_all, analyze_asset, _get_fear_greed, ASSETS

logger = logging.getLogger(__name__)
router = APIRouter()

_cache: dict[str, tuple[float, dict]] = {}
_CACHE_TTL = 180.0  # 3 min for crypto (prices move fast)


def _cget(key: str) -> Optional[dict]:
    hit = _cache.get(key)
    return hit[1] if hit and (time.time() - hit[0]) < _CACHE_TTL else None


def _cset(key: str, val: dict) -> None:
    _cache[key] = (time.time(), val)
    if len(_cache) > 32:
        _cache.pop(min(_cache, key=lambda k: _cache[k][0]), None)


@router.get("/signals", summary="Crypto analysis — BTC, ETH, SOL")
async def get_crypto_signals(
    balance: float = Query(10_000.0, gt=0, description="Account balance"),
    risk_pct: float = Query(1.0, gt=0, le=2.0, description="Risk per trade %"),
):
    key = f"crypto-all:{balance}:{risk_pct}"
    cached = _cget(key)
    if cached:
        return cached

    try:
        result = await asyncio.wait_for(
            asyncio.to_thread(analyze_all, balance, risk_pct),
            timeout=90.0,
        )
    except asyncio.TimeoutError:
        from fastapi import HTTPException
        raise HTTPException(504, "Crypto analysis timed out")
    except Exception as exc:
        logger.exception("Crypto scan failed")
        from fastapi import HTTPException
        raise HTTPException(500, f"Crypto scan failed: {exc}")

    _cset(key, result)
    return result


@router.get("/signal/{symbol}", summary="Analysis for a single crypto asset")
async def get_single_signal(
    symbol: str,
    balance: float = Query(10_000.0, gt=0),
    risk_pct: float = Query(1.0, gt=0, le=2.0),
):
    sym = symbol.upper()
    if sym not in ASSETS:
        from fastapi import HTTPException
        raise HTTPException(400, f"Unknown symbol {symbol}. Valid: {list(ASSETS.keys())}")

    key = f"crypto-single:{sym}:{balance}:{risk_pct}"
    cached = _cget(key)
    if cached:
        return cached

    try:
        result = await asyncio.wait_for(
            asyncio.to_thread(analyze_asset, sym, None, balance, risk_pct),
            timeout=60.0,
        )
    except asyncio.TimeoutError:
        from fastapi import HTTPException
        raise HTTPException(504, "Analysis timed out")
    except Exception as exc:
        logger.exception("Single crypto analysis failed")
        from fastapi import HTTPException
        raise HTTPException(500, str(exc))

    _cset(key, result)
    return result


@router.get("/fear-greed", summary="Fear & Greed index (alternative.me)")
async def get_fear_greed():
    key = "crypto-fg"
    cached = _cget(key)
    if cached:
        return cached
    try:
        result = await asyncio.wait_for(asyncio.to_thread(_get_fear_greed), timeout=10.0)
    except Exception:
        result = {"value": 50, "label": "Neutral", "timestamp": None}
    _cset(key, result)
    return result
