"""
Paper trading simulator.

Provides an in-memory virtual broker for risk-free strategy testing.
Tracks capital, positions, trade history, and PnL with configurable
slippage simulation.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)

IST = ZoneInfo("Asia/Kolkata")


# ═══════════════════════════════════════════════════════════════════════
# Data classes
# ═══════════════════════════════════════════════════════════════════════

class PaperOrderStatus(str, Enum):
    """Paper-order lifecycle status."""

    PENDING = "PENDING"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"


@dataclass
class PaperOrder:
    """A single paper order."""

    order_id: str
    symbol: str
    direction: str  # "BUY" or "SELL"
    quantity: int
    order_price: float
    fill_price: float = 0.0
    status: PaperOrderStatus = PaperOrderStatus.PENDING
    timestamp: str = field(
        default_factory=lambda: datetime.now(tz=IST).isoformat()
    )
    fill_timestamp: Optional[str] = None
    slippage_applied: float = 0.0


@dataclass
class PaperPosition:
    """An open paper-trading position."""

    symbol: str
    direction: str
    quantity: int
    entry_price: float
    current_price: float = 0.0
    unrealised_pnl: float = 0.0
    entry_time: str = field(
        default_factory=lambda: datetime.now(tz=IST).isoformat()
    )


# ═══════════════════════════════════════════════════════════════════════
# Paper Trader
# ═══════════════════════════════════════════════════════════════════════

class PaperTrader:
    """In-memory paper-trading engine.

    Simulates order placement, position tracking, and PnL computation
    without hitting any real broker API.

    Parameters
    ----------
    initial_capital : float
        Starting virtual capital (₹).
    """

    def __init__(self, initial_capital: float = 1_000_000.0) -> None:
        self._initial_capital = initial_capital
        self._available_capital = initial_capital
        self._positions: list[PaperPosition] = []
        self._orders: list[PaperOrder] = []
        self._closed_trades: list[dict[str, Any]] = []
        self._realised_pnl: float = 0.0

        logger.info(
            "PaperTrader initialised: capital=₹%.2f", initial_capital,
        )

    # ── Order placement ──────────────────────────────────────────────

    def place_order(
        self,
        symbol: str,
        direction: str,
        quantity: int,
        price: float,
        slippage_pct: float = 0.05,
    ) -> PaperOrder:
        """Place a paper order and simulate an immediate fill.

        Parameters
        ----------
        symbol : str
        direction : str
            ``"BUY"`` or ``"SELL"``.
        quantity : int
        price : float
            Requested entry price.
        slippage_pct : float, default 0.05
            Simulated slippage in percent (0.05 = 0.05 %).

        Returns
        -------
        PaperOrder
        """
        direction = direction.upper()
        if direction not in ("BUY", "SELL"):
            raise ValueError(f"Invalid direction: {direction}")

        if quantity <= 0:
            raise ValueError(f"Quantity must be positive, got {quantity}")

        if price <= 0:
            raise ValueError(f"Price must be positive, got {price}")

        order_id = f"PAPER-{uuid.uuid4().hex[:8].upper()}"
        order = PaperOrder(
            order_id=order_id,
            symbol=symbol,
            direction=direction,
            quantity=quantity,
            order_price=price,
        )

        # Check capital for BUY orders
        required = price * quantity
        if direction == "BUY" and required > self._available_capital:
            order.status = PaperOrderStatus.REJECTED
            order.fill_price = 0.0
            logger.warning(
                "Paper order rejected: insufficient capital "
                "(need=₹%.2f, available=₹%.2f)",
                required,
                self._available_capital,
            )
            self._orders.append(order)
            return order

        # Simulate fill with slippage
        filled_order = self.simulate_fill(order, slippage_pct)
        self._orders.append(filled_order)

        # Update positions and capital
        if filled_order.status == PaperOrderStatus.FILLED:
            self._apply_fill(filled_order)

        return filled_order

    def simulate_fill(
        self,
        order: PaperOrder,
        slippage_pct: float = 0.05,
    ) -> PaperOrder:
        """Apply slippage and mark the order as filled.

        Slippage direction:
        - BUY  → price slightly higher (adverse).
        - SELL → price slightly lower (adverse).

        Parameters
        ----------
        order : PaperOrder
        slippage_pct : float, default 0.05

        Returns
        -------
        PaperOrder
            The same order object, mutated.
        """
        slippage_factor = slippage_pct / 100.0
        if order.direction == "BUY":
            fill = order.order_price * (1 + slippage_factor)
        else:
            fill = order.order_price * (1 - slippage_factor)

        order.fill_price = round(fill, 2)
        order.slippage_applied = round(
            abs(fill - order.order_price), 4
        )
        order.status = PaperOrderStatus.FILLED
        order.fill_timestamp = datetime.now(tz=IST).isoformat()

        logger.info(
            "Paper fill: %s %s %d × ₹%.2f (slippage ₹%.4f, id=%s)",
            order.direction,
            order.symbol,
            order.quantity,
            order.fill_price,
            order.slippage_applied,
            order.order_id,
        )
        return order

    # ── Position management ──────────────────────────────────────────

    def get_positions(self) -> list[dict[str, Any]]:
        """Return all open positions as dicts.

        Returns
        -------
        list[dict]
        """
        return [
            {
                "symbol": p.symbol,
                "direction": p.direction,
                "quantity": p.quantity,
                "entry_price": p.entry_price,
                "current_price": p.current_price,
                "unrealised_pnl": round(p.unrealised_pnl, 2),
                "entry_time": p.entry_time,
            }
            for p in self._positions
        ]

    def get_capital(self) -> float:
        """Return current available capital.

        Returns
        -------
        float
        """
        return round(self._available_capital, 2)

    def get_pnl(self) -> dict[str, float]:
        """Return realised and unrealised PnL breakdown.

        Returns
        -------
        dict
        """
        unrealised = sum(p.unrealised_pnl for p in self._positions)
        return {
            "realised_pnl": round(self._realised_pnl, 2),
            "unrealised_pnl": round(unrealised, 2),
            "total_pnl": round(self._realised_pnl + unrealised, 2),
            "initial_capital": self._initial_capital,
            "current_capital": round(
                self._available_capital + sum(
                    p.entry_price * p.quantity for p in self._positions
                ),
                2,
            ),
            "return_pct": round(
                ((self._available_capital + sum(
                    p.entry_price * p.quantity for p in self._positions
                ) + self._realised_pnl) / self._initial_capital - 1) * 100,
                2,
            ),
        }

    def update_prices(self, prices: dict[str, float]) -> None:
        """Update current prices and recalculate unrealised PnL.

        Parameters
        ----------
        prices : dict[str, float]
            ``{symbol: current_price}``
        """
        for pos in self._positions:
            if pos.symbol in prices:
                pos.current_price = prices[pos.symbol]
                if pos.direction == "BUY":
                    pos.unrealised_pnl = (
                        (pos.current_price - pos.entry_price) * pos.quantity
                    )
                else:
                    pos.unrealised_pnl = (
                        (pos.entry_price - pos.current_price) * pos.quantity
                    )

    def close_position(
        self,
        symbol: str,
        exit_price: float,
        quantity: Optional[int] = None,
    ) -> dict[str, Any]:
        """Close (fully or partially) an open position.

        Parameters
        ----------
        symbol : str
        exit_price : float
        quantity : int, optional
            Number of shares to close.  Defaults to full position.

        Returns
        -------
        dict
            Trade summary with PnL.
        """
        pos = next(
            (p for p in self._positions if p.symbol == symbol), None,
        )
        if pos is None:
            logger.warning("close_position: no open position for %s", symbol)
            return {"error": f"No open position for {symbol}"}

        close_qty = quantity or pos.quantity
        close_qty = min(close_qty, pos.quantity)

        if pos.direction == "BUY":
            pnl = (exit_price - pos.entry_price) * close_qty
        else:
            pnl = (pos.entry_price - exit_price) * close_qty

        self._realised_pnl += pnl
        self._available_capital += (exit_price * close_qty) if pos.direction == "BUY" else (
            pos.entry_price * close_qty + pnl
        )

        trade_record = {
            "symbol": symbol,
            "direction": pos.direction,
            "entry_price": pos.entry_price,
            "exit_price": round(exit_price, 2),
            "quantity": close_qty,
            "pnl": round(pnl, 2),
            "entry_time": pos.entry_time,
            "exit_time": datetime.now(tz=IST).isoformat(),
        }
        self._closed_trades.append(trade_record)

        # Update or remove position
        pos.quantity -= close_qty
        if pos.quantity <= 0:
            self._positions.remove(pos)

        logger.info(
            "Position closed: %s %s %d × ₹%.2f → ₹%.2f, PnL=₹%.2f",
            pos.direction,
            symbol,
            close_qty,
            pos.entry_price,
            exit_price,
            pnl,
        )
        return trade_record

    def get_trade_history(self) -> list[dict[str, Any]]:
        """Return all closed trades.

        Returns
        -------
        list[dict]
        """
        return self._closed_trades.copy()

    def reset(self) -> None:
        """Reset the paper trader to initial state."""
        self._available_capital = self._initial_capital
        self._positions.clear()
        self._orders.clear()
        self._closed_trades.clear()
        self._realised_pnl = 0.0
        logger.info("PaperTrader reset to initial state")

    # ── Internal ─────────────────────────────────────────────────────

    def _apply_fill(self, order: PaperOrder) -> None:
        """Apply a filled order to positions and capital."""
        if order.direction == "BUY":
            # Check for existing position in same symbol
            existing = next(
                (p for p in self._positions
                 if p.symbol == order.symbol and p.direction == "BUY"),
                None,
            )
            cost = order.fill_price * order.quantity

            if existing:
                # Average up
                total_qty = existing.quantity + order.quantity
                total_cost = (
                    existing.entry_price * existing.quantity + cost
                )
                existing.entry_price = round(total_cost / total_qty, 2)
                existing.quantity = total_qty
            else:
                self._positions.append(
                    PaperPosition(
                        symbol=order.symbol,
                        direction="BUY",
                        quantity=order.quantity,
                        entry_price=order.fill_price,
                        current_price=order.fill_price,
                    )
                )
            self._available_capital -= cost

        else:  # SELL
            # Check for existing long position to close
            existing = next(
                (p for p in self._positions
                 if p.symbol == order.symbol and p.direction == "BUY"),
                None,
            )
            if existing:
                close_qty = min(order.quantity, existing.quantity)
                pnl = (order.fill_price - existing.entry_price) * close_qty
                self._realised_pnl += pnl
                self._available_capital += order.fill_price * close_qty
                existing.quantity -= close_qty
                if existing.quantity <= 0:
                    self._positions.remove(existing)

                self._closed_trades.append({
                    "symbol": order.symbol,
                    "direction": "BUY",
                    "entry_price": existing.entry_price,
                    "exit_price": order.fill_price,
                    "quantity": close_qty,
                    "pnl": round(pnl, 2),
                    "exit_time": datetime.now(tz=IST).isoformat(),
                })
            else:
                # Open a short position
                self._positions.append(
                    PaperPosition(
                        symbol=order.symbol,
                        direction="SELL",
                        quantity=order.quantity,
                        entry_price=order.fill_price,
                        current_price=order.fill_price,
                    )
                )

        logger.debug(
            "Fill applied: capital=₹%.2f, positions=%d",
            self._available_capital,
            len(self._positions),
        )
