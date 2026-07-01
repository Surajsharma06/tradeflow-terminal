"""
Pydantic schemas for market data endpoints.

Covers index data, OHLCV candles, live price ticks, and market status.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class IndexData(BaseModel):
    """Single market index snapshot."""

    symbol: str = Field(..., description="Index ticker symbol")
    name: str = Field(..., description="Full index name")
    exchange: str = Field(..., description="Exchange code")
    value: float = Field(..., description="Current value")
    change: float = Field(..., description="Absolute change from previous close")
    change_pct: float = Field(..., description="Percentage change")
    high: float = Field(..., description="Day high")
    low: float = Field(..., description="Day low")
    prev_close: float = Field(..., description="Previous close")
    timestamp: datetime


class PriceData(BaseModel):
    """Real-time price tick for a symbol."""

    symbol: str
    price: float
    change: float
    change_pct: float
    volume: int
    bid: Optional[float] = None
    ask: Optional[float] = None
    timestamp: datetime


class OHLCV(BaseModel):
    """Single OHLCV candlestick."""

    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int


class MarketStatus(BaseModel):
    """Current market status (open / closed / pre-market)."""

    market: str
    status: str  # open, closed, pre_market, post_market
    next_open: Optional[datetime] = None
    next_close: Optional[datetime] = None
    timezone: str


class MarketRegimeResponse(BaseModel):
    """Detected market regime with confidence."""

    regime: str
    confidence: float = Field(..., ge=0, le=100)
    description: str
    indicators: dict
    timestamp: datetime


class MarketOverview(BaseModel):
    """Complete market overview across all tracked markets."""

    indian_indices: list[IndexData]
    us_indices: list[IndexData]
    market_status: list[MarketStatus]
    regime: MarketRegimeResponse
    timestamp: datetime
