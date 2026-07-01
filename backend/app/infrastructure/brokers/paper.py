"""
Paper trading broker for the Trading System.

Implements ``BrokerInterface`` with an in-memory virtual portfolio.
Simulates realistic order execution including slippage, and calculates
Indian brokerage charges (STT, stamp duty, exchange fees, GST) on
every trade.  Supports both INR and USD markets.
"""

import logging
import random
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional
from zoneinfo import ZoneInfo

from app.core.constants import INDIAN_CHARGES
from app.infrastructure.brokers.base import (
    BrokerInterface,
    OrderResult,
    OrderStatus,
)

logger = logging.getLogger(__name__)

IST = ZoneInfo("Asia/Kolkata")


@dataclass
class _Position:
    """Internal position tracker."""

    symbol: str
    quantity: int
    avg_price: float
    direction: str  # "LONG" or "SHORT"
    market_value: float = 0.0
    pnl: float = 0.0
    charges: float = 0.0


@dataclass
class _TradeRecord:
    """Internal record for a completed trade."""

    trade_id: str
    order_id: str
    symbol: str
    direction: str
    quantity: int
    price: float
    charges: float
    timestamp: datetime
    pnl: float = 0.0


class PaperBroker(BrokerInterface):
    """
    In-memory paper-trading broker.

    Features:
    * Realistic slippage model (0.01 – 0.05 %).
    * Indian equity charges (STT, stamp, exchange, GST, SEBI fee).
    * Virtual cash + position tracking.
    * Full order history and trade log.
    * Works with both Indian (INR) and US ($) markets.
    """

    # Slippage range as fraction of price
    _SLIPPAGE_MIN: float = 0.0001
    _SLIPPAGE_MAX: float = 0.0005

    def __init__(
        self,
        initial_capital: float = 1_000_000.0,
        currency: str = "INR",
    ) -> None:
        """
        Args:
            initial_capital: Starting cash balance.
            currency: ``"INR"`` or ``"USD"``.
        """
        self.currency = currency.upper()
        self.initial_capital = initial_capital
        self.cash: float = initial_capital
        self.is_connected: bool = False

        # Portfolio state
        self._positions: dict[str, _Position] = {}
        self._orders: dict[str, OrderResult] = {}
        self._trades: list[_TradeRecord] = []

        # PnL tracking
        self.realised_pnl: float = 0.0
        self.total_charges: float = 0.0

        logger.info(
            "PaperBroker initialised — capital: %s %.2f",
            self.currency, self.initial_capital,
        )

    # ── Connection ───────────────────────────────────────────────────

    def connect(self) -> bool:
        """Simulate broker connection."""
        self.is_connected = True
        logger.info("PaperBroker connected (paper trading mode)")
        return True

    def disconnect(self) -> None:
        """Simulate broker disconnection."""
        self.is_connected = False
        logger.info("PaperBroker disconnected")

    # ── Charges calculation ──────────────────────────────────────────

    def _calculate_charges(
        self,
        price: float,
        quantity: int,
        direction: str,
        product: str = "CNC",
    ) -> float:
        """
        Calculate Indian trading charges for a single leg.

        For USD markets, charges are simplified to a flat
        $0.005 per share (US commission model).
        """
        if self.currency == "USD":
            return round(quantity * 0.005, 2)

        turnover = price * quantity
        charges = 0.0

        # Brokerage
        brokerage = min(
            turnover * INDIAN_CHARGES["brokerage_intraday"],
            INDIAN_CHARGES["brokerage_max_per_order"],
        ) if product == "MIS" else 0.0  # Delivery is free
        charges += brokerage

        # STT
        if product == "CNC":
            # Delivery: both sides
            charges += turnover * INDIAN_CHARGES["stt_delivery_buy"]
        else:
            # Intraday: sell side only
            if direction == "SELL":
                charges += turnover * INDIAN_CHARGES["stt_intraday_sell"]

        # Exchange transaction charges
        charges += turnover * INDIAN_CHARGES["exchange_nse"]

        # SEBI turnover fee
        charges += turnover * INDIAN_CHARGES["sebi_fee"]

        # Stamp duty (buy side only)
        if direction == "BUY":
            stamp_key = "stamp_duty_delivery" if product == "CNC" else "stamp_duty_intraday"
            charges += turnover * INDIAN_CHARGES[stamp_key]

        # GST on brokerage + exchange charges
        taxable = brokerage + (turnover * INDIAN_CHARGES["exchange_nse"])
        charges += taxable * INDIAN_CHARGES["gst_rate"]

        return round(charges, 2)

    # ── Slippage simulation ──────────────────────────────────────────

    def _apply_slippage(self, price: float, direction: str) -> float:
        """
        Apply realistic slippage to a market order price.

        Buys slip up, sells slip down.
        """
        slip_pct = random.uniform(self._SLIPPAGE_MIN, self._SLIPPAGE_MAX)
        if direction == "BUY":
            return round(price * (1 + slip_pct), 2)
        return round(price * (1 - slip_pct), 2)

    # ── Order execution ──────────────────────────────────────────────

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
        Execute a paper order instantly with simulated slippage.

        For market orders, ``price`` must still be provided as the
        *reference price* (i.e., last traded price); slippage is
        applied on top.
        """
        direction = direction.upper()
        symbol = symbol.upper()
        order_id = f"PAPER-{uuid.uuid4().hex[:12].upper()}"

        if price is None or price <= 0:
            logger.error("Price required for paper order simulation — order rejected")
            result = OrderResult(
                order_id=order_id,
                status=OrderStatus.REJECTED,
                message="Price is required for paper broker simulation",
            )
            self._orders[order_id] = result
            return result

        # Apply slippage for market orders
        fill_price = self._apply_slippage(price, direction) if order_type == "MARKET" else price

        # Calculate charges
        charges = self._calculate_charges(fill_price, quantity, direction, product)
        cost = fill_price * quantity

        # Validate sufficient funds for BUY
        if direction == "BUY":
            total_cost = cost + charges
            if total_cost > self.cash:
                result = OrderResult(
                    order_id=order_id,
                    status=OrderStatus.REJECTED,
                    message=f"Insufficient funds: need {self.currency} {total_cost:.2f}, "
                            f"available {self.currency} {self.cash:.2f}",
                )
                self._orders[order_id] = result
                logger.warning("Order %s rejected — insufficient funds", order_id)
                return result

        # Execute the fill
        now = datetime.now(IST)

        if direction == "BUY":
            self.cash -= (cost + charges)
            self._add_position(symbol, quantity, fill_price, charges)
        elif direction == "SELL":
            pnl = self._reduce_position(symbol, quantity, fill_price)
            self.cash += (cost - charges)
            self.realised_pnl += pnl
        else:
            result = OrderResult(
                order_id=order_id,
                status=OrderStatus.REJECTED,
                message=f"Unknown direction: {direction}",
            )
            self._orders[order_id] = result
            return result

        self.total_charges += charges

        # Record trade
        trade = _TradeRecord(
            trade_id=f"T-{uuid.uuid4().hex[:8].upper()}",
            order_id=order_id,
            symbol=symbol,
            direction=direction,
            quantity=quantity,
            price=fill_price,
            charges=charges,
            timestamp=now,
            pnl=self.realised_pnl if direction == "SELL" else 0.0,
        )
        self._trades.append(trade)

        result = OrderResult(
            order_id=order_id,
            status=OrderStatus.FILLED,
            filled_price=fill_price,
            filled_qty=quantity,
            timestamp=now,
            message=f"Paper {direction} {quantity} {symbol} @ {self.currency} {fill_price:.2f} "
                    f"(charges: {self.currency} {charges:.2f})",
        )
        self._orders[order_id] = result

        logger.info(
            "📝 Paper order filled: %s %d %s @ %s %.2f | charges: %.2f | cash: %.2f",
            direction, quantity, symbol, self.currency, fill_price, charges, self.cash,
        )
        return result

    # ── Position helpers ─────────────────────────────────────────────

    def _add_position(self, symbol: str, qty: int, price: float, charges: float) -> None:
        """Add to or open a new long position."""
        if symbol in self._positions:
            pos = self._positions[symbol]
            total_qty = pos.quantity + qty
            pos.avg_price = round(
                ((pos.avg_price * pos.quantity) + (price * qty)) / total_qty, 2,
            )
            pos.quantity = total_qty
            pos.charges += charges
        else:
            self._positions[symbol] = _Position(
                symbol=symbol,
                quantity=qty,
                avg_price=price,
                direction="LONG",
                market_value=price * qty,
                charges=charges,
            )

    def _reduce_position(self, symbol: str, qty: int, price: float) -> float:
        """
        Reduce a position and return realised PnL for the sold portion.
        """
        if symbol not in self._positions:
            logger.warning("No position in %s to sell — treating as short", symbol)
            return 0.0

        pos = self._positions[symbol]
        sell_qty = min(qty, pos.quantity)
        pnl = round((price - pos.avg_price) * sell_qty, 2)
        pos.quantity -= sell_qty

        if pos.quantity <= 0:
            del self._positions[symbol]

        return pnl

    # ── Cancel ───────────────────────────────────────────────────────

    def cancel_order(self, order_id: str) -> bool:
        """
        Cancel an order. In paper mode, only PENDING orders can be cancelled.
        """
        if order_id in self._orders:
            order = self._orders[order_id]
            if order.status == OrderStatus.PENDING:
                order.status = OrderStatus.CANCELLED
                logger.info("Paper order %s cancelled", order_id)
                return True
            logger.warning("Cannot cancel order %s — status is %s", order_id, order.status)
            return False
        logger.warning("Order %s not found", order_id)
        return False

    # ── Queries ──────────────────────────────────────────────────────

    def get_order_status(self, order_id: str) -> OrderResult:
        """Return the status of a previously placed order."""
        if order_id in self._orders:
            return self._orders[order_id]
        return OrderResult(
            order_id=order_id,
            status=OrderStatus.REJECTED,
            message="Order not found",
        )

    def get_order_history(self) -> list[OrderResult]:
        """Return all orders placed in this session."""
        return list(self._orders.values())

    def get_positions(self) -> list[dict[str, Any]]:
        """Return all open positions as dicts."""
        return [
            {
                "symbol": pos.symbol,
                "quantity": pos.quantity,
                "avg_price": pos.avg_price,
                "direction": pos.direction,
                "market_value": round(pos.avg_price * pos.quantity, 2),
                "pnl": pos.pnl,
                "charges": pos.charges,
            }
            for pos in self._positions.values()
        ]

    def get_holdings(self) -> list[dict[str, Any]]:
        """Return holdings (same as positions in paper mode)."""
        return self.get_positions()

    def get_margins(self) -> dict[str, Any]:
        """Return current margin / cash status."""
        invested = sum(p.avg_price * p.quantity for p in self._positions.values())
        return {
            "available_cash": round(self.cash, 2),
            "used_margin": round(invested, 2),
            "total_margin": round(self.cash + invested, 2),
            "available_margin": round(self.cash, 2),
            "realised_pnl": round(self.realised_pnl, 2),
            "total_charges": round(self.total_charges, 2),
            "currency": self.currency,
        }

    # ── Trade log ────────────────────────────────────────────────────

    def get_trade_log(self) -> list[dict[str, Any]]:
        """Return the full trade log as a list of dicts."""
        return [
            {
                "trade_id": t.trade_id,
                "order_id": t.order_id,
                "symbol": t.symbol,
                "direction": t.direction,
                "quantity": t.quantity,
                "price": t.price,
                "charges": t.charges,
                "pnl": t.pnl,
                "timestamp": t.timestamp.isoformat(),
            }
            for t in self._trades
        ]
