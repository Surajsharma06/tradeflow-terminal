"""
Zerodha Kite Connect broker integration.

Implements ``BrokerInterface`` using the ``kiteconnect`` Python library.
Returns mock data when API credentials are not configured, allowing the
system to operate in demo mode.

.. warning::
    Zerodha Kite Connect requires a **static IP whitelist** for production
    API access.  Ensure your server IP is added in the Kite developer
    console before going live.
"""

import logging
import time
from datetime import datetime
from typing import Any, Optional
from zoneinfo import ZoneInfo

from app.core.config import get_settings
from app.infrastructure.brokers.base import (
    BrokerInterface,
    OrderResult,
    OrderStatus,
)

try:
    from kiteconnect import KiteConnect

    HAS_KITE = True
except ImportError:
    HAS_KITE = False

logger = logging.getLogger(__name__)

IST = ZoneInfo("Asia/Kolkata")

# Rate limiting: Kite allows ~10 requests/second
_RATE_LIMIT_DELAY: float = 0.12
_last_request_ts: float = 0.0


def _rate_limit() -> None:
    """Enforce rate limiting for Kite API calls."""
    global _last_request_ts
    elapsed = time.monotonic() - _last_request_ts
    if elapsed < _RATE_LIMIT_DELAY:
        time.sleep(_RATE_LIMIT_DELAY - elapsed)
    _last_request_ts = time.monotonic()


class ZerodhaBroker(BrokerInterface):
    """
    Zerodha Kite Connect broker implementation.

    Uses the official ``kiteconnect`` library for order placement,
    position queries, and margin checks.  When credentials are
    absent, every method returns mock data.

    **Static IP Warning**: Kite Connect mandates IP whitelisting
    for production.  Add your server IP at
    https://developers.kite.trade/.
    """

    # Kite order type mapping
    _ORDER_TYPE_MAP: dict[str, str] = {
        "MARKET": "MARKET",
        "LIMIT": "LIMIT",
        "SL": "SL",
        "SL-M": "SL-M",
    }

    _DIRECTION_MAP: dict[str, str] = {
        "BUY": "BUY",
        "SELL": "SELL",
    }

    def __init__(self) -> None:
        """Initialise with credentials from settings."""
        settings = get_settings()
        self._api_key = settings.kite_api_key
        self._api_secret = settings.kite_api_secret
        self._access_token = settings.kite_access_token

        self._kite: Any = None
        self._is_mock: bool = True

        if not all([self._api_key, self._api_secret]):
            logger.info(
                "Kite API credentials not configured — "
                "ZerodhaBroker will return mock data"
            )
        elif not HAS_KITE:
            logger.warning(
                "kiteconnect library not installed — "
                "ZerodhaBroker will return mock data"
            )

    # ── Connection ───────────────────────────────────────────────────

    def connect(self) -> bool:
        """
        Connect to Kite API using the configured access token.

        Returns:
            ``True`` on success or when running in mock mode.
        """
        if not HAS_KITE or not self._api_key:
            logger.info("ZerodhaBroker connected (mock mode)")
            self._is_mock = True
            return True

        try:
            self._kite = KiteConnect(api_key=self._api_key)
            if self._access_token:
                self._kite.set_access_token(self._access_token)
                # Validate session
                profile = self._kite.profile()
                logger.info(
                    "ZerodhaBroker connected — user: %s",
                    profile.get("user_id", "unknown"),
                )
                self._is_mock = False
                return True
            else:
                logger.warning(
                    "Kite access token not set — login via "
                    "request_token flow required"
                )
                self._is_mock = True
                return True
        except Exception as exc:
            logger.error("Kite connection failed: %s", exc)
            self._is_mock = True
            return False

    def disconnect(self) -> None:
        """Invalidate the Kite session."""
        if self._kite and not self._is_mock:
            try:
                self._kite.invalidate_access_token()
                logger.info("Kite session invalidated")
            except Exception as exc:
                logger.warning("Kite disconnect error: %s", exc)
        self._kite = None
        logger.info("ZerodhaBroker disconnected")

    # ── Order placement ──────────────────────────────────────────────

    def place_order(
        self,
        symbol: str,
        direction: str,
        quantity: int,
        price: Optional[float] = None,
        order_type: str = "MARKET",
        product: str = "CNC",
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
    ) -> OrderResult:
        """Place an order via Kite Connect (or return mock result)."""
        now = datetime.now(IST)
        direction = direction.upper()

        logger.info(
            "Placing Kite order: %s %d %s @ %s (%s)",
            direction, quantity, symbol, price or "MARKET", order_type,
        )

        if self._is_mock:
            return self._mock_order(symbol, direction, quantity, price, order_type, now)

        try:
            _rate_limit()
            kite_order_type = self._ORDER_TYPE_MAP.get(order_type, "MARKET")
            params: dict[str, Any] = {
                "tradingsymbol": symbol,
                "exchange": "NSE",
                "transaction_type": self._DIRECTION_MAP.get(direction, "BUY"),
                "quantity": quantity,
                "order_type": kite_order_type,
                "product": product,
                "variety": "regular",
            }
            if price and order_type in ("LIMIT", "SL"):
                params["price"] = price
            if stop_loss and order_type in ("SL", "SL-M"):
                params["trigger_price"] = stop_loss

            order_id = self._kite.place_order(**params)
            logger.info("Kite order placed — ID: %s", order_id)

            return OrderResult(
                order_id=str(order_id),
                status=OrderStatus.OPEN,
                filled_price=price or 0.0,
                filled_qty=0,
                timestamp=now,
                message=f"Order placed: {direction} {quantity} {symbol}",
            )

        except Exception as exc:
            logger.error("Kite order placement failed: %s", exc)
            return OrderResult(
                order_id="ERROR",
                status=OrderStatus.REJECTED,
                timestamp=now,
                message=f"Order failed: {exc}",
            )

    # ── Cancel order ─────────────────────────────────────────────────

    def cancel_order(self, order_id: str) -> bool:
        """Cancel an order via Kite Connect."""
        if self._is_mock:
            logger.info("Mock cancel order: %s", order_id)
            return True

        try:
            _rate_limit()
            self._kite.cancel_order(variety="regular", order_id=order_id)
            logger.info("Kite order %s cancelled", order_id)
            return True
        except Exception as exc:
            logger.error("Failed to cancel order %s: %s", order_id, exc)
            return False

    # ── Order status ─────────────────────────────────────────────────

    def get_order_status(self, order_id: str) -> OrderResult:
        """Query order status from Kite."""
        now = datetime.now(IST)

        if self._is_mock:
            return OrderResult(
                order_id=order_id,
                status=OrderStatus.FILLED,
                filled_price=100.0,
                filled_qty=1,
                timestamp=now,
                message="Mock order — assumed filled",
            )

        try:
            _rate_limit()
            history = self._kite.order_history(order_id)
            if not history:
                return OrderResult(order_id=order_id, status=OrderStatus.PENDING, timestamp=now)

            latest = history[-1]
            status_map = {
                "COMPLETE": OrderStatus.FILLED,
                "CANCELLED": OrderStatus.CANCELLED,
                "REJECTED": OrderStatus.REJECTED,
                "OPEN": OrderStatus.OPEN,
                "TRIGGER PENDING": OrderStatus.PENDING,
            }
            return OrderResult(
                order_id=order_id,
                status=status_map.get(latest.get("status", ""), OrderStatus.PENDING),
                filled_price=latest.get("average_price", 0.0),
                filled_qty=latest.get("filled_quantity", 0),
                timestamp=now,
                message=latest.get("status_message", ""),
                raw=latest,
            )
        except Exception as exc:
            logger.error("Failed to get order status %s: %s", order_id, exc)
            return OrderResult(
                order_id=order_id,
                status=OrderStatus.REJECTED,
                timestamp=now,
                message=str(exc),
            )

    # ── Order history ────────────────────────────────────────────────

    def get_order_history(self) -> list[OrderResult]:
        """Get all orders for the day."""
        if self._is_mock:
            return []

        try:
            _rate_limit()
            orders = self._kite.orders()
            now = datetime.now(IST)
            results = []
            for o in orders:
                status_map = {
                    "COMPLETE": OrderStatus.FILLED,
                    "CANCELLED": OrderStatus.CANCELLED,
                    "REJECTED": OrderStatus.REJECTED,
                    "OPEN": OrderStatus.OPEN,
                }
                results.append(OrderResult(
                    order_id=str(o.get("order_id", "")),
                    status=status_map.get(o.get("status", ""), OrderStatus.PENDING),
                    filled_price=o.get("average_price", 0.0),
                    filled_qty=o.get("filled_quantity", 0),
                    timestamp=now,
                    raw=o,
                ))
            return results
        except Exception as exc:
            logger.error("Failed to fetch order history: %s", exc)
            return []

    # ── Positions ────────────────────────────────────────────────────

    def get_positions(self) -> list[dict[str, Any]]:
        """Get open positions from Kite."""
        if self._is_mock:
            return self._mock_positions()

        try:
            _rate_limit()
            positions = self._kite.positions()
            results = []
            for p in positions.get("net", []):
                if p.get("quantity", 0) != 0:
                    results.append({
                        "symbol": p.get("tradingsymbol", ""),
                        "quantity": p.get("quantity", 0),
                        "avg_price": p.get("average_price", 0.0),
                        "pnl": p.get("pnl", 0.0),
                        "market_value": p.get("value", 0.0),
                        "product": p.get("product", ""),
                        "exchange": p.get("exchange", ""),
                    })
            return results
        except Exception as exc:
            logger.error("Failed to fetch positions: %s", exc)
            return []

    # ── Holdings ─────────────────────────────────────────────────────

    def get_holdings(self) -> list[dict[str, Any]]:
        """Get demat holdings from Kite."""
        if self._is_mock:
            return self._mock_holdings()

        try:
            _rate_limit()
            holdings = self._kite.holdings()
            return [
                {
                    "symbol": h.get("tradingsymbol", ""),
                    "quantity": h.get("quantity", 0),
                    "avg_price": h.get("average_price", 0.0),
                    "current_price": h.get("last_price", 0.0),
                    "pnl": h.get("pnl", 0.0),
                    "isin": h.get("isin", ""),
                }
                for h in holdings
            ]
        except Exception as exc:
            logger.error("Failed to fetch holdings: %s", exc)
            return []

    # ── Margins ──────────────────────────────────────────────────────

    def get_margins(self) -> dict[str, Any]:
        """Get available margins from Kite."""
        if self._is_mock:
            return {
                "available_cash": 500_000.0,
                "used_margin": 150_000.0,
                "total_margin": 650_000.0,
                "available_margin": 500_000.0,
                "mock": True,
            }

        try:
            _rate_limit()
            margins = self._kite.margins(segment="equity")
            return {
                "available_cash": margins.get("available", {}).get("cash", 0.0),
                "used_margin": margins.get("utilised", {}).get("debits", 0.0),
                "total_margin": margins.get("net", 0.0),
                "available_margin": margins.get("available", {}).get("live_balance", 0.0),
            }
        except Exception as exc:
            logger.error("Failed to fetch margins: %s", exc)
            return {}

    # ── Mock helpers ─────────────────────────────────────────────────

    @staticmethod
    def _mock_order(
        symbol: str,
        direction: str,
        quantity: int,
        price: Optional[float],
        order_type: str,
        now: datetime,
    ) -> OrderResult:
        """Return a mock filled order."""
        import uuid

        mock_price = price or 100.0
        return OrderResult(
            order_id=f"MOCK-{uuid.uuid4().hex[:8].upper()}",
            status=OrderStatus.FILLED,
            filled_price=mock_price,
            filled_qty=quantity,
            timestamp=now,
            message=f"Mock {direction} {quantity} {symbol} @ ₹{mock_price:.2f}",
        )

    @staticmethod
    def _mock_positions() -> list[dict[str, Any]]:
        """Return sample mock positions."""
        return [
            {
                "symbol": "RELIANCE",
                "quantity": 10,
                "avg_price": 2780.50,
                "pnl": 195.0,
                "market_value": 28000.0,
                "product": "CNC",
                "exchange": "NSE",
                "mock": True,
            },
        ]

    @staticmethod
    def _mock_holdings() -> list[dict[str, Any]]:
        """Return sample mock holdings."""
        return [
            {
                "symbol": "TCS",
                "quantity": 5,
                "avg_price": 4050.0,
                "current_price": 4200.0,
                "pnl": 750.0,
                "isin": "INE467B01029",
                "mock": True,
            },
        ]
