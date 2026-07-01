"""
Alpha Vantage data provider for forex and commodity data.

Returns realistic mock data when no API key is configured,
allowing the rest of the system to operate in demo mode.
"""

import logging
import random
import time
from datetime import datetime, timedelta
from typing import Any, Optional
from zoneinfo import ZoneInfo

import pandas as pd

try:
    import httpx

    HAS_HTTPX = True
except ImportError:
    HAS_HTTPX = False

from app.core.config import get_settings

logger = logging.getLogger(__name__)

IST = ZoneInfo("Asia/Kolkata")

_BASE_URL = "https://www.alphavantage.co/query"
_RATE_LIMIT_DELAY: float = 1.2  # Alpha Vantage free tier: 5 req/min
_last_request_ts: float = 0.0

# Realistic base rates for mock data
_MOCK_RATES: dict[str, float] = {
    "USD/INR": 83.45,
    "EUR/INR": 91.20,
    "GBP/INR": 106.30,
    "JPY/INR": 0.535,
    "EUR/USD": 1.093,
    "GBP/USD": 1.274,
    "USD/JPY": 155.8,
    "AUD/USD": 0.658,
}

_MOCK_COMMODITIES: dict[str, float] = {
    "GOLD": 2350.0,
    "SILVER": 28.50,
    "CRUDEOIL": 78.20,
    "NATURALGAS": 2.45,
    "COPPER": 4.52,
}


def _rate_limit() -> None:
    """Enforce minimum delay between Alpha Vantage API calls."""
    global _last_request_ts
    elapsed = time.monotonic() - _last_request_ts
    if elapsed < _RATE_LIMIT_DELAY:
        time.sleep(_RATE_LIMIT_DELAY - elapsed)
    _last_request_ts = time.monotonic()


class AlphaVantageProvider:
    """
    Data provider using the Alpha Vantage REST API.

    Falls back to mock data when:
    * No ``ALPHA_VANTAGE_KEY`` is configured, or
    * ``httpx`` is not installed, or
    * The API call fails.
    """

    def __init__(self) -> None:
        """Initialise with API key from settings (if available)."""
        settings = get_settings()
        self._api_key: Optional[str] = settings.alpha_vantage_key
        if not self._api_key:
            logger.info("Alpha Vantage API key not set — mock data will be used")

    @property
    def _is_live(self) -> bool:
        """True if we have an API key and httpx is available."""
        return bool(self._api_key) and HAS_HTTPX

    def _fetch(self, params: dict[str, str]) -> Optional[dict]:
        """
        Make a request to Alpha Vantage.

        Returns:
            Parsed JSON dict on success, ``None`` on failure.
        """
        if not self._is_live:
            return None

        params["apikey"] = self._api_key  # type: ignore[assignment]
        try:
            _rate_limit()
            with httpx.Client(timeout=15) as client:
                resp = client.get(_BASE_URL, params=params)
                resp.raise_for_status()
                data = resp.json()

            # Alpha Vantage returns error messages inside JSON
            if "Error Message" in data or "Note" in data:
                logger.warning("Alpha Vantage API error: %s", data.get("Error Message") or data.get("Note"))
                return None

            return data
        except Exception as exc:
            logger.error("Alpha Vantage request failed: %s", exc)
            return None

    # ── Forex rate ───────────────────────────────────────────────────

    def get_forex_rate(
        self,
        from_currency: str,
        to_currency: str,
    ) -> dict[str, Any]:
        """
        Get the latest exchange rate for a currency pair.

        Args:
            from_currency: Base currency (e.g. ``"USD"``).
            to_currency: Quote currency (e.g. ``"INR"``).

        Returns:
            Dict with ``from``, ``to``, ``rate``, ``bid``, ``ask``,
            ``timestamp``.
        """
        pair_key = f"{from_currency.upper()}/{to_currency.upper()}"

        # Try live API
        data = self._fetch({
            "function": "CURRENCY_EXCHANGE_RATE",
            "from_currency": from_currency,
            "to_currency": to_currency,
        })

        if data and "Realtime Currency Exchange Rate" in data:
            info = data["Realtime Currency Exchange Rate"]
            rate = float(info.get("5. Exchange Rate", 0))
            bid = float(info.get("8. Bid Price", rate))
            ask = float(info.get("9. Ask Price", rate))
            return {
                "from": from_currency.upper(),
                "to": to_currency.upper(),
                "rate": rate,
                "bid": bid,
                "ask": ask,
                "timestamp": info.get("6. Last Refreshed"),
            }

        # Mock fallback
        base_rate = _MOCK_RATES.get(pair_key, 1.0)
        jitter = base_rate * random.uniform(-0.002, 0.002)
        rate = round(base_rate + jitter, 4)
        spread = round(rate * 0.0003, 4)

        logger.debug("Mock forex rate %s: %.4f", pair_key, rate)
        return {
            "from": from_currency.upper(),
            "to": to_currency.upper(),
            "rate": rate,
            "bid": round(rate - spread, 4),
            "ask": round(rate + spread, 4),
            "timestamp": datetime.now(IST).isoformat(),
            "mock": True,
        }

    # ── Forex daily OHLCV ────────────────────────────────────────────

    def get_forex_daily(
        self,
        from_currency: str,
        to_currency: str,
        period: str = "5y",
    ) -> pd.DataFrame:
        """
        Get daily OHLCV forex data.

        Args:
            from_currency: Base currency.
            to_currency: Quote currency.
            period: ``"5y"`` (full) or ``"compact"`` (~100 days).

        Returns:
            DataFrame indexed by date with ``[open, high, low, close]``.
        """
        output_size = "full" if period in ("5y", "full") else "compact"

        data = self._fetch({
            "function": "FX_DAILY",
            "from_symbol": from_currency,
            "to_symbol": to_currency,
            "outputsize": output_size,
        })

        if data and "Time Series FX (Daily)" in data:
            ts = data["Time Series FX (Daily)"]
            records = []
            for date_str, vals in ts.items():
                records.append({
                    "date": date_str,
                    "open": float(vals["1. open"]),
                    "high": float(vals["2. high"]),
                    "low": float(vals["3. low"]),
                    "close": float(vals["4. close"]),
                })
            df = pd.DataFrame(records)
            df["date"] = pd.to_datetime(df["date"])
            df.set_index("date", inplace=True)
            df.sort_index(inplace=True)
            logger.info("Forex daily %s/%s: %d bars", from_currency, to_currency, len(df))
            return df

        # Mock fallback — generate synthetic daily data
        return self._generate_mock_ohlcv(
            f"{from_currency}/{to_currency}",
            _MOCK_RATES.get(f"{from_currency.upper()}/{to_currency.upper()}", 1.0),
            days=365 * 5 if period in ("5y", "full") else 100,
        )

    # ── Commodity data ───────────────────────────────────────────────

    def get_commodity_data(self, commodity: str) -> pd.DataFrame:
        """
        Get daily price data for a commodity.

        Args:
            commodity: Commodity name (e.g. ``"GOLD"``, ``"CRUDEOIL"``).

        Returns:
            DataFrame indexed by date with ``[open, high, low, close]``.
        """
        # Alpha Vantage commodity functions
        function_map: dict[str, str] = {
            "GOLD": "GOLD",
            "SILVER": "SILVER",
            "CRUDEOIL": "WTI",
            "NATURALGAS": "NATURAL_GAS",
            "COPPER": "COPPER",
            "ALUMINIUM": "ALUMINUM",
        }
        av_function = function_map.get(commodity.upper())
        if not av_function:
            logger.warning("Unknown commodity '%s' — returning mock data", commodity)
            base = _MOCK_COMMODITIES.get(commodity.upper(), 100.0)
            return self._generate_mock_ohlcv(commodity, base, days=365 * 2)

        data = self._fetch({
            "function": av_function,
            "interval": "daily",
        })

        if data and "data" in data:
            records = []
            for entry in data["data"]:
                if entry.get("value") and entry["value"] != ".":
                    records.append({
                        "date": entry["date"],
                        "close": float(entry["value"]),
                    })
            if records:
                df = pd.DataFrame(records)
                df["date"] = pd.to_datetime(df["date"])
                df.set_index("date", inplace=True)
                df.sort_index(inplace=True)
                # Alpha Vantage commodity API only returns close prices
                df["open"] = df["close"]
                df["high"] = df["close"] * 1.005
                df["low"] = df["close"] * 0.995
                logger.info("Commodity %s: %d data points", commodity, len(df))
                return df

        # Mock fallback
        base = _MOCK_COMMODITIES.get(commodity.upper(), 100.0)
        return self._generate_mock_ohlcv(commodity, base, days=365 * 2)

    # ── Mock data generator ──────────────────────────────────────────

    @staticmethod
    def _generate_mock_ohlcv(
        label: str,
        base_price: float,
        days: int = 365,
    ) -> pd.DataFrame:
        """
        Generate synthetic daily OHLCV data using a random walk.

        Args:
            label: Label for logging.
            base_price: Starting price.
            days: Number of trading days to generate.

        Returns:
            DataFrame with ``[open, high, low, close, volume]``.
        """
        dates = pd.bdate_range(
            end=datetime.now(IST).date(),
            periods=days,
        )
        price = base_price
        records: list[dict[str, Any]] = []

        for dt in dates:
            daily_return = random.gauss(0.0002, 0.012)
            open_price = price
            close_price = round(price * (1 + daily_return), 4)
            high_price = round(max(open_price, close_price) * (1 + abs(random.gauss(0, 0.005))), 4)
            low_price = round(min(open_price, close_price) * (1 - abs(random.gauss(0, 0.005))), 4)
            volume = random.randint(100_000, 5_000_000)

            records.append({
                "date": dt,
                "open": open_price,
                "high": high_price,
                "low": low_price,
                "close": close_price,
                "volume": volume,
            })
            price = close_price

        df = pd.DataFrame(records).set_index("date")
        logger.debug("Generated %d mock OHLCV bars for %s", len(df), label)
        return df
