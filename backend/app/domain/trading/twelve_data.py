"""
Twelve Data API Client — Real-Time Forex Data
=============================================
Replaces yfinance with Twelve Data for:
  - Real-time prices (no 15-min delay)
  - Reliable OHLCV candle data
  - 15m and 4H timeframes

API Limits (Free tier):
  - 800 credits/day
  - 8 requests/minute

Caching Strategy to save credits:
  - 15m data → cached for 14 minutes
  - 4H  data → cached for 3 hours 50 minutes
  - Estimated daily usage: ~450 calls (well within 800)
"""

from __future__ import annotations

import logging
import os
import time
from datetime import datetime
from typing import Optional

import pandas as pd
import requests

logger = logging.getLogger(__name__)

# ── Config ─────────────────────────────────────────────────────────────────
def _get_key() -> str:
    # Try env var first, then .env file
    key = os.environ.get("TWELVE_DATA_API_KEY", "")
    if not key:
        env_path = os.path.join(os.path.dirname(__file__), "..", "..", "..", ".env")
        env_path = os.path.normpath(env_path)
        if os.path.exists(env_path):
            with open(env_path) as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("TWELVE_DATA_API_KEY="):
                        key = line.split("=", 1)[1].strip()
                        break
    return key

API_KEY = _get_key()
BASE_URL = "https://api.twelvedata.com"

# Pair mapping → Twelve Data uses standard forex notation EUR/USD etc.
FOREX_PAIRS = {
    "EUR/USD": "EUR/USD",
    "GBP/USD": "GBP/USD",
    "USD/JPY": "USD/JPY",
    "AUD/USD": "AUD/USD",
    "USD/CAD": "USD/CAD",
    "NZD/USD": "NZD/USD",
    "USD/CHF": "USD/CHF",
    "GBP/JPY": "GBP/JPY",
    "USD/INR": "USD/INR",
}

INTERVAL_MAP = {
    "15m": "15min",
    "4h":  "4h",
    "1h":  "1h",
    "1d":  "1day",
}

# ── In-memory cache ─────────────────────────────────────────────────────────
_cache: dict[str, tuple[float, pd.DataFrame]] = {}   # key → (timestamp, df)

CACHE_TTL = {
    "15min": 14 * 60,           # 14 minutes
    "4h":    3 * 3600 + 50*60,  # 3h 50m
    "1h":    55 * 60,           # 55 minutes
    "1day":  23 * 3600,         # 23 hours
}


def _cache_key(symbol: str, interval: str) -> str:
    return f"{symbol}|{interval}"


def _from_cache(symbol: str, interval: str) -> Optional[pd.DataFrame]:
    key = _cache_key(symbol, interval)
    if key in _cache:
        ts, df = _cache[key]
        ttl = CACHE_TTL.get(interval, 900)
        if time.time() - ts < ttl:
            logger.debug("Cache HIT %s %s", symbol, interval)
            return df.copy()
        else:
            logger.debug("Cache EXPIRED %s %s", symbol, interval)
    return None


def _to_cache(symbol: str, interval: str, df: pd.DataFrame) -> None:
    _cache[_cache_key(symbol, interval)] = (time.time(), df.copy())


# ── API Call ────────────────────────────────────────────────────────────────

_last_request_time: float = 0.0
_MIN_INTERVAL = 8.0   # seconds between requests (free tier: 8/min)

def _fetch_raw(symbol: str, interval: str, outputsize: int = 500) -> Optional[pd.DataFrame]:
    """
    Call Twelve Data /time_series endpoint with rate limiting + retry.
    Returns a DataFrame with columns: open, high, low, close, volume
    """
    global _last_request_time

    if not API_KEY:
        logger.error("TWELVE_DATA_API_KEY not set!")
        return None

    # Check cache first — avoids hitting API
    cached = _from_cache(symbol, interval)
    if cached is not None:
        return cached

    # Rate limiting — enforce min gap between requests
    wait = _MIN_INTERVAL - (time.time() - _last_request_time)
    if wait > 0:
        logger.debug("Rate limit wait %.1fs for %s %s", wait, symbol, interval)
        time.sleep(wait)

    url = f"{BASE_URL}/time_series"
    params = {
        "symbol":     symbol,
        "interval":   interval,
        "outputsize": outputsize,
        "apikey":     API_KEY,
        "format":     "JSON",
        "order":      "ASC",
    }

    for attempt in range(3):  # retry up to 3 times on 429
        try:
            _last_request_time = time.time()
            logger.info("Twelve Data fetch [attempt %d]: %s %s", attempt + 1, symbol, interval)
            resp = requests.get(url, params=params, timeout=15)

            if resp.status_code == 429:
                wait_retry = 15 * (attempt + 1)
                logger.warning("429 rate limit — waiting %ds before retry", wait_retry)
                time.sleep(wait_retry)
                continue

            resp.raise_for_status()
            data = resp.json()
            break
        except requests.RequestException as e:
            logger.error("Twelve Data request failed %s %s: %s", symbol, interval, e)
            if attempt == 2:
                return None
            time.sleep(5)
            continue
    else:
        return None

    if data.get("status") == "error":
        logger.error("Twelve Data API error %s %s: %s", symbol, interval, data.get("message"))
        return None

    values = data.get("values")
    if not values:
        logger.warning("No values returned for %s %s", symbol, interval)
        return None

    try:
        df = pd.DataFrame(values)
        df["date"] = pd.to_datetime(df["datetime"])
        df = df.set_index("date").sort_index()
        for col in ["open", "high", "low", "close"]:
            df[col] = pd.to_numeric(df[col], errors="coerce")
        if "volume" in df.columns:
            df["volume"] = pd.to_numeric(df["volume"], errors="coerce").fillna(0)
        else:
            df["volume"] = 0
        df = df[["open", "high", "low", "close", "volume"]].dropna(
            subset=["open", "high", "low", "close"]
        )
    except Exception as e:
        logger.error("DataFrame parse error %s %s: %s", symbol, interval, e)
        return None

    if df.empty:
        logger.warning("Empty DataFrame after parse for %s %s", symbol, interval)
        return None

    _to_cache(symbol, interval, df)
    logger.info("Twelve Data OK: %s %s -> %d candles (latest: %s)",
                symbol, interval, len(df), df.index[-1])
    return df


# ── Public Functions ─────────────────────────────────────────────────────────

def fetch_15m(pair: str) -> Optional[pd.DataFrame]:
    """Fetch 15-minute candles for a forex pair (last ~500 candles = ~5 days)."""
    symbol = FOREX_PAIRS.get(pair)
    if not symbol:
        logger.warning("Unknown pair: %s", pair)
        return None
    return _fetch_raw(symbol, "15min", outputsize=500)


def fetch_4h(pair: str) -> Optional[pd.DataFrame]:
    """Fetch 4H candles for a forex pair (last 200 candles = ~33 days)."""
    symbol = FOREX_PAIRS.get(pair)
    if not symbol:
        return None
    return _fetch_raw(symbol, "4h", outputsize=200)


def get_current_price(pair: str) -> Optional[float]:
    """Get current real-time price using /price endpoint (1 credit)."""
    symbol = FOREX_PAIRS.get(pair)
    if not symbol or not API_KEY:
        return None

    cache_key = f"price|{symbol}"
    if cache_key in _cache:
        ts, val = _cache[cache_key]
        if time.time() - ts < 60:  # price cache: 60 sec
            return val  # type: ignore

    try:
        resp = requests.get(
            f"{BASE_URL}/price",
            params={"symbol": symbol, "apikey": API_KEY},
            timeout=10,
        )
        data = resp.json()
        price = float(data.get("price", 0))
        if price > 0:
            _cache[cache_key] = (time.time(), price)
            return price
    except Exception as e:
        logger.error("Price fetch failed %s: %s", pair, e)
    return None


def get_cache_stats() -> dict:
    """Return cache stats for monitoring."""
    now = time.time()
    stats = {}
    for k, (ts, df) in _cache.items():
        age = int(now - ts)
        stats[k] = {"age_seconds": age, "rows": len(df) if isinstance(df, pd.DataFrame) else "price"}
    return stats


def clear_cache() -> None:
    _cache.clear()
    logger.info("Twelve Data cache cleared")


# ── Quick test ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import json
    logging.basicConfig(level=logging.INFO)
    print(f"\nAPI Key loaded: {API_KEY[:8]}...{API_KEY[-4:]}")

    print("\n--- EUR/USD 15m (last 5 candles) ---")
    df = fetch_15m("EUR/USD")
    if df is not None:
        print(df.tail(5).to_string())
    else:
        print("FAILED")

    print("\n--- GBP/USD 4H (last 5 candles) ---")
    df4 = fetch_4h("GBP/USD")
    if df4 is not None:
        print(df4.tail(5).to_string())
    else:
        print("FAILED")

    print("\n--- Current EUR/USD price ---")
    p = get_current_price("EUR/USD")
    print(f"Price: {p}")
