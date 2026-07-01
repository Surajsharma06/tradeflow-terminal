"""
Trading signals endpoints.

Returns mock active signals with full score breakdowns, signal history,
and individual signal detail. Realistic Indian stock signals.
"""

import logging
import random
from datetime import datetime, timedelta, timezone

from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.core.constants import INDIAN_STOCKS, MarketType, StrategyName
from app.schemas.signal import SignalResponse, SignalScoreBreakdown

logger = logging.getLogger(__name__)
router = APIRouter()

IST = timezone(timedelta(hours=5, minutes=30))


def _now_ist() -> datetime:
    return datetime.now(IST)


def _generate_mock_signal(signal_id: int, status: str = "active") -> SignalResponse:
    """Generate a single realistic mock signal."""
    symbols = list(INDIAN_STOCKS.keys())
    symbol = random.choice(symbols)
    stock = INDIAN_STOCKS[symbol]
    base = stock["base_price"]

    direction = random.choice(["long", "short"])
    strategy = random.choice(list(StrategyName)).value

    # Score breakdown
    tech = round(random.uniform(40, 95), 1)
    sent = round(random.uniform(30, 85), 1)
    vol = round(random.uniform(35, 90), 1)
    reg = round(random.uniform(40, 85), 1)
    macro = round(random.uniform(35, 80), 1)
    # Weighted composite
    score = round(tech * 0.35 + sent * 0.15 + vol * 0.20 + reg * 0.15 + macro * 0.15, 1)

    entry = round(base * random.uniform(0.97, 1.03), 2)
    if direction == "long":
        sl = round(entry * (1 - random.uniform(0.015, 0.03)), 2)
        tp = round(entry * (1 + random.uniform(0.03, 0.08)), 2)
    else:
        sl = round(entry * (1 + random.uniform(0.015, 0.03)), 2)
        tp = round(entry * (1 - random.uniform(0.03, 0.08)), 2)

    risk = abs(entry - sl)
    reward = abs(tp - entry)
    rr = round(reward / risk, 2) if risk > 0 else 0.0

    created = _now_ist() - timedelta(minutes=random.randint(5, 480))

    return SignalResponse(
        id=signal_id,
        symbol=symbol,
        market=MarketType.INDIAN_EQUITY.value,
        direction=direction,
        strategy=strategy,
        score=score,
        breakdown=SignalScoreBreakdown(
            technical_score=tech,
            sentiment_score=sent,
            volume_score=vol,
            regime_score=reg,
            macro_score=macro,
        ),
        entry_price=entry,
        stop_loss=sl,
        target_price=tp,
        risk_reward=rr,
        status=status,
        created_at=created,
        expires_at=created + timedelta(hours=random.randint(4, 24)),
    )


@router.get("/active", response_model=list[SignalResponse], summary="Active signals")
async def get_active_signals() -> list[SignalResponse]:
    """
    Return 5-8 mock active trading signals with full score breakdowns.

    Each signal includes technical, sentiment, volume, regime, and macro
    scores that compose the final signal score.
    """
    logger.info("Fetching active signals")
    count = random.randint(5, 8)
    return [_generate_mock_signal(i + 1, status="active") for i in range(count)]


@router.get("/history", response_model=list[SignalResponse], summary="Signal history")
async def get_signal_history(
    limit: int = Query(20, ge=1, le=100),
    strategy: Optional[str] = Query(None, description="Filter by strategy"),
) -> list[SignalResponse]:
    """Return historical signals (executed, expired, or rejected)."""
    logger.info("Fetching signal history — limit=%d, strategy=%s", limit, strategy)
    statuses = ["executed", "expired", "rejected"]
    signals = []
    for i in range(limit):
        s = _generate_mock_signal(100 + i, status=random.choice(statuses))
        if strategy and s.strategy != strategy:
            continue
        signals.append(s)
    return signals[:limit]


# ─────────────────────────────────────────────────────────────────────────
# Forex signals — ADX + Session + ATR engine (all pairs)
# GET /api/v1/signals/forex
# ─────────────────────────────────────────────────────────────────────────

@router.get("/forex", summary="Forex signals — all pairs (ADX + Session + ATR)")
async def get_forex_signals(
    pairs: Optional[str] = Query(
        default=None,
        description="Comma-separated pairs e.g. EUR/USD,GBP/USD. Empty = all."
    ),
    min_confidence: int = Query(default=55, ge=0, le=100),
    use_cache: bool = Query(default=True, description="Return saved signals if < 5 min old"),
):
    """
    Scan all forex pairs and return signals with ADX>20 filter,
    session filter, ATR-based SL/TP1/TP2/TP3, and confidence %.

    Covers: Majors, EUR/GBP/AUD/NZD/CAD crosses, XAU/USD, XAG/USD,
    BTC/USD, ETH/USD.
    """
    from app.domain.trading.forex_signal_engine import (
        scan_all_pairs, load_saved_signals, ALL_PAIRS
    )
    from datetime import timezone
    from dateutil import parser as dparser

    # Optionally serve cached results if fresh (< 5 min)
    if use_cache:
        cached = load_saved_signals()
        if cached.get("updated_at"):
            try:
                age_seconds = (
                    _now_ist().timestamp()
                    - dparser.parse(cached["updated_at"]).timestamp()
                )
                if age_seconds < 300:
                    sigs = cached.get("signals", [])
                    if pairs:
                        wanted = {p.strip() for p in pairs.split(",") if p.strip()}
                        sigs = [s for s in sigs if s["pair"] in wanted]
                    sigs = [s for s in sigs if s.get("confidence", 0) >= min_confidence]
                    return {
                        "status": "cached",
                        "count": len(sigs),
                        "signals": sigs,
                        "updated_at": cached["updated_at"],
                    }
            except Exception:
                pass

    pair_list = None
    if pairs:
        pair_list = [p.strip() for p in pairs.split(",") if p.strip() in ALL_PAIRS]

    logger.info("Forex signal scan — pairs=%s min_conf=%d", pair_list or "all", min_confidence)

    import asyncio
    loop = asyncio.get_event_loop()
    signals = await loop.run_in_executor(
        None, lambda: scan_all_pairs(pair_list, min_confidence)
    )

    return {
        "status": "ok",
        "count": len(signals),
        "pairs_scanned": len(pair_list) if pair_list else len(ALL_PAIRS),
        "signals": signals,
        "updated_at": _now_ist().isoformat(),
    }


# ─────────────────────────────────────────────────────────────────────────
# Smart Money Forex — ICT / SMC Signals (Real-time yfinance data)
# IMPORTANT: This MUST be registered BEFORE /{signal_id} to avoid conflict
# GET /api/v1/signals/smart-money-forex
# ─────────────────────────────────────────────────────────────────────────

import asyncio as _asyncio
import time as _time

# ── In-process SMC cache (avoids blocking event loop on every call) ───────
_smc_cache: dict = {}          # {"signals": [...], "ts": float, "pairs_scanned": int}
_SMC_TTL   = 90                # seconds — serve stale while refreshing
_smc_lock  = _asyncio.Lock()   # one refresh at a time


async def _refresh_smc(pair_list, FOREX_PAIRS, scan_all, signal_to_dict):
    """Run scan_all in thread pool and update the cache."""
    loop   = _asyncio.get_event_loop()
    try:
        signals = await loop.run_in_executor(
            None, lambda: scan_all(pair_list)
        )
        _smc_cache.update({
            "signals":       [signal_to_dict(s) for s in signals],
            "pairs_scanned": len(pair_list) if pair_list else None,
            "ts":            _time.monotonic(),
            "updated_at":    _now_ist().isoformat(),
        })
    except Exception as exc:
        logger.error("SMC background refresh failed: %s", exc)


@router.get("/smart-money-forex", summary="Smart Money Forex Signals (FVG + Liq Sweep + OB)")
async def get_smart_money_signals(
    pairs: Optional[str] = Query(
        default=None,
        description="Comma-separated pairs e.g. EUR/USD,GBP/USD. Leave empty for all."
    )
):
    """
    Real-time ICT / Smart Money Concept forex signals.

    Cached (90 s) and served from thread pool so the event loop is never blocked.
    """
    from app.domain.trading.smart_money_forex import (
        scan_all, signal_to_dict, FOREX_PAIRS
    )

    pair_list = None
    if pairs:
        pair_list = [p.strip() for p in pairs.split(",") if p.strip() in FOREX_PAIRS]

    logger.info("SMC forex scan — pairs: %s", pair_list or "all")

    now_ts = _time.monotonic()
    cache_age = now_ts - _smc_cache.get("ts", 0)

    # Fresh cache → return immediately
    if cache_age < _SMC_TTL and _smc_cache.get("signals") is not None:
        sigs = _smc_cache["signals"]
        return {
            "status":        "cached",
            "count":         len(sigs),
            "pairs_scanned": _smc_cache.get("pairs_scanned") or len(FOREX_PAIRS),
            "signals":       sigs,
            "updated_at":    _smc_cache.get("updated_at", _now_ist().isoformat()),
        }

    # Stale cache → return stale instantly and kick off background refresh
    if _smc_cache.get("signals") is not None:
        async with _smc_lock:
            if _time.monotonic() - _smc_cache.get("ts", 0) >= _SMC_TTL:
                _asyncio.ensure_future(
                    _refresh_smc(pair_list, FOREX_PAIRS, scan_all, signal_to_dict)
                )
        sigs = _smc_cache["signals"]
        return {
            "status":        "stale",
            "count":         len(sigs),
            "pairs_scanned": _smc_cache.get("pairs_scanned") or len(FOREX_PAIRS),
            "signals":       sigs,
            "updated_at":    _smc_cache.get("updated_at", _now_ist().isoformat()),
        }

    # Cold start — must block once to populate cache
    async with _smc_lock:
        if _smc_cache.get("signals") is None:
            await _refresh_smc(pair_list, FOREX_PAIRS, scan_all, signal_to_dict)

    sigs = _smc_cache.get("signals", [])
    return {
        "status":        "ok",
        "count":         len(sigs),
        "pairs_scanned": _smc_cache.get("pairs_scanned") or len(FOREX_PAIRS),
        "signals":       sigs,
        "updated_at":    _smc_cache.get("updated_at", _now_ist().isoformat()),
    }


@router.get("/{signal_id}", response_model=SignalResponse, summary="Signal detail")
async def get_signal_detail(signal_id: int) -> SignalResponse:
    """Return full detail for a single signal by ID."""
    logger.info("Fetching signal detail — id=%d", signal_id)
    if signal_id < 1:
        raise HTTPException(status_code=404, detail="Signal not found")
    return _generate_mock_signal(signal_id, status="active")

