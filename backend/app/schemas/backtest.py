"""
Pydantic schemas for backtesting.

Covers backtest requests, responses, and detailed performance metrics.
"""

from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, Field


class BacktestRequest(BaseModel):
    """Request body to run a backtest."""

    symbol: str = Field(..., description="Symbol to backtest")
    strategy: str = Field(..., description="Strategy name")
    start_date: date
    end_date: date
    initial_capital: float = Field(1_000_000.0, gt=0)
    stop_loss_pct: float = Field(2.0, gt=0, le=50)
    take_profit_pct: float = Field(4.0, gt=0, le=100)
    position_size_pct: float = Field(5.0, gt=0, le=100)
    commission_pct: float = Field(0.03, ge=0)


class BacktestMetrics(BaseModel):
    """Performance metrics from a backtest run."""

    total_return: float = Field(..., description="Total return %")
    cagr: float = Field(..., description="Compound Annual Growth Rate %")
    sharpe: float = Field(..., description="Sharpe Ratio")
    sortino: float = Field(..., description="Sortino Ratio")
    max_drawdown: float = Field(..., description="Maximum Drawdown %")
    win_rate: float = Field(..., description="Win Rate %")
    profit_factor: float
    total_trades: int
    winning_trades: int
    losing_trades: int
    avg_win: float
    avg_loss: float
    largest_win: float
    largest_loss: float
    avg_holding_period_days: float
    expectancy: float = Field(..., description="Expected value per trade (₹)")
    recovery_factor: float
    calmar_ratio: float


class EquityCurvePoint(BaseModel):
    """Single point on the equity curve."""

    date: date
    equity: float
    drawdown: float
    benchmark: Optional[float] = None


class BacktestResponse(BaseModel):
    """Complete backtest result returned to the frontend."""

    id: int
    symbol: str
    strategy: str
    start_date: date
    end_date: date
    initial_capital: float
    final_capital: float
    metrics: BacktestMetrics
    equity_curve: list[EquityCurvePoint]
    monthly_returns: list[dict]
    created_at: datetime
