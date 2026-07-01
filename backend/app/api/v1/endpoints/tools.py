"""
Trading tools endpoints.

Position sizing calculator, Indian brokerage charges calculator,
and mock economic calendar.
"""

import logging
import random
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.core.constants import INDIAN_CHARGES

logger = logging.getLogger(__name__)
router = APIRouter()

IST = timezone(timedelta(hours=5, minutes=30))


def _now_ist() -> datetime:
    return datetime.now(IST)


# ═════════════════════════════════════════════════════════════════════
# Request / Response Models
# ═════════════════════════════════════════════════════════════════════

class PositionSizeRequest(BaseModel):
    """Input for position size calculation."""

    capital: float = Field(..., gt=0, description="Total available capital (₹)")
    risk_pct: float = Field(2.0, gt=0, le=100, description="% of capital to risk")
    entry_price: float = Field(..., gt=0)
    stop_loss: float = Field(..., gt=0)
    max_pct_per_trade: float = Field(5.0, gt=0, le=100)


class PositionSizeResponse(BaseModel):
    """Calculated position sizing result."""

    quantity: int
    position_value: float
    risk_amount: float
    risk_per_share: float
    position_pct_of_capital: float
    max_loss: float


class ChargesRequest(BaseModel):
    """Input for brokerage charges calculation."""

    buy_price: float = Field(..., gt=0)
    sell_price: float = Field(..., gt=0)
    quantity: int = Field(..., gt=0)
    segment: str = Field("delivery", description="delivery, intraday, futures, options")
    exchange: str = Field("NSE", description="NSE or BSE")


class ChargesResponse(BaseModel):
    """Itemised brokerage charges breakdown."""

    turnover: float
    brokerage: float
    stt: float
    exchange_charges: float
    gst: float
    sebi_fee: float
    stamp_duty: float
    total_charges: float
    net_pnl: float
    breakeven_points: float


# ═════════════════════════════════════════════════════════════════════
# Endpoints
# ═════════════════════════════════════════════════════════════════════

@router.post(
    "/position-size",
    response_model=PositionSizeResponse,
    summary="Calculate position size",
)
async def calculate_position_size(req: PositionSizeRequest) -> PositionSizeResponse:
    """
    Calculate the optimal position size based on capital, risk tolerance,
    entry price, and stop loss.

    Uses the fixed-fractional risk model: risk a fixed % of capital,
    then derive quantity from the per-share risk (entry – stop loss).
    """
    logger.info(
        "Position size calc — capital=₹%.0f, risk=%.1f%%, entry=%.2f, sl=%.2f",
        req.capital, req.risk_pct, req.entry_price, req.stop_loss,
    )

    risk_amount = req.capital * req.risk_pct / 100
    risk_per_share = abs(req.entry_price - req.stop_loss)

    if risk_per_share == 0:
        risk_per_share = req.entry_price * 0.02  # fallback 2 %

    quantity = int(risk_amount / risk_per_share)

    # Cap by max % of capital per trade
    max_value = req.capital * req.max_pct_per_trade / 100
    max_qty_by_capital = int(max_value / req.entry_price)
    quantity = min(quantity, max_qty_by_capital)
    quantity = max(quantity, 1)

    position_value = round(quantity * req.entry_price, 2)
    max_loss = round(quantity * risk_per_share, 2)

    return PositionSizeResponse(
        quantity=quantity,
        position_value=position_value,
        risk_amount=round(risk_amount, 2),
        risk_per_share=round(risk_per_share, 2),
        position_pct_of_capital=round(position_value / req.capital * 100, 2),
        max_loss=max_loss,
    )


@router.post(
    "/charges",
    response_model=ChargesResponse,
    summary="Calculate brokerage charges",
)
async def calculate_charges(req: ChargesRequest) -> ChargesResponse:
    """
    Calculate full Indian brokerage charges including STT, exchange fees,
    GST, SEBI fee, and stamp duty for the given trade parameters.
    """
    logger.info(
        "Charges calc — buy=%.2f, sell=%.2f, qty=%d, segment=%s",
        req.buy_price, req.sell_price, req.quantity, req.segment,
    )

    buy_val = req.buy_price * req.quantity
    sell_val = req.sell_price * req.quantity
    turnover = buy_val + sell_val

    # Brokerage
    if req.segment == "delivery":
        brokerage = 0.0  # free delivery (Zerodha model)
    else:
        brokerage_raw = turnover * INDIAN_CHARGES["brokerage_intraday"]
        brokerage = min(brokerage_raw, INDIAN_CHARGES["brokerage_max_per_order"] * 2)

    # STT
    if req.segment == "delivery":
        stt = buy_val * INDIAN_CHARGES["stt_delivery_buy"] + sell_val * INDIAN_CHARGES["stt_delivery_sell"]
    elif req.segment == "intraday":
        stt = sell_val * INDIAN_CHARGES["stt_intraday_sell"]
    else:
        stt = sell_val * INDIAN_CHARGES["stt_fno_sell"]

    # Exchange charges
    exc_rate = (
        INDIAN_CHARGES["exchange_nse"]
        if req.exchange.upper() == "NSE"
        else INDIAN_CHARGES["exchange_bse"]
    )
    exchange_charges = turnover * exc_rate

    # GST on brokerage + exchange charges
    gst = (brokerage + exchange_charges) * INDIAN_CHARGES["gst_rate"]

    # SEBI fee
    sebi_fee = turnover * INDIAN_CHARGES["sebi_fee"]

    # Stamp duty (buy side only)
    stamp_key = f"stamp_duty_{req.segment}" if f"stamp_duty_{req.segment}" in INDIAN_CHARGES else "stamp_duty_delivery"
    stamp_duty = buy_val * INDIAN_CHARGES[stamp_key]

    total = round(brokerage + stt + exchange_charges + gst + sebi_fee + stamp_duty, 2)
    gross_pnl = round((req.sell_price - req.buy_price) * req.quantity, 2)
    net_pnl = round(gross_pnl - total, 2)
    breakeven = round(total / req.quantity, 2) if req.quantity > 0 else 0

    return ChargesResponse(
        turnover=round(turnover, 2),
        brokerage=round(brokerage, 2),
        stt=round(stt, 2),
        exchange_charges=round(exchange_charges, 2),
        gst=round(gst, 2),
        sebi_fee=round(sebi_fee, 2),
        stamp_duty=round(stamp_duty, 2),
        total_charges=total,
        net_pnl=net_pnl,
        breakeven_points=breakeven,
    )


@router.get("/calendar", summary="Economic calendar")
async def get_economic_calendar() -> list[dict]:
    """
    Return a mock economic calendar of upcoming events.

    Includes RBI policy, US Fed, GDP, inflation, earnings, and
    Indian market holidays.
    """
    logger.info("Fetching economic calendar")
    now = _now_ist()

    events = [
        {
            "date": (now + timedelta(days=2)).strftime("%Y-%m-%d"),
            "time": "10:00 IST",
            "event": "RBI Monetary Policy Decision",
            "country": "IN",
            "impact": "high",
            "previous": "6.50%",
            "forecast": "6.25%",
        },
        {
            "date": (now + timedelta(days=3)).strftime("%Y-%m-%d"),
            "time": "18:30 IST",
            "event": "US Non-Farm Payrolls",
            "country": "US",
            "impact": "high",
            "previous": "175K",
            "forecast": "180K",
        },
        {
            "date": (now + timedelta(days=5)).strftime("%Y-%m-%d"),
            "time": "17:30 IST",
            "event": "India CPI Inflation (YoY)",
            "country": "IN",
            "impact": "high",
            "previous": "4.75%",
            "forecast": "4.60%",
        },
        {
            "date": (now + timedelta(days=7)).strftime("%Y-%m-%d"),
            "time": "09:00 IST",
            "event": "India GDP Growth Rate (Q4)",
            "country": "IN",
            "impact": "high",
            "previous": "8.4%",
            "forecast": "7.8%",
        },
        {
            "date": (now + timedelta(days=8)).strftime("%Y-%m-%d"),
            "time": "00:00 IST",
            "event": "US FOMC Meeting Minutes",
            "country": "US",
            "impact": "medium",
            "previous": None,
            "forecast": None,
        },
        {
            "date": (now + timedelta(days=10)).strftime("%Y-%m-%d"),
            "time": "After Market",
            "event": "TCS Q1 FY26 Results",
            "country": "IN",
            "impact": "medium",
            "previous": "EPS ₹65.2",
            "forecast": "EPS ₹68.0",
        },
        {
            "date": (now + timedelta(days=12)).strftime("%Y-%m-%d"),
            "time": "18:00 IST",
            "event": "US CPI Inflation (MoM)",
            "country": "US",
            "impact": "high",
            "previous": "0.3%",
            "forecast": "0.2%",
        },
        {
            "date": (now + timedelta(days=14)).strftime("%Y-%m-%d"),
            "time": "All Day",
            "event": "NSE Holiday — Independence Day",
            "country": "IN",
            "impact": "info",
            "previous": None,
            "forecast": None,
        },
        {
            "date": (now + timedelta(days=15)).strftime("%Y-%m-%d"),
            "time": "After Market",
            "event": "Reliance Industries Q1 Results",
            "country": "IN",
            "impact": "high",
            "previous": "EPS ₹17.8",
            "forecast": "EPS ₹18.5",
        },
        {
            "date": (now + timedelta(days=18)).strftime("%Y-%m-%d"),
            "time": "14:00 IST",
            "event": "India WPI Inflation (YoY)",
            "country": "IN",
            "impact": "medium",
            "previous": "1.26%",
            "forecast": "1.10%",
        },
    ]

    return events
