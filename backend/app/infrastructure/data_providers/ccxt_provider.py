"""
Crypto data provider backed by the *ccxt* library.

Supports OHLCV retrieval, live tickers, order-book snapshots,
funding rates, and top-pairs-by-volume queries across any
ccxt-supported exchange (default: Binance).
"""

import logging
import time
from datetime import datetime, timezone
from typing import Any, Optional

import pandas as pd

try:
    import ccxt

    HAS_CCXT = True
except ImportError:
    HAS_CCXT = False

logger = logging.getLogger(__name__)

# Rate-limit: minimum seconds between consecutive requests
_RATE_LIMIT_DELAY: float = 0.35
_last_request_ts: float = 0.0


def _rate_limit() -> None:
    """Throttle requests to respect exchange rate limits."""
    global _last_request_ts
    elapsed = time.monotonic() - _last_request_ts
    if elapsed < _RATE_LIMIT_DELAY:
        time.sleep(_RATE_LIMIT_DELAY - elapsed)
    _last_request_ts = time.monotonic()


class CryptoDataProvider:
    """
    Multi-exchange crypto data provider via *ccxt*.

    Attributes:
        exchange_id: ccxt exchange identifier (e.g. ``"binance"``).
        exchange: initialised ``ccxt.Exchange`` instance (or ``None``).
    """

    def __init__(
        self,
        exchange_id: str = "binance",
        api_key: Optional[str] = None,
        secret: Optional[str] = None,
    ) -> None:
        """
        Initialise the provider.

        Args:
            exchange_id: ccxt exchange name.
            api_key: Exchange API key (optional, read-only access ok).
            secret: Exchange API secret.
        """
        self.exchange_id = exchange_id
        self.exchange: Any = None

        if not HAS_CCXT:
            logger.warning("ccxt not installed — CryptoDataProvider will return empty data")
            return

        try:
            exchange_class = getattr(ccxt, exchange_id)
            config: dict[str, Any] = {
                "enableRateLimit": True,
                "options": {"defaultType": "spot"},
            }
            if api_key:
                config["apiKey"] = api_key
            if secret:
                config["secret"] = secret

            self.exchange = exchange_class(config)
            logger.info("Initialised ccxt exchange: %s", exchange_id)
        except Exception as exc:
            logger.error("Failed to initialise ccxt exchange '%s': %s", exchange_id, exc)
            self.exchange = None

    # ── OHLCV ────────────────────────────────────────────────────────

    def get_ohlcv(
        self,
        symbol: str,
        timeframe: str = "1d",
        limit: int = 500,
    ) -> pd.DataFrame:
        """
        Fetch OHLCV candle data.

        Args:
            symbol: Trading pair (e.g. ``"BTC/USDT"``).
            timeframe: Candle interval (e.g. ``"1m"``, ``"1h"``, ``"1d"``).
            limit: Max number of candles to return.

        Returns:
            DataFrame with ``[timestamp, open, high, low, close, volume]``.
        """
        if self.exchange is None:
            logger.warning("Exchange not initialised — returning empty OHLCV")
            return pd.DataFrame()

        try:
            _rate_limit()
            data = self.exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
            df = pd.DataFrame(data, columns=["timestamp", "open", "high", "low", "close", "volume"])
            df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
            df.set_index("timestamp", inplace=True)
            logger.info("OHLCV %s (%s): %d candles fetched", symbol, timeframe, len(df))
            return df
        except Exception as exc:
            logger.error("Failed to fetch OHLCV for %s: %s", symbol, exc)
            return pd.DataFrame()

    # ── Ticker ───────────────────────────────────────────────────────

    def get_ticker(self, symbol: str) -> dict[str, Any]:
        """
        Get the latest ticker for *symbol*.

        Returns:
            Dict with ``price``, ``volume_24h``, ``change_24h``,
            ``change_pct_24h``, ``high_24h``, ``low_24h``, ``bid``, ``ask``.
        """
        if self.exchange is None:
            return {"symbol": symbol, "error": "exchange not initialised"}

        try:
            _rate_limit()
            t = self.exchange.fetch_ticker(symbol)
            ticker = {
                "symbol": symbol,
                "price": t.get("last", 0.0),
                "volume_24h": t.get("quoteVolume") or t.get("baseVolume", 0.0),
                "change_24h": t.get("change", 0.0),
                "change_pct_24h": t.get("percentage", 0.0),
                "high_24h": t.get("high", 0.0),
                "low_24h": t.get("low", 0.0),
                "bid": t.get("bid", 0.0),
                "ask": t.get("ask", 0.0),
                "timestamp": t.get("datetime"),
            }
            logger.debug("Ticker %s: $%.2f", symbol, ticker["price"])
            return ticker
        except Exception as exc:
            logger.error("Ticker fetch failed for %s: %s", symbol, exc)
            return {"symbol": symbol, "error": str(exc)}

    # ── Order book ───────────────────────────────────────────────────

    def get_order_book(self, symbol: str, limit: int = 20) -> dict[str, Any]:
        """
        Fetch the current order-book snapshot.

        Args:
            symbol: Trading pair.
            limit: Number of levels per side.

        Returns:
            Dict with ``bids`` and ``asks``, each a list of
            ``[price, quantity]`` pairs.
        """
        if self.exchange is None:
            return {"symbol": symbol, "bids": [], "asks": []}

        try:
            _rate_limit()
            book = self.exchange.fetch_order_book(symbol, limit=limit)
            result = {
                "symbol": symbol,
                "bids": book.get("bids", [])[:limit],
                "asks": book.get("asks", [])[:limit],
                "timestamp": book.get("datetime"),
                "bid_depth": sum(qty for _, qty in book.get("bids", [])[:limit]),
                "ask_depth": sum(qty for _, qty in book.get("asks", [])[:limit]),
            }
            logger.debug(
                "Order book %s: %d bids, %d asks",
                symbol, len(result["bids"]), len(result["asks"]),
            )
            return result
        except Exception as exc:
            logger.error("Order book fetch failed for %s: %s", symbol, exc)
            return {"symbol": symbol, "bids": [], "asks": [], "error": str(exc)}

    # ── Funding rate ─────────────────────────────────────────────────

    def get_funding_rate(self, symbol: str) -> float:
        """
        Get the current funding rate for a perpetual futures pair.

        Args:
            symbol: Trading pair (e.g. ``"BTC/USDT"``).

        Returns:
            Funding rate as a float (e.g. 0.0001 for 0.01 %).
            Returns ``0.0`` on error.
        """
        if self.exchange is None:
            return 0.0

        try:
            _rate_limit()
            # Use futures-specific API if exchange supports it
            if hasattr(self.exchange, "fetch_funding_rate"):
                fr = self.exchange.fetch_funding_rate(symbol)
                rate = fr.get("fundingRate", 0.0) or 0.0
            else:
                logger.debug("Exchange %s does not support funding rate", self.exchange_id)
                rate = 0.0

            logger.debug("Funding rate %s: %.6f", symbol, rate)
            return float(rate)
        except Exception as exc:
            logger.error("Funding rate fetch failed for %s: %s", symbol, exc)
            return 0.0

    # ── Top pairs by volume ──────────────────────────────────────────

    def get_top_pairs(self, limit: int = 20) -> list[dict[str, Any]]:
        """
        Return the top trading pairs ranked by 24 h quote volume.

        Args:
            limit: Number of pairs to return.

        Returns:
            List of ticker dicts sorted by volume descending.
        """
        if self.exchange is None:
            return []

        try:
            _rate_limit()
            tickers: dict = self.exchange.fetch_tickers()
            pairs: list[dict[str, Any]] = []

            for sym, t in tickers.items():
                # Only include USDT-quoted spot pairs for consistency
                if "/USDT" not in sym:
                    continue
                pairs.append({
                    "symbol": sym,
                    "price": t.get("last", 0.0),
                    "volume_24h": t.get("quoteVolume") or t.get("baseVolume", 0.0),
                    "change_pct_24h": t.get("percentage", 0.0),
                })

            # Sort by 24h volume descending
            pairs.sort(key=lambda p: p.get("volume_24h", 0) or 0, reverse=True)
            top = pairs[:limit]
            logger.info("Top %d pairs by volume fetched (%s)", len(top), self.exchange_id)
            return top

        except Exception as exc:
            logger.error("Failed to fetch top pairs: %s", exc)
            return []
