"""
Live Order Book endpoint for Forex pairs.

Generates realistic synthetic order book depth using real current prices
from yfinance. Forex is OTC so true L2 data doesn't exist publicly;
we simulate depth based on typical interbank spread distributions.
"""

import asyncio
import logging
import math
import random
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException, Query

_executor = ThreadPoolExecutor(max_workers=4)

logger = logging.getLogger(__name__)
router = APIRouter()

IST = timezone(timedelta(hours=5, minutes=30))

# ── Typical spreads per pair (in price units) ─────────────────────────────
_SPREADS: dict[str, float] = {
    "EUR/USD": 0.00012, "GBP/USD": 0.00018, "USD/JPY": 0.015,
    "USD/CHF": 0.00015, "AUD/USD": 0.00018, "USD/CAD": 0.00018,
    "NZD/USD": 0.00022, "EUR/GBP": 0.00014, "EUR/JPY": 0.018,
    "GBP/JPY": 0.025,   "EUR/AUD": 0.00030, "EUR/CAD": 0.00028,
    "AUD/JPY": 0.020,   "CAD/JPY": 0.022,   "CHF/JPY": 0.022,
    "NZD/JPY": 0.022,   "AUD/CAD": 0.00025, "AUD/CHF": 0.00025,
    "XAU/USD": 0.35,    "XAG/USD": 0.015,
    "BTC/USD": 15.0,    "ETH/USD": 1.5,
    "USD/INR": 0.008,
}

_YF_MAP: dict[str, str] = {
    "EUR/USD": "EURUSD=X", "GBP/USD": "GBPUSD=X", "USD/JPY": "USDJPY=X",
    "USD/CHF": "USDCHF=X", "AUD/USD": "AUDUSD=X", "USD/CAD": "USDCAD=X",
    "NZD/USD": "NZDUSD=X", "EUR/GBP": "EURGBP=X", "EUR/JPY": "EURJPY=X",
    "GBP/JPY": "GBPJPY=X", "EUR/AUD": "EURAUD=X", "EUR/CAD": "EURCAD=X",
    "AUD/JPY": "AUDJPY=X", "CAD/JPY": "CADJPY=X", "CHF/JPY": "CHFJPY=X",
    "NZD/JPY": "NZDJPY=X", "AUD/CAD": "AUDCAD=X", "AUD/CHF": "AUDCHF=X",
    "XAU/USD": "GC=F",     "XAG/USD": "SI=F",
    "BTC/USD": "BTC-USD",  "ETH/USD": "ETH-USD",
    "USD/INR": "INR=X",
}

# pip value helper
def _pip_size(pair: str) -> float:
    if "JPY" in pair or "JPY" in pair.upper():
        return 0.01
    if pair in ("XAU/USD",):
        return 0.10
    if pair in ("BTC/USD", "ETH/USD"):
        return 1.0
    return 0.0001

# ── In-memory price cache (90s TTL) ─────────────────────────────────────────
_price_cache: dict[str, tuple[float, float]] = {}  # pair → (price, ts)
_PRICE_TTL = 90.0

# Fallback prices when yfinance is slow/down
_FALLBACK_PRICES: dict[str, float] = {
    "EUR/USD": 1.1350, "GBP/USD": 1.3200, "USD/JPY": 162.50,
    "USD/CHF": 0.8100, "AUD/USD": 0.6880, "USD/CAD": 1.4230,
    "NZD/USD": 0.5650, "EUR/GBP": 0.8600, "EUR/JPY": 184.50,
    "GBP/JPY": 214.50, "EUR/AUD": 1.6490, "EUR/CAD": 1.6150,
    "AUD/JPY": 111.80, "CAD/JPY": 114.20, "CHF/JPY": 200.50,
    "NZD/JPY": 91.80,  "AUD/CAD": 0.9780, "AUD/CHF": 0.5560,
    "XAU/USD": 3350.0, "XAG/USD": 33.50,
    "BTC/USD": 65000.0,"ETH/USD": 3500.0,
    "USD/INR": 84.50,
}

def _fetch_yf_price(ticker: str) -> float:
    """Blocking yfinance fetch — run in thread executor."""
    import yfinance as yf
    t = yf.Ticker(ticker)
    try:
        price = float(t.fast_info.last_price or 0)
        if price > 0:
            return price
    except Exception:
        pass
    hist = t.history(period="2d", interval="1h")
    if not hist.empty:
        return float(hist["Close"].iloc[-1])
    return 0.0

async def _get_price_async(pair: str) -> float:
    now = time.time()
    if pair in _price_cache:
        price, ts = _price_cache[pair]
        if now - ts < _PRICE_TTL:
            return price

    ticker = _YF_MAP.get(pair)
    if not ticker:
        return _FALLBACK_PRICES.get(pair, 1.0)

    try:
        loop  = asyncio.get_event_loop()
        price = await asyncio.wait_for(
            loop.run_in_executor(_executor, _fetch_yf_price, ticker),
            timeout=8.0,
        )
        if price <= 0:
            raise ValueError("zero price")
    except Exception as exc:
        logger.warning("yfinance fetch failed %s (%s) — using fallback/cache", pair, exc)
        if pair in _price_cache:
            return _price_cache[pair][0]
        price = _FALLBACK_PRICES.get(pair, 1.0)

    _price_cache[pair] = (price, now)
    return price

def _get_price(pair: str) -> float:
    """Sync wrapper used by WebSocket handler (already in thread context)."""
    now = time.time()
    if pair in _price_cache:
        price, ts = _price_cache[pair]
        if now - ts < _PRICE_TTL:
            return price
    return _FALLBACK_PRICES.get(pair, 1.0)


def _build_orderbook(pair: str, price: float, levels: int = 15) -> dict:
    """Build synthetic order book levels around the current price."""
    spread = _SPREADS.get(pair, 0.0002)
    pip    = _pip_size(pair)

    mid    = price
    bid0   = mid - spread / 2
    ask0   = mid + spread / 2

    # tick size ≈ 1 pip
    tick   = pip

    # Volume profile: Gaussian-like concentration near mid, tapering away
    def _vol(level_idx: int, total: int) -> int:
        # level_idx 0 = closest to mid, total-1 = furthest
        frac  = level_idx / max(total - 1, 1)
        sigma = 0.35
        w     = math.exp(-0.5 * (frac / sigma) ** 2)
        base  = random.uniform(800_000, 3_500_000)
        return max(100_000, int(base * w * random.uniform(0.7, 1.3)))

    bids, asks = [], []
    bid_cum = ask_cum = 0

    for i in range(levels):
        bp = round(bid0 - tick * i, 6)
        ap = round(ask0 + tick * i, 6)
        bv = _vol(i, levels)
        av = _vol(i, levels)
        bid_cum += bv
        ask_cum += av
        bids.append({"price": bp, "volume": bv, "cumulative": bid_cum})
        asks.append({"price": ap, "volume": av, "cumulative": ask_cum})

    total_bid = bid_cum
    total_ask = ask_cum
    imbalance = round(total_bid / (total_bid + total_ask), 4) if (total_bid + total_ask) > 0 else 0.5

    spread_pips = round(spread / pip, 1)

    return {
        "symbol":        pair,
        "price":         round(mid, 6),
        "bid":           round(bid0, 6),
        "ask":           round(ask0, 6),
        "spread":        round(spread, 6),
        "spread_pips":   spread_pips,
        "bids":          bids,
        "asks":          asks,
        "total_bid_vol": total_bid,
        "total_ask_vol": total_ask,
        "imbalance":     imbalance,
        "updated_at":    datetime.now(IST).isoformat(),
    }


@router.get("/orderbook", summary="Live synthetic order book for forex pair")
async def get_orderbook(
    symbol: str = Query(..., description="Pair e.g. EURUSD or EUR/USD"),
    levels: int = Query(15, ge=5, le=25, description="Depth levels each side"),
) -> dict:
    """
    Return a synthetic order book for the given forex pair.

    Uses real current price from yfinance (with 8s timeout + fallback)
    and generates realistic bid/ask depth based on pair-specific spreads.
    Forex is OTC — true L2 data requires premium broker feeds.
    """
    pair = symbol.upper().replace("-", "/")
    if "/" not in pair and len(pair) == 6:
        pair = pair[:3] + "/" + pair[3:]

    logger.info("Order book requested: %s (%d levels)", pair, levels)
    price = await _get_price_async(pair)
    return _build_orderbook(pair, price, levels)
