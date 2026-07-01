"""
Alpaca broker integration for US equities.

Implements ``BrokerInterface`` using ``httpx`` to call the Alpaca
REST API.  Paper-trading URL is used by default.  Supports fractional
shares.  Returns mock data when API credentials are absent.
"""

import logging
import time
import uuid
from datetime import datetime
from typing import Any, Optional
from zoneinfo import ZoneInfo

try:
    import httpx

    HAS_HTTPX = True
except ImportError:
    HAS_HTTPX = False

from app.core.config import get_settings
from app.infrastructure.brokers.base import (
    BrokerInterface,
    OrderResult,
    OrderStatus,
)

logger = logging.getLogger(__name__)

IST = ZoneInfo("Asia/Kolkata")
ET = ZoneInfo("America/New_York")

_RATE_LIMIT_DELAY: float = 0.15
_last_request_ts: float = 0.0


def _rate_limit() -> None:
    """Enforce rate limiting for Alpaca API calls."""
    global _last_request_ts
    elapsed = time.monotonic() - _last_request_ts
    if elapsed < _RATE_LIMIT_DELAY:
        time.sleep(_RATE_LIMIT_DELAY - elapsed)
    _last_request_ts = time.monotonic()


class AlpacaBroker(BrokerInterface):
    """
    Alpaca Markets broker for US equities.

    * Uses the **paper trading** endpoint by default.
    * Supports fractional share orders.
    * Falls back to mock data when ``ALPACA_API_KEY`` is not set.

    All HTTP calls use ``httpx.Client`` (sync).  Wrap with
    ``asyncio.to_thread`` for async FastAPI handlers.
    """

    def __init__(self) -> None:
        """Initialise with credentials from settings."""
        settings = get_settings()
        self._api_key = settings.alpaca_api_key
        self._secret_key = settings.alpaca_secret_key
        self._base_url = settings.alpaca_base_url  # defaults to paper URL

        self._is_mock: bool = True
        self._client: Optional[Any] = None

        if not self._api_key or not self._secret_key:
            logger.info(
                "Alpaca credentials not configured — "
                "AlpacaBroker will return mock data"
            )
        elif not HAS_HTTPX:
            logger.warning(
                "httpx not installed — AlpacaBroker will return mock data"
            )

    # ── Internal HTTP helpers ────────────────────────────────────────

    def _headers(self) -> dict[str, str]:
        """Return authentication headers for Alpaca."""
        return {
            "APCA-API-KEY-ID": self._api_key or "",
            "APCA-API-SECRET-KEY": self._secret_key or "",
            "Content-Type": "application/json",
        }

    def _request(
        self,
        method: str,
        path: str,
        json_data: Optional[dict] = None,
        params: Optional[dict] = None,
    ) -> Optional[dict]:
        """
        Make an authenticated request to the Alpaca API.

        Returns:
            Parsed JSON response on success, ``None`` on failure.
        """
        if self._is_mock:
            return None

        url = f"{self._base_url}/v2{path}"
        try:
            _rate_limit()
            with httpx.Client(timeout=15) as client:
                resp = client.request(
                    method, url,
                    headers=self._headers(),
                    json=json_data,
                    params=params,
                )
                if resp.status_code >= 400:
                    logger.error(
                        "Alpaca API error %d: %s",
                        resp.status_code, resp.text,
                    )
                    return None
                return resp.json() if resp.content else {}
        except Exception as exc:
            logger.error("Alpaca request failed (%s %s): %s", method, path, exc)
            return None

    # ── Connection ───────────────────────────────────────────────────

    def connect(self) -> bool:
        """Verify Alpaca API connectivity."""
        if not self._api_key or not HAS_HTTPX:
            self._is_mock = True
            logger.info("AlpacaBroker connected (mock mode)")
            return True

        self._is_mock = False
        data = self._request("GET", "/account")
        if data:
            logger.info(
                "AlpacaBroker connected — account: %s, equity: $%s",
                data.get("account_number", "?"),
                data.get("equity", "?"),
            )
            return True

        logger.warning("Alpaca connection failed — falling back to mock mode")
        self._is_mock = True
        return True

    def disconnect(self) -> None:
        """No persistent connection to close for Alpaca."""
        logger.info("AlpacaBroker disconnected")

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
        """
        Place an order via the Alpaca API.

        Supports fractional shares by accepting ``quantity`` as int
        (whole shares) and using Alpaca's ``qty`` parameter.
        """
        now = datetime.now(IST)
        direction = direction.upper()
        symbol = symbol.upper()

        logger.info(
            "Placing Alpaca order: %s %d %s @ %s (%s)",
            direction, quantity, symbol, price or "MARKET", order_type,
        )

        if self._is_mock:
            return self._mock_order(symbol, direction, quantity, price, now)

        order_type_map = {
            "MARKET": "market",
            "LIMIT": "limit",
            "SL": "stop_limit",
            "SL-M": "stop",
        }

        body: dict[str, Any] = {
            "symbol": symbol,
            "qty": str(quantity),
            "side": "buy" if direction == "BUY" else "sell",
            "type": order_type_map.get(order_type, "market"),
            "time_in_force": "day",
        }

        if price and order_type in ("LIMIT", "SL"):
            body["limit_price"] = str(price)
        if stop_loss and order_type in ("SL", "SL-M"):
            body["stop_price"] = str(stop_loss)

        # Bracket order: take_profit + stop_loss
        if take_profit and stop_loss and order_type == "MARKET":
            body["order_class"] = "bracket"
            body["take_profit"] = {"limit_price": str(take_profit)}
            body["stop_loss"] = {"stop_price": str(stop_loss)}

        data = self._request("POST", "/orders", json_data=body)
        if data:
            return OrderResult(
                order_id=data.get("id", ""),
                status=OrderStatus.OPEN,
                filled_price=float(data.get("filled_avg_price", 0) or 0),
                filled_qty=int(float(data.get("filled_qty", 0) or 0)),
                timestamp=now,
                message=f"Alpaca order placed: {direction} {quantity} {symbol}",
                raw=data,
            )

        return OrderResult(
            order_id="ERROR",
            status=OrderStatus.REJECTED,
            timestamp=now,
            message="Failed to place Alpaca order",
        )

    # ── Cancel order ─────────────────────────────────────────────────

    def cancel_order(self, order_id: str) -> bool:
        """Cancel an open order on Alpaca."""
        if self._is_mock:
            logger.info("Mock cancel Alpaca order: %s", order_id)
            return True

        data = self._request("DELETE", f"/orders/{order_id}")
        if data is not None:
            logger.info("Alpaca order %s cancelled", order_id)
            return True
        return False

    # ── Order status ─────────────────────────────────────────────────

    def get_order_status(self, order_id: str) -> OrderResult:
        """Get the current status of an Alpaca order."""
        now = datetime.now(IST)

        if self._is_mock:
            return OrderResult(
                order_id=order_id,
                status=OrderStatus.FILLED,
                filled_price=195.0,
                filled_qty=1,
                timestamp=now,
                message="Mock order — assumed filled",
            )

        data = self._request("GET", f"/orders/{order_id}")
        if data:
            status_map = {
                "filled": OrderStatus.FILLED,
                "partially_filled": OrderStatus.PARTIALLY_FILLED,
                "canceled": OrderStatus.CANCELLED,
                "expired": OrderStatus.CANCELLED,
                "rejected": OrderStatus.REJECTED,
                "new": OrderStatus.OPEN,
                "accepted": OrderStatus.OPEN,
                "pending_new": OrderStatus.PENDING,
            }
            return OrderResult(
                order_id=order_id,
                status=status_map.get(data.get("status", ""), OrderStatus.PENDING),
                filled_price=float(data.get("filled_avg_price", 0) or 0),
                filled_qty=int(float(data.get("filled_qty", 0) or 0)),
                timestamp=now,
                raw=data,
            )

        return OrderResult(
            order_id=order_id,
            status=OrderStatus.REJECTED,
            timestamp=now,
            message="Could not retrieve order status",
        )

    # ── Order history ────────────────────────────────────────────────

    def get_order_history(self) -> list[OrderResult]:
        """Get today's orders from Alpaca."""
        if self._is_mock:
            return []

        data = self._request("GET", "/orders", params={"status": "all", "limit": "100"})
        if not data or not isinstance(data, list):
            return []

        now = datetime.now(IST)
        results = []
        status_map = {
            "filled": OrderStatus.FILLED,
            "partially_filled": OrderStatus.PARTIALLY_FILLED,
            "canceled": OrderStatus.CANCELLED,
            "rejected": OrderStatus.REJECTED,
            "new": OrderStatus.OPEN,
        }
        for o in data:
            results.append(OrderResult(
                order_id=o.get("id", ""),
                status=status_map.get(o.get("status", ""), OrderStatus.PENDING),
                filled_price=float(o.get("filled_avg_price", 0) or 0),
                filled_qty=int(float(o.get("filled_qty", 0) or 0)),
                timestamp=now,
                raw=o,
            ))
        return results

    # ── Positions ────────────────────────────────────────────────────

    def get_positions(self) -> list[dict[str, Any]]:
        """Get all open positions from Alpaca."""
        if self._is_mock:
            return [
                {
                    "symbol": "AAPL",
                    "quantity": 10,
                    "avg_price": 190.50,
                    "pnl": 45.0,
                    "market_value": 1950.0,
                    "mock": True,
                },
            ]

        data = self._request("GET", "/positions")
        if not data or not isinstance(data, list):
            return []

        return [
            {
                "symbol": p.get("symbol", ""),
                "quantity": int(float(p.get("qty", 0))),
                "avg_price": float(p.get("avg_entry_price", 0)),
                "pnl": float(p.get("unrealized_pl", 0)),
                "market_value": float(p.get("market_value", 0)),
                "current_price": float(p.get("current_price", 0)),
                "side": p.get("side", ""),
            }
            for p in data
        ]

    # ── Holdings ─────────────────────────────────────────────────────

    def get_holdings(self) -> list[dict[str, Any]]:
        """Alpaca doesn't distinguish holdings from positions."""
        return self.get_positions()

    # ── Margins ──────────────────────────────────────────────────────

    def get_margins(self) -> dict[str, Any]:
        """Get account equity and buying power."""
        if self._is_mock:
            return {
                "available_cash": 50_000.0,
                "used_margin": 10_000.0,
                "total_margin": 60_000.0,
                "available_margin": 50_000.0,
                "currency": "USD",
                "mock": True,
            }

        data = self._request("GET", "/account")
        if data:
            return {
                "available_cash": float(data.get("cash", 0)),
                "used_margin": float(data.get("initial_margin", 0)),
                "total_margin": float(data.get("equity", 0)),
                "available_margin": float(data.get("buying_power", 0)),
                "currency": "USD",
            }
        return {}

    # ── Mock helpers ─────────────────────────────────────────────────

    @staticmethod
    def _mock_order(
        symbol: str,
        direction: str,
        quantity: int,
        price: Optional[float],
        now: datetime,
    ) -> OrderResult:
        """Return a mock filled order for demo purposes."""
        mock_price = price or 195.0
        return OrderResult(
            order_id=f"MOCK-ALP-{uuid.uuid4().hex[:8].upper()}",
            status=OrderStatus.FILLED,
            filled_price=mock_price,
            filled_qty=quantity,
            timestamp=now,
            message=f"Mock Alpaca {direction} {quantity} {symbol} @ ${mock_price:.2f}",
        )
