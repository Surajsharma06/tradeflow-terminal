"""
Pydantic schemas for trading signals.

Covers signal creation, response, and score breakdown.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class SignalScoreBreakdown(BaseModel):
    """Detailed breakdown of how a signal score was computed."""

    technical_score: float = Field(0.0, ge=0, le=100, description="Technical indicators score")
    sentiment_score: float = Field(0.0, ge=0, le=100, description="News & social sentiment score")
    volume_score: float = Field(0.0, ge=0, le=100, description="Volume analysis score")
    regime_score: float = Field(0.0, ge=0, le=100, description="Market regime alignment score")
    macro_score: float = Field(0.0, ge=0, le=100, description="Macro economic score")


class SignalCreate(BaseModel):
    """Request schema to create a new signal (internal use)."""

    symbol: str
    market: str = "indian_equity"
    direction: str = Field(..., pattern="^(long|short)$")
    strategy: str
    score: float = Field(..., ge=0, le=100)
    breakdown: SignalScoreBreakdown
    entry_price: float = Field(..., gt=0)
    stop_loss: Optional[float] = None
    target_price: Optional[float] = None


class SignalResponse(BaseModel):
    """Full signal detail returned to the frontend."""

    id: int
    symbol: str
    market: str
    direction: str
    strategy: str
    score: float
    breakdown: SignalScoreBreakdown
    entry_price: float
    stop_loss: Optional[float] = None
    target_price: Optional[float] = None
    risk_reward: Optional[float] = None
    status: str
    created_at: datetime
    expires_at: Optional[datetime] = None

    model_config = {"from_attributes": True}
