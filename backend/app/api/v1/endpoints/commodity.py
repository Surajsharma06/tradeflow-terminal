"""Commodity Analysis endpoints — Gold, Silver, WTI Crude, Natural Gas"""

import asyncio
import logging
import time
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.domain.commodity.engine import (
    analyze_all, analyze_commodity, backtest_commodity,
    get_upcoming_events, ASSETS,
)

logger = logging.getLogger(__name__)
router = APIRouter()

_cache: dict[str, tuple[float, dict]] = {}
_TTL = 300.0   # 5-min price cache


def _cget(k: str) -> Optional[dict]:
    h = _cache.get(k)
    return h[1] if h and (time.time() - h[0]) < _TTL else None


def _cset(k: str, v: dict) -> None:
    _cache[k] = (time.time(), v)
    if len(_cache) > 40:
        _cache.pop(min(_cache, key=lambda x: _cache[x][0]), None)


@router.get("/signals", summary="Full commodity analysis — all 4 assets")
async def get_commodity_signals(
    balance: float = Query(10_000.0, gt=0),
    risk_pct: float = Query(1.0, gt=0, le=2.0),
):
    key = f"comm-all:{balance}:{risk_pct}"
    if c := _cget(key): return c
    try:
        result = await asyncio.wait_for(
            asyncio.to_thread(analyze_all, balance, risk_pct), timeout=120.0
        )
    except asyncio.TimeoutError:
        raise HTTPException(504, "Commodity scan timed out")
    except Exception as exc:
        logger.exception("Commodity scan failed"); raise HTTPException(500, str(exc))
    _cset(key, result)
    return result


@router.get("/signal/{symbol}", summary="Analysis for a single commodity")
async def get_single_signal(
    symbol: str,
    balance: float = Query(10_000.0, gt=0),
    risk_pct: float = Query(1.0, gt=0, le=2.0),
):
    sym = symbol.upper()
    if sym not in ASSETS:
        raise HTTPException(400, f"Unknown symbol '{symbol}'. Valid: {list(ASSETS.keys())}")
    key = f"comm-{sym}:{balance}:{risk_pct}"
    if c := _cget(key): return c
    try:
        result = await asyncio.wait_for(
            asyncio.to_thread(analyze_commodity, sym, None, balance, risk_pct), timeout=90.0
        )
    except asyncio.TimeoutError:
        raise HTTPException(504, "Analysis timed out")
    except Exception as exc:
        logger.exception("Single commodity analysis failed"); raise HTTPException(500, str(exc))
    _cset(key, result)
    return result


@router.get("/backtest", summary="Technical backtest for a commodity")
async def run_backtest(
    symbol: str = Query("XAU"),
    days: int = Query(365, ge=60, le=730),
    balance: float = Query(10_000.0, gt=0),
    risk_pct: float = Query(1.0, gt=0, le=2.0),
):
    sym = symbol.upper()
    if sym not in ASSETS:
        raise HTTPException(400, f"Unknown symbol '{symbol}'")
    key = f"comm-bt:{sym}:{days}:{balance}:{risk_pct}"
    if c := _cget(key): return c
    try:
        result = await asyncio.wait_for(
            asyncio.to_thread(backtest_commodity, sym, days, balance, risk_pct), timeout=180.0
        )
    except asyncio.TimeoutError:
        raise HTTPException(504, "Backtest timed out")
    except Exception as exc:
        logger.exception("Commodity backtest failed"); raise HTTPException(500, str(exc))
    _cset(key, result)
    return result


@router.get("/calendar", summary="Economic calendar — next 7 days")
async def get_calendar(horizon_days: int = Query(7, ge=1, le=30)):
    try:
        events = await asyncio.to_thread(get_upcoming_events, horizon_days)
    except Exception as exc:
        raise HTTPException(500, str(exc))
    return {"events": events, "horizon_days": horizon_days}
