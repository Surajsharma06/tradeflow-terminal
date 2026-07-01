"""
Pydantic schemas for portfolio, positions, and trades.

Used by the portfolio and trade-history endpoints.
"""

from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, Field


class PositionResponse(BaseModel):
    """An open position in the portfolio."""

    id: int
    symbol: str
    market: str
    direction: str
    entry_price: float
    current_price: float
    quantity: int
    unrealized_pnl: float
    unrealized_pnl_pct: float
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    strategy: Optional[str] = None
    opened_at: datetime
    holding_period_days: int = 0

    model_config = {"from_attributes": True}


class TradeResponse(BaseModel):
    """A completed (closed) trade."""

    id: int
    symbol: str
    market: str
    direction: str
    strategy: str
    entry_price: float
    exit_price: Optional[float] = None
    quantity: int
    pnl: float
    charges: float
    net_pnl: float
    score: Optional[float] = None
    status: str
    entry_time: datetime
    exit_time: Optional[datetime] = None

    model_config = {"from_attributes": True}


class DailyPnLResponse(BaseModel):
    """Daily PnL for the calendar heatmap."""

    date: date
    pnl: float
    trades_count: int
    wins: int
    losses: int
    cumulative_pnl: float = 0.0


class PortfolioSummary(BaseModel):
    """Aggregate portfolio statistics."""

    total_capital: float = Field(..., description="Total portfolio value (₹)")
    cash: float = Field(..., description="Available cash")
    used_capital: float = Field(..., description="Capital in open positions")
    used_capital_pct: float = Field(..., description="% of capital deployed")

    # P&L
    daily_pnl: float
    daily_pnl_pct: float
    weekly_pnl: float
    monthly_pnl: float
    total_pnl: float
    total_pnl_pct: float

    # Positions
    open_positions: int
    total_trades: int
    win_rate: float

    # Risk
    current_drawdown: float
    max_drawdown: float

    # Paper trading
    is_paper: bool = True
    timestamp: datetime
