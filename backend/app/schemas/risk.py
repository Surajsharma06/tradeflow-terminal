"""
Pydantic schemas for risk management.

Covers risk status, metrics, drawdown tracking, and limit usage.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class DrawdownInfo(BaseModel):
    """Current and historical drawdown data."""

    current_drawdown: float = Field(..., description="Current drawdown %")
    max_drawdown: float = Field(..., description="Maximum drawdown %")
    drawdown_start: Optional[datetime] = None
    drawdown_duration_days: int = 0
    recovery_needed_pct: float = Field(0.0, description="% gain needed to recover")


class RiskMetrics(BaseModel):
    """Quantitative risk metrics for the portfolio."""

    capital_at_risk: float = Field(..., description="Total ₹ value at risk")
    capital_at_risk_pct: float
    value_at_risk_95: float = Field(..., description="VaR at 95% confidence (₹)")
    beta: float = Field(1.0, description="Portfolio beta vs NIFTY 50")
    sharpe_ratio: float
    sortino_ratio: float
    volatility_annual: float = Field(..., description="Annualised volatility %")
    avg_position_size: float
    max_position_size: float
    correlation_to_nifty: float = 0.0


class LimitUsage(BaseModel):
    """Current usage against configured risk limits."""

    period: str  # daily / weekly / monthly
    loss_limit: float
    current_loss: float
    usage_pct: float
    remaining: float
    breached: bool = False


class RiskStatus(BaseModel):
    """Complete risk dashboard response."""

    metrics: RiskMetrics
    drawdown: DrawdownInfo
    limits: list[LimitUsage]
    vix_level: float = Field(..., description="India VIX level")
    vix_status: str  # low / moderate / high / extreme
    open_positions: int
    max_positions: int
    paper_trading: bool = True
    timestamp: datetime
