"""
Market data endpoints.

Provides mock market overview, OHLCV price data, index tracking,
and market regime detection. All mock data uses realistic Indian
stock prices with slight randomisation on each call.
"""

import logging
import random
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Query

from app.core.constants import (
    INDIAN_INDICES,
    INDIAN_STOCKS,
    MARKET_HOURS,
    US_INDICES,
    MarketRegime,
)
from app.schemas.market import (
    OHLCV,
    IndexData,
    MarketOverview,
    MarketRegimeResponse,
    MarketStatus,
)

import asyncio

logger = logging.getLogger(__name__)


# ── Trendline detection helpers ────────────────────────────────────────────

def _find_swing_points(candles: list[dict], n: int = 5):
    """
    Return swing highs and swing lows.
    A swing high at index i: its high > highs of n bars on each side.
    A swing low  at index i: its low  < lows  of n bars on each side.
    """
    swing_highs, swing_lows = [], []
    highs = [c["high"] for c in candles]
    lows  = [c["low"]  for c in candles]
    times = [c["time"] for c in candles]

    for i in range(n, len(candles) - n):
        h, l, t = highs[i], lows[i], times[i]

        if all(h >= highs[i - j] for j in range(1, n + 1)) and \
           all(h >= highs[i + j] for j in range(1, n + 1)):
            swing_highs.append({"time": t, "price": h, "idx": i})

        if all(l <= lows[i - j] for j in range(1, n + 1)) and \
           all(l <= lows[i + j] for j in range(1, n + 1)):
            swing_lows.append({"time": t, "price": l, "idx": i})

    return swing_highs, swing_lows


def _build_trendlines(swing_points: list[dict], line_type: str,
                      last_time: int, last_idx: int) -> list[dict]:
    """
    Connect consecutive swing points and extend each line to the right edge.
    slope_per_sec lets the frontend extrapolate at any future time.
    """
    lines = []
    for i in range(len(swing_points) - 1):
        p1, p2 = swing_points[i], swing_points[i + 1]
        dt_sec = p2["time"] - p1["time"]
        if dt_sec == 0:
            continue
        slope_per_sec = (p2["price"] - p1["price"]) / dt_sec
        # Extend to last candle (or 20 bars beyond p2)
        ext_time  = last_time
        ext_price = p2["price"] + slope_per_sec * (ext_time - p2["time"])
        lines.append({
            "type":          line_type,
            "p1":            {"time": p1["time"], "price": round(p1["price"], 6)},
            "p2":            {"time": p2["time"], "price": round(p2["price"], 6)},
            "extended":      {"time": ext_time,   "price": round(ext_price, 6)},
            "slope_per_sec": round(slope_per_sec, 10),
        })
    return lines
router = APIRouter()

IST = timezone(timedelta(hours=5, minutes=30))


def _now_ist() -> datetime:
    return datetime.now(IST)


def _jitter(base: float, pct: float = 2.0) -> float:
    """Apply a small random jitter (±pct %) to a base value."""
    return round(base * (1 + random.uniform(-pct, pct) / 100), 2)


# ═════════════════════════════════════════════════════════════════════
# Helpers to build mock data
# ═════════════════════════════════════════════════════════════════════

_INDEX_BASE_VALUES: dict[str, float] = {
    "NIFTY 50": 24850.0,
    "NIFTY BANK": 52700.0,
    "NIFTY IT": 38200.0,
    "NIFTY MIDCAP 50": 16100.0,
    "NIFTY FIN SERVICE": 24300.0,
    "SENSEX": 81500.0,
    "NIFTY PHARMA": 21500.0,
    "NIFTY AUTO": 25800.0,
    "NIFTY METAL": 9200.0,
    "NIFTY ENERGY": 40100.0,
    "SPX": 5320.0,
    "DJI": 39800.0,
    "IXIC": 16900.0,
    "RUT": 2080.0,
    "VIX": 14.5,
}


def _mock_index(idx: dict[str, str]) -> IndexData:
    """Generate a single mock index data point."""
    base = _INDEX_BASE_VALUES.get(idx["symbol"], 10000.0)
    value = _jitter(base, 1.5)
    prev = _jitter(base, 0.5)
    change = round(value - prev, 2)
    change_pct = round((change / prev) * 100, 2)
    return IndexData(
        symbol=idx["symbol"],
        name=idx["name"],
        exchange=idx["exchange"],
        value=value,
        change=change,
        change_pct=change_pct,
        high=round(value * 1.005, 2),
        low=round(value * 0.993, 2),
        prev_close=prev,
        timestamp=_now_ist(),
    )


def _mock_market_statuses() -> list[MarketStatus]:
    """Return mock market statuses based on current IST time."""
    now = _now_ist()
    hour = now.hour
    minute = now.minute
    current_minutes = hour * 60 + minute

    statuses = []
    # NSE: 9:15 - 15:30 IST
    nse_open = 9 * 60 + 15
    nse_close = 15 * 60 + 30
    nse_status = "open" if nse_open <= current_minutes <= nse_close and now.weekday() < 5 else "closed"
    statuses.append(MarketStatus(
        market="NSE", status=nse_status, timezone="Asia/Kolkata",
        next_open=now.replace(hour=9, minute=15, second=0) + timedelta(days=1 if nse_status == "closed" else 0),
        next_close=now.replace(hour=15, minute=30, second=0) if nse_status == "open" else None,
    ))
    # NYSE: open 9:30-16:00 ET → 20:00-01:30 IST (next day)
    statuses.append(MarketStatus(
        market="NYSE", status="closed", timezone="America/New_York",
    ))
    # Crypto: always open
    statuses.append(MarketStatus(
        market="CRYPTO", status="open", timezone="UTC",
    ))
    return statuses


# ═════════════════════════════════════════════════════════════════════
# Endpoints
# ═════════════════════════════════════════════════════════════════════

@router.get("/overview", response_model=MarketOverview, summary="Full market overview")
async def market_overview() -> MarketOverview:
    """
    Return a complete market overview with Indian & US indices,
    market statuses, and the current detected regime.
    """
    logger.info("Generating market overview")
    indian = [_mock_index(idx) for idx in INDIAN_INDICES]
    us = [_mock_index(idx) for idx in US_INDICES]

    regime = MarketRegimeResponse(
        regime=random.choice([MarketRegime.BULLISH, MarketRegime.NEUTRAL, MarketRegime.TRENDING]).value,
        confidence=round(random.uniform(60, 90), 1),
        description="Market showing moderate bullish momentum with sector rotation into IT and banking.",
        indicators={
            "adv_dec_ratio": round(random.uniform(1.1, 2.5), 2),
            "fii_flow_cr": round(random.uniform(-500, 2000), 0),
            "dii_flow_cr": round(random.uniform(200, 1500), 0),
            "put_call_ratio": round(random.uniform(0.7, 1.4), 2),
            "india_vix": round(random.uniform(11, 22), 2),
            "breadth_pct": round(random.uniform(45, 75), 1),
        },
        timestamp=_now_ist(),
    )

    return MarketOverview(
        indian_indices=indian,
        us_indices=us,
        market_status=_mock_market_statuses(),
        regime=regime,
        timestamp=_now_ist(),
    )


@router.get("/prices/{symbol}", response_model=list[OHLCV], summary="OHLCV price data")
async def get_price_data(
    symbol: str,
    interval: str = Query("1d", description="Candle interval: 1m, 5m, 15m, 1h, 1d"),
    limit: int = Query(500, ge=1, le=2000, description="Number of candles"),
) -> list[OHLCV]:
    """
    Generate mock OHLCV candle data for a given symbol.

    Uses the base price from INDIAN_STOCKS and applies a random walk
    to produce realistic-looking price history.
    """
    logger.info("Generating %d %s candles for %s", limit, interval, symbol)

    # Determine base price
    stock_info = INDIAN_STOCKS.get(symbol.upper())
    base_price = stock_info["base_price"] if stock_info else 1000.0

    # Interval mapping to timedelta
    interval_map = {
        "1m": timedelta(minutes=1),
        "5m": timedelta(minutes=5),
        "15m": timedelta(minutes=15),
        "1h": timedelta(hours=1),
        "1d": timedelta(days=1),
    }
    delta = interval_map.get(interval, timedelta(days=1))

    candles: list[OHLCV] = []
    price = base_price
    now = _now_ist()
    start_time = now - delta * limit

    for i in range(limit):
        ts = start_time + delta * i

        # Random walk
        change_pct = random.gauss(0.0002, 0.015)  # slight upward drift
        price = max(price * (1 + change_pct), 1.0)

        o = round(price, 2)
        h = round(o * (1 + abs(random.gauss(0, 0.008))), 2)
        l = round(o * (1 - abs(random.gauss(0, 0.008))), 2)  # noqa: E741
        c = round(random.uniform(l, h), 2)
        v = int(random.uniform(50_000, 5_000_000))

        price = c  # next candle continues from close

        candles.append(OHLCV(timestamp=ts, open=o, high=h, low=l, close=c, volume=v))

    return candles


@router.get("/indices", summary="All tracked indices")
async def get_indices() -> dict:
    """Return current values for all tracked Indian and US indices."""
    return {
        "indian": [_mock_index(idx).model_dump() for idx in INDIAN_INDICES],
        "us": [_mock_index(idx).model_dump() for idx in US_INDICES],
        "timestamp": _now_ist().isoformat(),
    }


@router.get("/candles", summary="Real OHLCV candles for forex pair")
async def get_candles(
    symbol: str = Query(..., description="Pair e.g. EURUSD or EUR/USD"),
    interval: str = Query("1h", description="1h, 4h, 1d, 15m"),
    outputsize: int = Query(200, ge=10, le=1000),
) -> list[dict]:
    """
    Return real OHLCV candlestick data for a forex/metal/crypto pair.
    Tries TwelveData → local CSV → yfinance in order.
    """
    # Normalise symbol: EURUSD → EUR/USD
    sym = symbol.upper().replace("-", "/")
    if "/" not in sym and len(sym) == 6:
        sym = sym[:3] + "/" + sym[3:]

    logger.info("Candles requested: %s %s x%d", sym, interval, outputsize)
    try:
        from app.domain.trading.forex_signal_engine import get_ohlcv_for_chart
        candles = get_ohlcv_for_chart(sym, interval, outputsize)
        return candles
    except Exception as exc:
        logger.error("Candles error %s: %s", sym, exc)
        return []


@router.get("/regime", response_model=MarketRegimeResponse, summary="Market regime")
async def get_market_regime() -> MarketRegimeResponse:
    """Return the current detected market regime with confidence score."""
    regime = random.choice(list(MarketRegime))
    descriptions = {
        MarketRegime.STRONG_BULLISH: "Strong bullish trend — broad-based rally with FII inflows.",
        MarketRegime.BULLISH: "Moderate bullish bias — selective buying in large caps.",
        MarketRegime.NEUTRAL: "Consolidation phase — range-bound trading expected.",
        MarketRegime.BEARISH: "Bearish undertone — selling pressure in mid/small caps.",
        MarketRegime.STRONG_BEARISH: "Sharp sell-off — panic-driven decline across sectors.",
        MarketRegime.HIGH_VOLATILITY: "High volatility — wide swings driven by global cues.",
        MarketRegime.LOW_VOLATILITY: "Low volatility — quiet tape, breakout expected soon.",
        MarketRegime.TRENDING: "Trending market — clear directional moves.",
        MarketRegime.RANGING: "Range-bound market — mean reversion strategies favoured.",
    }
    return MarketRegimeResponse(
        regime=regime.value,
        confidence=round(random.uniform(55, 95), 1),
        description=descriptions.get(regime, "Market conditions normal."),
        indicators={
            "adl": round(random.uniform(-0.5, 0.5), 3),
            "vix": round(random.uniform(11, 25), 2),
            "put_call_ratio": round(random.uniform(0.6, 1.5), 2),
            "rsi_nifty": round(random.uniform(30, 75), 1),
            "sma_200_slope": round(random.uniform(-0.3, 0.5), 3),
            "fii_net_cr": round(random.uniform(-1500, 2500), 0),
        },
        timestamp=_now_ist(),
    )


# ── Trendline endpoint ─────────────────────────────────────────────────────

@router.get("/trendlines", summary="Auto-detected support & resistance trendlines")
async def get_trendlines(
    symbol: str = Query(..., description="Pair e.g. EURUSD or EUR/USD"),
    interval: str = Query("1h", description="Candle interval: 15m, 1h, 4h, 1d"),
    outputsize: int = Query(150, ge=30, le=500),
    swing_n: int = Query(5, ge=2, le=10, description="Bars on each side to confirm swing"),
) -> dict:
    """
    Detect support (swing-low) and resistance (swing-high) trendlines
    from real OHLCV data. Returns p1, p2 and an extended endpoint at
    the last candle time so the frontend can draw straight trend lines.
    """
    sym = symbol.upper().replace("-", "/")
    if "/" not in sym and len(sym) == 6:
        sym = sym[:3] + "/" + sym[3:]

    logger.info("Trendlines requested: %s %s n=%d", sym, interval, swing_n)

    try:
        from app.domain.trading.forex_signal_engine import get_ohlcv_for_chart
        loop    = asyncio.get_event_loop()
        candles = await loop.run_in_executor(
            None, lambda: get_ohlcv_for_chart(sym, interval, outputsize)
        )
    except Exception as exc:
        logger.error("Trendline candle fetch failed %s: %s", sym, exc)
        candles = []

    if not candles or len(candles) < swing_n * 2 + 2:
        return {"symbol": sym, "interval": interval, "trendlines": [],
                "swing_highs": [], "swing_lows": []}

    swing_highs, swing_lows = _find_swing_points(candles, n=swing_n)

    last_time = candles[-1]["time"]

    support_lines    = _build_trendlines(swing_lows[-6:],  "support",    last_time, len(candles) - 1)
    resistance_lines = _build_trendlines(swing_highs[-6:], "resistance", last_time, len(candles) - 1)

    return {
        "symbol":      sym,
        "interval":    interval,
        "trendlines":  support_lines + resistance_lines,
        "swing_highs": [{"time": p["time"], "price": p["price"]} for p in swing_highs[-10:]],
        "swing_lows":  [{"time": p["time"], "price": p["price"]} for p in swing_lows[-10:]],
    }
