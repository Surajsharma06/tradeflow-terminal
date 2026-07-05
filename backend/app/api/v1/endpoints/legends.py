"""
Legends Mode endpoints — regime-gated multi-strategy ensemble built
from documented rules of history's great traders. Honest framing:
decision support with strict risk management, never a profit promise.
"""

import asyncio
import logging
import time
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.domain.legends.engine import (
    generate_signals,
    backtest,
    detect_regime,
    TRADER_ROSTER,
    DEFAULT_PAIRS,
)
from app.domain.lipschutz.engine import RiskGovernor
from app.domain.backtesting.backtester import _fetch_ohlcv, _normalise_pair

logger = logging.getLogger(__name__)
router = APIRouter()

_cache: dict[str, tuple[float, dict]] = {}
_CACHE_TTL = 300.0


def _cache_get(key: str) -> Optional[dict]:
    hit = _cache.get(key)
    if hit and (time.time() - hit[0]) < _CACHE_TTL:
        return hit[1]
    return None


def _cache_set(key: str, value: dict) -> None:
    _cache[key] = (time.time(), value)
    if len(_cache) > 64:
        _cache.pop(min(_cache, key=lambda k: _cache[k][0]), None)


@router.get("/signals", summary="Legends ensemble signals (regime-gated)")
async def get_signals(
    pairs: Optional[str] = Query(None, description="Comma-separated pairs"),
    equity: float = Query(10_000.0, gt=0),
    risk_pct: float = Query(1.0, gt=0, le=2.0),
):
    pair_list = [p.strip() for p in pairs.split(",")] if pairs else DEFAULT_PAIRS
    key = f"legends:{','.join(sorted(pair_list))}:{equity}:{risk_pct}"
    cached = _cache_get(key)
    if cached:
        return cached

    gov = RiskGovernor(equity=equity, risk_per_trade_pct=risk_pct)
    try:
        result = await asyncio.wait_for(
            asyncio.to_thread(generate_signals, pair_list, gov), timeout=90.0
        )
    except asyncio.TimeoutError:
        raise HTTPException(504, "Legends scan timed out")
    except Exception as exc:
        logger.exception("Legends scan failed")
        raise HTTPException(500, f"Legends scan failed: {exc}")

    _cache_set(key, result)
    return result


@router.get("/backtest", summary="Backtest the legends ensemble")
async def run_backtest(
    pair: str = Query("EURUSD"),
    days: int = Query(180, ge=60, le=365),
    equity: float = Query(10_000.0, gt=0),
    risk_pct: float = Query(1.0, gt=0, le=2.0),
):
    key = f"legends-bt:{pair}:{days}:{equity}:{risk_pct}"
    cached = _cache_get(key)
    if cached:
        return cached

    gov = RiskGovernor(equity=equity, risk_per_trade_pct=risk_pct)
    try:
        result = await asyncio.wait_for(
            asyncio.to_thread(backtest, pair, days, gov), timeout=180.0
        )
    except asyncio.TimeoutError:
        raise HTTPException(504, "Backtest timed out — try fewer days")
    except Exception as exc:
        logger.exception("Legends backtest failed")
        raise HTTPException(500, f"Backtest failed: {exc}")

    if "error" in result:
        raise HTTPException(422, result["error"])

    _cache_set(key, result)
    return result


@router.get("/regime", summary="Current market regime for a pair")
async def get_regime(pair: str = Query("EURUSD")):
    key = f"legends-regime:{pair}"
    cached = _cache_get(key)
    if cached:
        return cached

    norm = _normalise_pair(pair)
    try:
        df = await asyncio.wait_for(
            asyncio.to_thread(_fetch_ohlcv, norm, 60), timeout=45.0
        )
    except asyncio.TimeoutError:
        raise HTTPException(504, "Data fetch timed out")
    if df is None or len(df) < 210:
        raise HTTPException(422, f"Not enough data for {norm}")

    result = {"pair": norm, **detect_regime(df)}
    _cache_set(key, result)
    return result


@router.get("/traders", summary="The legends roster and their encoded rules")
async def get_traders():
    return {
        "roster": TRADER_ROSTER,
        "philosophy": (
            "Markets alternate between trends, ranges and chop. Each legend "
            "here earned their record in one of those conditions — so each "
            "strategy only trades in the regime it was built for, Livermore "
            "keeps you out of dead markets, Dalio stops correlated bets from "
            "stacking, and Lipschutz's risk governor outranks everything. "
            "No system wins every trade; this one is built to lose small "
            "and let winners run."
        ),
    }
