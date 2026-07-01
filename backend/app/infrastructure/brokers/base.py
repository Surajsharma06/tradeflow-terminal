"""
Abstract broker interface for the Trading System.

Defines the contract that every broker implementation (paper, Zerodha,
Alpaca, etc.) must satisfy.  Also provides the ``OrderResult`` dataclass
and ``OrderStatus`` enum shared across all brokers.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")


class OrderStatus(str, Enum):
    """Lifecycle status of a broker order."""

    PENDING = "PENDING"
    OPEN = "OPEN"
    FILLED = "FILLED"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"


@dataclass
class OrderResult:
    """
    Standardised result returned after placing or querying an order.

    Attributes:
        order_id: Broker-assigned unique order identifier.
        status: Current lifecycle status.
        filled_price: Average fill price (``0.0`` if not yet filled).
        filled_qty: Quantity filled so far.
        timestamp: Timestamp of the last status change (IST).
        message: Optional human-readable status message.
        raw: Raw broker response for debugging.
    """

    order_id: str
    status: OrderStatus
    filled_price: float = 0.0
    filled_qty: int = 0
    timestamp: datetime = field(default_factory=lambda: datetime.now(IST))
    message: str = ""
    raw: dict[str, Any] = field(default_factory=dict)


class BrokerInterface(ABC):
    """
    Abstract base class for all broker integrations.

    Every concrete broker must implement every method listed below.
    Methods are intentionally synchronous; async adapters can wrap
    them via ``asyncio.to_thread`` at the service layer.
    """

    # ── Connection lifecycle ─────────────────────────────────────────

    @abstractmethod
    def connect(self) -> bool:
        """
        Establish a connection / session with the broker.

        Returns:
            ``True`` if the connection succeeded.
        """

    @abstractmethod
    def disconnect(self) -> None:
        """Close the broker session gracefully."""

    # ── Order management ─────────────────────────────────────────────

    @abstractmethod
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
        Place a new order.

        Args:
            symbol: Instrument symbol.
            direction: ``"BUY"`` or ``"SELL"``.
            quantity: Number of shares / lots.
            price: Limit price (``None`` for market orders).
            order_type: ``"MARKET"``, ``"LIMIT"``, ``"SL"``, ``"SL-M"``.
            product: ``"CNC"`` (delivery), ``"MIS"`` (intraday),
                     ``"NRML"`` (F&O normal).
            stop_loss: Optional stop-loss trigger price.
            take_profit: Optional take-profit price.

        Returns:
            ``OrderResult`` with order ID and initial status.
        """

    @abstractmethod
    def cancel_order(self, order_id: str) -> bool:
        """
        Cancel an open order.

        Args:
            order_id: Broker-assigned order ID.

        Returns:
            ``True`` if cancellation was accepted.
        """

    @abstractmethod
    def get_order_status(self, order_id: str) -> OrderResult:
        """
        Query the current status of an order.

        Args:
            order_id: Broker-assigned order ID.

        Returns:
            ``OrderResult`` with the latest status.
        """

    @abstractmethod
    def get_order_history(self) -> list[OrderResult]:
        """
        Retrieve the order history for the current trading session.

        Returns:
            List of ``OrderResult`` instances.
        """

    # ── Portfolio queries ────────────────────────────────────────────

    @abstractmethod
    def get_positions(self) -> list[dict[str, Any]]:
        """
        Get all open positions.

        Returns:
            List of dicts with at least ``symbol``, ``quantity``,
            ``avg_price``, ``pnl``, ``market_value``.
        """

    @abstractmethod
    def get_holdings(self) -> list[dict[str, Any]]:
        """
        Get long-term holdings (delivery / demat).

        Returns:
            List of dicts with ``symbol``, ``quantity``, ``avg_price``,
            ``current_price``, ``pnl``.
        """

    @abstractmethod
    def get_margins(self) -> dict[str, Any]:
        """
        Get available margin / buying power.

        Returns:
            Dict with ``available_cash``, ``used_margin``,
            ``total_margin``, ``available_margin``.
        """
