"""
Order execution with broker failover.

Provides a unified ``OrderExecutor`` that routes orders through a
prioritised list of broker adapters, automatically failing over to
the next broker on error.  Includes Indian NSE / BSE charge
calculation (brokerage, STT, exchange fees, GST, SEBI, stamp duty).
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional
from zoneinfo import ZoneInfo

from app.core.constants import INDIAN_CHARGES

logger = logging.getLogger(__name__)

IST = ZoneInfo("Asia/Kolkata")


# ═══════════════════════════════════════════════════════════════════════
# Enums & data classes
# ═══════════════════════════════════════════════════════════════════════

class OrderStatus(str, Enum):
    """Lifecycle status of a broker order."""

    PENDING = "PENDING"
    PLACED = "PLACED"
    PARTIAL = "PARTIAL"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"
    ERROR = "ERROR"


@dataclass
class OrderResult:
    """Result of a single order-placement attempt."""

    success: bool
    order_id: str = ""
    status: OrderStatus = OrderStatus.PENDING
    fill_price: float = 0.0
    quantity: int = 0
    broker: str = ""
    message: str = ""
    timestamp: str = field(
        default_factory=lambda: datetime.now(tz=IST).isoformat()
    )


@dataclass
class ChargesBreakdown:
    """Itemised breakdown of Indian equity charges."""

    brokerage: float = 0.0
    stt: float = 0.0
    exchange_charges: float = 0.0
    gst: float = 0.0
    sebi_fee: float = 0.0
    stamp_duty: float = 0.0
    total: float = 0.0


# ═══════════════════════════════════════════════════════════════════════
# Order Executor
# ═══════════════════════════════════════════════════════════════════════

class OrderExecutor:
    """Unified order executor with broker-priority failover.

    When a broker rejects or errors out, the executor tries the next
    broker in the priority list.  If no live broker succeeds and
    ``"paper"`` is in the list, the order is routed to paper trading.

    Parameters
    ----------
    brokers : list[str]
        Priority-ordered broker names (e.g. ``["zerodha", "angel", "paper"]``).
    default : str
        Default broker to use when none is specified.
    broker_clients : dict, optional
        Pre-initialised broker client instances keyed by name.
    """

    def __init__(
        self,
        brokers: Optional[list[str]] = None,
        default: str = "paper",
        broker_clients: Optional[dict[str, Any]] = None,
    ) -> None:
        self._brokers = brokers or ["paper"]
        self._default = default
        self._broker_clients = broker_clients or {}
        self._order_log: list[OrderResult] = []

        logger.info(
            "OrderExecutor initialised: brokers=%s, default=%s",
            self._brokers,
            self._default,
        )

    # ── Public API ───────────────────────────────────────────────────

    def place_order(
        self,
        symbol: str,
        direction: str,
        quantity: int,
        price: float,
        order_type: str = "LIMIT",
        broker: Optional[str] = None,
    ) -> OrderResult:
        """Place an order, with automatic failover on error.

        Parameters
        ----------
        symbol : str
        direction : str
            ``"BUY"`` or ``"SELL"``.
        quantity : int
        price : float
            Limit price (ignored for MARKET orders).
        order_type : str, default "LIMIT"
        broker : str, optional
            Specific broker to use.  Falls back to failover list if
            omitted or on error.

        Returns
        -------
        OrderResult
        """
        order_data = {
            "symbol": symbol,
            "direction": direction.upper(),
            "quantity": quantity,
            "price": price,
            "order_type": order_type.upper(),
        }

        if broker:
            result = self._try_broker(broker, order_data)
            if result.success:
                self._order_log.append(result)
                return result
            logger.warning(
                "Broker %s failed for %s — attempting failover",
                broker,
                symbol,
            )

        # Failover
        result = self._failover_execute(order_data)
        self._order_log.append(result)
        return result

    def cancel_order(self, order_id: str, broker: str) -> bool:
        """Cancel an open order.

        Parameters
        ----------
        order_id : str
        broker : str

        Returns
        -------
        bool
        """
        client = self._broker_clients.get(broker)
        if client is None:
            logger.warning("cancel_order: broker '%s' not available", broker)
            # Simulate success for paper orders
            if broker == "paper":
                logger.info("Paper order %s cancelled", order_id)
                return True
            return False

        try:
            client.cancel_order(order_id)  # type: ignore[attr-defined]
            logger.info("Order %s cancelled on %s", order_id, broker)
            return True
        except Exception:
            logger.exception("Failed to cancel order %s on %s", order_id, broker)
            return False

    def get_order_status(self, order_id: str, broker: str) -> OrderStatus:
        """Query the current status of an order.

        Parameters
        ----------
        order_id : str
        broker : str

        Returns
        -------
        OrderStatus
        """
        client = self._broker_clients.get(broker)
        if client is None:
            # Check local log
            for order in self._order_log:
                if order.order_id == order_id:
                    return order.status
            return OrderStatus.PENDING

        try:
            status = client.get_order_status(order_id)  # type: ignore[attr-defined]
            return OrderStatus(status)
        except Exception:
            logger.exception("Failed to get status for %s on %s", order_id, broker)
            return OrderStatus.ERROR

    # ── Charges ──────────────────────────────────────────────────────

    @staticmethod
    def calculate_charges(
        price: float,
        quantity: int,
        order_type: str = "DELIVERY",
        market: str = "NSE",
    ) -> ChargesBreakdown:
        """Calculate Indian equity trading charges.

        Parameters
        ----------
        price : float
            Fill price per share.
        quantity : int
        order_type : str
            ``"DELIVERY"`` or ``"INTRADAY"``.
        market : str
            ``"NSE"`` or ``"BSE"``.

        Returns
        -------
        ChargesBreakdown
        """
        turnover = price * quantity
        is_delivery = order_type.upper() == "DELIVERY"

        # Brokerage
        if is_delivery:
            brokerage = turnover * INDIAN_CHARGES["brokerage_delivery"]
        else:
            brokerage = min(
                turnover * INDIAN_CHARGES["brokerage_intraday"],
                INDIAN_CHARGES["brokerage_max_per_order"],
            )

        # STT
        if is_delivery:
            stt = turnover * (
                INDIAN_CHARGES["stt_delivery_buy"]
                + INDIAN_CHARGES["stt_delivery_sell"]
            )
        else:
            stt = turnover * INDIAN_CHARGES["stt_intraday_sell"]

        # Exchange charges
        if market.upper() == "BSE":
            exchange = turnover * INDIAN_CHARGES["exchange_bse"]
        else:
            exchange = turnover * INDIAN_CHARGES["exchange_nse"]

        # GST on (brokerage + exchange)
        gst = (brokerage + exchange) * INDIAN_CHARGES["gst_rate"]

        # SEBI fee
        sebi = turnover * INDIAN_CHARGES["sebi_fee"]

        # Stamp duty (buy side only → half turnover approximation)
        if is_delivery:
            stamp = (turnover / 2) * INDIAN_CHARGES["stamp_duty_delivery"]
        else:
            stamp = (turnover / 2) * INDIAN_CHARGES["stamp_duty_intraday"]

        total = brokerage + stt + exchange + gst + sebi + stamp

        breakdown = ChargesBreakdown(
            brokerage=round(brokerage, 2),
            stt=round(stt, 2),
            exchange_charges=round(exchange, 2),
            gst=round(gst, 2),
            sebi_fee=round(sebi, 4),
            stamp_duty=round(stamp, 2),
            total=round(total, 2),
        )
        logger.debug(
            "Charges for %d × ₹%.2f (%s, %s): ₹%.2f",
            quantity, price, order_type, market, total,
        )
        return breakdown

    # ── Internal ─────────────────────────────────────────────────────

    def _try_broker(
        self,
        broker: str,
        order: dict[str, Any],
    ) -> OrderResult:
        """Attempt to place *order* on *broker*.

        For ``"paper"`` broker or when no client is available, a
        simulated fill is returned.
        """
        if broker == "paper" or broker not in self._broker_clients:
            # Simulated fill
            order_id = f"PAPER-{uuid.uuid4().hex[:8].upper()}"
            logger.info(
                "Paper order placed: %s %s %d × ₹%.2f (id=%s)",
                order["direction"],
                order["symbol"],
                order["quantity"],
                order["price"],
                order_id,
            )
            return OrderResult(
                success=True,
                order_id=order_id,
                status=OrderStatus.FILLED,
                fill_price=order["price"],
                quantity=order["quantity"],
                broker="paper",
                message="Simulated fill",
            )

        client = self._broker_clients[broker]
        try:
            resp = client.place_order(  # type: ignore[attr-defined]
                symbol=order["symbol"],
                direction=order["direction"],
                quantity=order["quantity"],
                price=order["price"],
                order_type=order["order_type"],
            )
            return OrderResult(
                success=True,
                order_id=resp.get("order_id", ""),
                status=OrderStatus.PLACED,
                fill_price=order["price"],
                quantity=order["quantity"],
                broker=broker,
                message=resp.get("message", "Order placed"),
            )
        except Exception as exc:
            logger.exception("Broker %s order failed", broker)
            return OrderResult(
                success=False,
                broker=broker,
                message=str(exc),
                status=OrderStatus.ERROR,
            )

    def _failover_execute(self, order: dict[str, Any]) -> OrderResult:
        """Try each broker in priority order; return first success."""
        for broker in self._brokers:
            result = self._try_broker(broker, order)
            if result.success:
                return result
            logger.warning(
                "Failover: broker %s failed — trying next", broker,
            )

        # All failed
        logger.error(
            "All brokers failed for %s %s",
            order["direction"],
            order["symbol"],
        )
        return OrderResult(
            success=False,
            status=OrderStatus.REJECTED,
            message="All brokers exhausted",
        )
