"""
Lipschutz Mode endpoints — disciplined rules-based signals.

Honest framing: these endpoints expose a deterministic decision-support
engine with mandatory risk management. Copy never promises profit.
"""

import asyncio
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.domain.lipschutz.engine import (
    RiskGovernor,
    generate_signals,
    backtest,
    DEFAULT_PAIRS,
)

logger = logging.getLogger(__name__)
router = APIRouter()

# Simple in-process TTL cache: live scans hit yfinance for every pair,
# so cache results for 5 minutes to stay well inside rate limits.
_cache: dict[str, tuple[float, dict]] = {}
_CACHE_TTL = 300.0


def _cache_get(key: str) -> Optional[dict]:
    import time
    hit = _cache.get(key)
    if hit and (time.time() - hit[0]) < _CACHE_TTL:
        return hit[1]
    return None


def _cache_set(key: str, value: dict) -> None:
    import time
    _cache[key] = (time.time(), value)
    # Keep the cache bounded.
    if len(_cache) > 64:
        oldest = min(_cache, key=lambda k: _cache[k][0])
        _cache.pop(oldest, None)


@router.get("/signals", summary="Current disciplined signals (rules-based)")
async def get_signals(
    pairs: Optional[str] = Query(None, description="Comma-separated pairs, e.g. EURUSD,GBPUSD"),
    equity: float = Query(10_000.0, gt=0, description="Account equity for position sizing"),
    risk_pct: float = Query(1.0, gt=0, le=2.0, description="Risk per trade (max 2%)"),
):
    """
    Scan pairs against the deterministic rule set (EMA trend + RSI
    pullback + ATR stops). Every signal includes the exact reasons it
    fired, mandatory SL/TP, R:R, and a position size suggestion.
    """
    pair_list = [p.strip() for p in pairs.split(",")] if pairs else DEFAULT_PAIRS
    cache_key = f"signals:{','.join(sorted(pair_list))}:{equity}:{risk_pct}"
    cached = _cache_get(cache_key)
    if cached:
        return cached

    governor = RiskGovernor(equity=equity, risk_per_trade_pct=risk_pct)
    try:
        result = await asyncio.wait_for(
            asyncio.to_thread(generate_signals, pair_list, governor),
            timeout=60.0,
        )
    except asyncio.TimeoutError:
        raise HTTPException(504, "Signal scan timed out — data provider slow")
    except Exception as exc:
        logger.exception("Lipschutz signal scan failed")
        raise HTTPException(500, f"Signal scan failed: {exc}")

    _cache_set(cache_key, result)
    return result


@router.get("/backtest", summary="Backtest the rule set on real history")
async def run_backtest(
    pair: str = Query("EURUSD", description="Pair, e.g. EURUSD or EUR/USD"),
    days: int = Query(180, ge=30, le=365, description="Lookback window"),
    equity: float = Query(10_000.0, gt=0),
    risk_pct: float = Query(1.0, gt=0, le=2.0),
):
    """
    Replay the exact live rules bar-by-bar over yfinance history.
    Returns win rate, average R multiple, profit factor, max drawdown
    and an equity curve — honest stats, no cherry-picking.
    """
    cache_key = f"bt:{pair}:{days}:{equity}:{risk_pct}"
    cached = _cache_get(cache_key)
    if cached:
        return cached

    governor = RiskGovernor(equity=equity, risk_per_trade_pct=risk_pct)
    try:
        result = await asyncio.wait_for(
            asyncio.to_thread(backtest, pair, days, governor),
            timeout=120.0,
        )
    except asyncio.TimeoutError:
        raise HTTPException(504, "Backtest timed out — try fewer days")
    except Exception as exc:
        logger.exception("Lipschutz backtest failed")
        raise HTTPException(500, f"Backtest failed: {exc}")

    if "error" in result:
        raise HTTPException(422, result["error"])

    _cache_set(cache_key, result)
    return result


@router.get("/status", summary="Risk governor status & engine rules")
async def get_status(
    daily_pnl_pct: float = Query(0.0, description="Today's realised P&L %"),
    weekly_pnl_pct: float = Query(0.0, description="This week's realised P&L %"),
):
    """Circuit-breaker state plus the full documented rule set."""
    gov = RiskGovernor(daily_pnl_pct=daily_pnl_pct, weekly_pnl_pct=weekly_pnl_pct)
    active, reason = gov.circuit_breaker_active()
    return {
        "circuit_breaker": active,
        "reason": reason,
        "limits": {
            "risk_per_trade_pct": gov.risk_per_trade_pct,
            "max_daily_loss_pct": gov.max_daily_loss_pct,
            "max_weekly_loss_pct": gov.max_weekly_loss_pct,
        },
        "philosophy": (
            "Discipline over prediction. Position sizing, mandatory stops "
            "and loss limits matter more than any entry signal. This engine "
            "is a transparent decision-support tool — it does not guarantee "
            "profit, and forex trading carries real risk of loss."
        ),
    }
