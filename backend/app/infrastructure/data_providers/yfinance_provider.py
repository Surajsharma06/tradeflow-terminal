"""
yfinance data provider for the Trading System.

Provides historical OHLCV data, live quotes, multi-symbol quotes,
options chains, and symbol search via the yfinance library.
Handles NSE (.NS), BSE (.BO), US, and crypto symbol normalization.
"""

import logging
import time
from typing import Any, Optional

import pandas as pd

try:
    import yfinance as yf

    HAS_YFINANCE = True
except ImportError:
    HAS_YFINANCE = False

logger = logging.getLogger(__name__)

# Minimum delay between consecutive yfinance requests (seconds)
_RATE_LIMIT_DELAY: float = 0.25
_last_request_ts: float = 0.0


def _rate_limit() -> None:
    """Enforce a minimum delay between consecutive yfinance API calls."""
    global _last_request_ts
    elapsed = time.monotonic() - _last_request_ts
    if elapsed < _RATE_LIMIT_DELAY:
        time.sleep(_RATE_LIMIT_DELAY - elapsed)
    _last_request_ts = time.monotonic()


class YFinanceProvider:
    """
    Data provider backed by the *yfinance* library.

    Supports Indian (NSE / BSE), US equity, and crypto markets.
    All public methods are synchronous because yfinance itself is
    synchronous; callers in async contexts should wrap with
    ``asyncio.to_thread``.
    """

    # ── Symbol normalisation helpers ─────────────────────────────────

    EXCHANGE_SUFFIXES: dict[str, str] = {
        "NSE": ".NS",
        "BSE": ".BO",
    }

    CRYPTO_QUOTE_CURRENCIES = ("USDT", "USD", "INR", "EUR", "BTC")

    @staticmethod
    def normalize_symbol(
        symbol: str,
        exchange: Optional[str] = None,
    ) -> str:
        """
        Return a yfinance-compatible ticker symbol.

        Args:
            symbol: Raw symbol string (e.g. ``"RELIANCE"``, ``"BTC/USDT"``).
            exchange: Optional exchange hint (``"NSE"``, ``"BSE"``).

        Returns:
            Normalised symbol (e.g. ``"RELIANCE.NS"``, ``"BTC-USD"``).
        """
        symbol = symbol.strip().upper()

        # Already has a suffix → leave it
        if "." in symbol and symbol.rsplit(".", 1)[-1] in ("NS", "BO"):
            return symbol

        # Crypto: convert slash notation to yfinance dash notation
        if "/" in symbol:
            base, quote = symbol.split("/", 1)
            return f"{base}-{quote}"

        # Explicit exchange hint
        if exchange:
            suffix = YFinanceProvider.EXCHANGE_SUFFIXES.get(exchange.upper(), "")
            return f"{symbol}{suffix}"

        return symbol

    # ── Historical data ──────────────────────────────────────────────

    def get_historical_data(
        self,
        symbol: str,
        period: str = "5y",
        interval: str = "1d",
        exchange: Optional[str] = None,
    ) -> pd.DataFrame:
        """
        Fetch historical OHLCV data.

        Args:
            symbol: Ticker symbol.
            period: Lookback period (yfinance format, e.g. ``"5y"``, ``"1mo"``).
            interval: Bar interval (e.g. ``"1d"``, ``"1h"``).
            exchange: Exchange hint for symbol normalisation.

        Returns:
            ``pandas.DataFrame`` with columns
            ``[Open, High, Low, Close, Volume]``.
        """
        if not HAS_YFINANCE:
            logger.warning("yfinance not installed — returning empty DataFrame")
            return pd.DataFrame()

        ticker = self.normalize_symbol(symbol, exchange)
        logger.info(
            "Fetching historical data: %s  period=%s  interval=%s",
            ticker, period, interval,
        )
        try:
            _rate_limit()
            tk = yf.Ticker(ticker)
            df: pd.DataFrame = tk.history(period=period, interval=interval)
            if df.empty:
                logger.warning("No data returned for %s", ticker)
            else:
                logger.info(
                    "Received %d bars for %s (%s → %s)",
                    len(df), ticker,
                    df.index[0].strftime("%Y-%m-%d"),
                    df.index[-1].strftime("%Y-%m-%d"),
                )
            return df
        except Exception as exc:
            logger.error("Failed to fetch historical data for %s: %s", ticker, exc)
            return pd.DataFrame()

    # ── Live quote ───────────────────────────────────────────────────

    def get_live_quote(
        self,
        symbol: str,
        exchange: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Get the latest quote for a single symbol.

        Returns:
            Dict with keys ``price``, ``change``, ``change_pct``,
            ``volume``, ``day_high``, ``day_low``, ``open``,
            ``previous_close``, ``market_cap``, ``symbol``.
        """
        if not HAS_YFINANCE:
            logger.warning("yfinance not installed — returning empty quote")
            return {}

        ticker = self.normalize_symbol(symbol, exchange)
        try:
            _rate_limit()
            tk = yf.Ticker(ticker)
            info: dict = tk.info or {}

            current_price = (
                info.get("regularMarketPrice")
                or info.get("currentPrice")
                or info.get("previousClose", 0.0)
            )
            prev_close = info.get("previousClose") or info.get("regularMarketPreviousClose", 0.0)
            change = round(current_price - prev_close, 2) if current_price and prev_close else 0.0
            change_pct = round((change / prev_close) * 100, 2) if prev_close else 0.0

            quote = {
                "symbol": ticker,
                "price": current_price,
                "change": change,
                "change_pct": change_pct,
                "volume": info.get("regularMarketVolume", 0),
                "day_high": info.get("dayHigh", 0.0),
                "day_low": info.get("dayLow", 0.0),
                "open": info.get("regularMarketOpen", 0.0),
                "previous_close": prev_close,
                "market_cap": info.get("marketCap"),
                "fifty_two_week_high": info.get("fiftyTwoWeekHigh"),
                "fifty_two_week_low": info.get("fiftyTwoWeekLow"),
            }
            logger.debug("Quote for %s: ₹%.2f (%.2f%%)", ticker, current_price, change_pct)
            return quote

        except Exception as exc:
            logger.error("Failed to fetch quote for %s: %s", ticker, exc)
            return {"symbol": ticker, "error": str(exc)}

    # ── Multiple quotes ──────────────────────────────────────────────

    def get_multiple_quotes(
        self,
        symbols: list[str],
        exchange: Optional[str] = None,
    ) -> dict[str, dict[str, Any]]:
        """
        Fetch live quotes for multiple symbols at once.

        Args:
            symbols: List of raw symbol strings.
            exchange: Exchange hint applied to every symbol.

        Returns:
            ``{symbol: quote_dict, ...}``
        """
        results: dict[str, dict[str, Any]] = {}
        for sym in symbols:
            results[sym] = self.get_live_quote(sym, exchange)
        return results

    # ── Options chain ────────────────────────────────────────────────

    def get_options_chain(
        self,
        symbol: str,
        exchange: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Retrieve the options chain (nearest expiry) for *symbol*.

        Returns:
            Dict with ``expiry_dates``, ``calls`` (list[dict]),
            ``puts`` (list[dict]) including IV and Open Interest.
        """
        if not HAS_YFINANCE:
            logger.warning("yfinance not installed — returning empty options chain")
            return {}

        ticker = self.normalize_symbol(symbol, exchange)
        try:
            _rate_limit()
            tk = yf.Ticker(ticker)
            expiry_dates: tuple[str, ...] = tk.options  # type: ignore[assignment]
            if not expiry_dates:
                logger.warning("No options data for %s", ticker)
                return {"symbol": ticker, "expiry_dates": [], "calls": [], "puts": []}

            nearest = expiry_dates[0]
            chain = tk.option_chain(nearest)

            def _chain_to_records(df: pd.DataFrame) -> list[dict[str, Any]]:
                cols = [
                    "contractSymbol", "strike", "lastPrice",
                    "bid", "ask", "volume", "openInterest", "impliedVolatility",
                ]
                available = [c for c in cols if c in df.columns]
                return df[available].to_dict(orient="records")

            result = {
                "symbol": ticker,
                "expiry_dates": list(expiry_dates),
                "selected_expiry": nearest,
                "calls": _chain_to_records(chain.calls),
                "puts": _chain_to_records(chain.puts),
            }
            logger.info(
                "Options chain for %s (expiry %s): %d calls, %d puts",
                ticker, nearest, len(result["calls"]), len(result["puts"]),
            )
            return result

        except Exception as exc:
            logger.error("Failed to fetch options chain for %s: %s", ticker, exc)
            return {"symbol": ticker, "error": str(exc)}

    # ── Symbol search ────────────────────────────────────────────────

    def search_symbol(self, query: str) -> list[dict[str, str]]:
        """
        Search for ticker symbols matching *query*.

        Returns:
            List of dicts with ``symbol``, ``name``, ``exchange``, ``type``.
        """
        if not HAS_YFINANCE:
            return []

        try:
            _rate_limit()
            # yfinance ≥ 0.2.31 exposes a search helper
            if hasattr(yf, "Search"):
                search = yf.Search(query)
                quotes = getattr(search, "quotes", [])
            else:
                # Fallback: return the query itself as a single result
                return [{"symbol": query.upper(), "name": query, "exchange": "unknown", "type": "equity"}]

            results: list[dict[str, str]] = []
            for q in quotes:
                results.append({
                    "symbol": q.get("symbol", ""),
                    "name": q.get("shortname") or q.get("longname", ""),
                    "exchange": q.get("exchange", ""),
                    "type": q.get("quoteType", "equity").lower(),
                })
            logger.debug("Symbol search '%s' → %d results", query, len(results))
            return results

        except Exception as exc:
            logger.error("Symbol search failed for '%s': %s", query, exc)
            return []
