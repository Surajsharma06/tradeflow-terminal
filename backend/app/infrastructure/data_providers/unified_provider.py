"""
Unified Data Provider
=====================
Priority order:
  1. Twelve Data  — forex pairs  (fast, real-time, no delay)
  2. yfinance     — Indian stocks, crypto, fallback for anything else

Usage:
    from app.infrastructure.data_providers.unified_provider import UnifiedProvider
    df = UnifiedProvider().get_ohlcv("EUR/USD", period="60d", interval="1h")
    df = UnifiedProvider().get_ohlcv("RELIANCE", period="1y",  interval="1d", exchange="NSE")
"""

from __future__ import annotations

import logging
import time
import warnings
from typing import Optional

import pandas as pd

logger = logging.getLogger(__name__)

# ── Twelve Data pairs that are supported ─────────────────────────────────────
_TWELVE_FOREX = {
    "EUR/USD", "GBP/USD", "USD/JPY", "USD/CHF", "AUD/USD",
    "USD/CAD", "NZD/USD", "EUR/GBP", "EUR/JPY", "EUR/AUD",
    "EUR/CAD", "EUR/CHF", "EUR/NZD", "GBP/JPY", "GBP/AUD",
    "GBP/CAD", "GBP/CHF", "GBP/NZD", "AUD/CAD", "AUD/CHF",
    "AUD/JPY", "AUD/NZD", "CAD/CHF", "CAD/JPY", "CHF/JPY",
    "NZD/CAD", "NZD/CHF", "NZD/JPY", "XAU/USD", "XAG/USD",
}

_TD_INTERVAL_MAP = {
    "1m":  "1min",  "5m":  "5min",  "15m": "15min", "30m": "30min",
    "1h":  "1h",    "4h":  "4h",    "1d":  "1day",  "1w":  "1week",
}


class UnifiedProvider:
    """Single interface for all market data — Twelve Data or yfinance."""

    def __init__(self) -> None:
        self._td_key = self._load_td_key()
        self._td_cache: dict[str, tuple[float, pd.DataFrame]] = {}

    # ── Public API ────────────────────────────────────────────────────────────

    def get_ohlcv(
        self,
        symbol: str,
        period: str = "90d",
        interval: str = "1d",
        exchange: Optional[str] = None,
    ) -> pd.DataFrame:
        """
        Fetch OHLCV data for any symbol.
        Returns DataFrame with lowercase columns: open, high, low, close, volume
        """
        pair_clean = symbol.upper().replace("-", "/")

        if pair_clean in _TWELVE_FOREX and self._td_key:
            df = self._fetch_twelve(pair_clean, interval, period)
            if df is not None and not df.empty and self._is_valid(df):
                logger.info("Twelve Data OK: %s %s → %d rows", pair_clean, interval, len(df))
                return df
            logger.warning("Twelve Data bad/failed for %s — falling back to yfinance", pair_clean)

        return self._fetch_yfinance(symbol, period, interval, exchange)

    def get_price(self, symbol: str) -> Optional[float]:
        """Current price — Twelve Data for forex, yfinance otherwise."""
        pair_clean = symbol.upper().replace("-", "/")
        if pair_clean in _TWELVE_FOREX and self._td_key:
            price = self._td_price(pair_clean)
            if price:
                return price
        return self._yf_price(symbol)

    # ── Twelve Data internals ─────────────────────────────────────────────────

    def _fetch_twelve(
        self, pair: str, interval: str, period: str
    ) -> Optional[pd.DataFrame]:
        import requests

        td_interval = _TD_INTERVAL_MAP.get(interval, "1day")
        outputsize  = self._period_to_bars(period, interval)
        cache_key   = f"{pair}|{td_interval}"

        # Cache check
        ttl = {"1min": 60, "5min": 300, "15min": 840, "30min": 1740,
               "1h": 3300, "4h": 13800, "1day": 82800}.get(td_interval, 900)
        if cache_key in self._td_cache:
            ts, df = self._td_cache[cache_key]
            if time.time() - ts < ttl:
                return df.copy()

        url = "https://api.twelvedata.com/time_series"
        params = {
            "symbol":     pair,
            "interval":   td_interval,
            "outputsize": min(outputsize, 5000),
            "apikey":     self._td_key,
            "format":     "JSON",
            "order":      "ASC",
        }
        try:
            resp = requests.get(url, params=params, timeout=15)
            data = resp.json()
            if data.get("status") == "error":
                logger.error("Twelve Data error: %s", data.get("message"))
                return None
            values = data.get("values", [])
            if not values:
                return None

            df = pd.DataFrame(values)
            df.index = pd.to_datetime(df["datetime"])
            df.index.name = "date"
            df = df.sort_index()
            for col in ["open", "high", "low", "close"]:
                df[col] = pd.to_numeric(df[col], errors="coerce")
            df["volume"] = pd.to_numeric(df.get("volume", 0), errors="coerce").fillna(0)
            df = df[["open", "high", "low", "close", "volume"]].dropna()

            self._td_cache[cache_key] = (time.time(), df.copy())
            return df
        except Exception as e:
            logger.error("Twelve Data fetch error %s: %s", pair, e)
            return None

    def _td_price(self, pair: str) -> Optional[float]:
        import requests
        try:
            resp = requests.get(
                "https://api.twelvedata.com/price",
                params={"symbol": pair, "apikey": self._td_key},
                timeout=8,
            )
            price = float(resp.json().get("price", 0))
            return price if price > 0 else None
        except Exception:
            return None

    # ── yfinance internals ────────────────────────────────────────────────────

    def _fetch_yfinance(
        self, symbol: str, period: str, interval: str, exchange: Optional[str]
    ) -> pd.DataFrame:
        try:
            import yfinance as yf
            warnings.filterwarnings("ignore")
            ticker = self._normalize_yf(symbol, exchange)
            df = yf.download(ticker, period=period, interval=interval,
                             auto_adjust=True, progress=False)
            if df.empty:
                return pd.DataFrame()
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = [c[0].lower() for c in df.columns]
            else:
                df.columns = [c.lower() for c in df.columns]
            df["volume"] = df.get("volume", pd.Series(0, index=df.index)).fillna(0)
            df = df[["open", "high", "low", "close", "volume"]].dropna(subset=["close"])
            logger.info("yfinance OK: %s %s → %d rows", ticker, interval, len(df))
            return df
        except Exception as e:
            logger.error("yfinance error %s: %s", symbol, e)
            return pd.DataFrame()

    def _yf_price(self, symbol: str) -> Optional[float]:
        try:
            import yfinance as yf
            warnings.filterwarnings("ignore")
            tk = yf.Ticker(symbol)
            info = tk.info or {}
            return info.get("regularMarketPrice") or info.get("currentPrice")
        except Exception:
            return None

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _normalize_yf(symbol: str, exchange: Optional[str]) -> str:
        s = symbol.strip().upper()
        if "/" in s:
            base, quote = s.split("/", 1)
            return f"{base}-{quote}"
        if exchange == "NSE" and not s.endswith(".NS"):
            return s + ".NS"
        if exchange == "BSE" and not s.endswith(".BO"):
            return s + ".BO"
        return s

    @staticmethod
    def _period_to_bars(period: str, interval: str) -> int:
        days_map = {"1d": 1, "5d": 5, "1mo": 30, "3mo": 90, "6mo": 180,
                    "1y": 365, "2y": 730, "5y": 1825}
        if period.endswith("d"):
            days = int(period[:-1])
        else:
            days = days_map.get(period, 90)
        bars_per_day = {"1m": 390, "5m": 78, "15m": 26, "30m": 13,
                        "1h": 6, "4h": 2, "1d": 1, "1w": 0.2}.get(interval, 1)
        return max(100, min(int(days * bars_per_day), 5000))

    @staticmethod
    def _is_valid(df: pd.DataFrame) -> bool:
        """Reject data where all prices are identical (bad API response)."""
        if df.empty:
            return False
        price_std = df["close"].std()
        if price_std < 1e-8:
            logger.warning("Data rejected: all close prices identical (std=%.2e)", price_std)
            return False
        return True

    @staticmethod
    def _load_td_key() -> str:
        import os
        key = os.environ.get("TWELVE_DATA_API_KEY", "")
        if not key:
            import pathlib
            for env_path in [
                pathlib.Path(__file__).parents[5] / ".env",
                pathlib.Path(__file__).parents[4] / ".env",
            ]:
                if env_path.exists():
                    for line in env_path.read_text().splitlines():
                        if line.startswith("TWELVE_DATA_API_KEY="):
                            key = line.split("=", 1)[1].strip()
                            break
        return key
