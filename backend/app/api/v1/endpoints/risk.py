"""
Risk management endpoints.

Returns mock risk metrics, drawdown data, and limit usage for
daily, weekly, and monthly loss thresholds.
"""

import logging
import random
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter

from app.schemas.risk import (
    DrawdownInfo,
    LimitUsage,
    RiskMetrics,
    RiskStatus,
)

logger = logging.getLogger(__name__)
router = APIRouter()

IST = timezone(timedelta(hours=5, minutes=30))


def _now_ist() -> datetime:
    return datetime.now(IST)


@router.get("/status", response_model=RiskStatus, summary="Risk status")
async def get_risk_status() -> RiskStatus:
    """
    Return the complete risk dashboard including capital-at-risk,
    VaR, drawdown, India VIX, and limit usage.
    """
    logger.info("Computing risk status")
    total_capital = 1_000_000.0

    car = round(random.uniform(25000, 80000), 2)
    car_pct = round(car / total_capital * 100, 2)
    vix = round(random.uniform(11, 24), 2)

    if vix < 13:
        vix_status = "low"
    elif vix < 18:
        vix_status = "moderate"
    elif vix < 25:
        vix_status = "high"
    else:
        vix_status = "extreme"

    metrics = RiskMetrics(
        capital_at_risk=car,
        capital_at_risk_pct=car_pct,
        value_at_risk_95=round(car * random.uniform(0.3, 0.7), 2),
        beta=round(random.uniform(0.7, 1.4), 2),
        sharpe_ratio=round(random.uniform(0.8, 2.5), 2),
        sortino_ratio=round(random.uniform(1.0, 3.0), 2),
        volatility_annual=round(random.uniform(12, 28), 1),
        avg_position_size=round(random.uniform(30000, 80000), 2),
        max_position_size=round(random.uniform(80000, 150000), 2),
        correlation_to_nifty=round(random.uniform(0.3, 0.85), 2),
    )

    dd_current = round(random.uniform(0.5, 6.0), 2)
    dd_max = round(random.uniform(6.0, 15.0), 2)
    drawdown = DrawdownInfo(
        current_drawdown=dd_current,
        max_drawdown=dd_max,
        drawdown_start=_now_ist() - timedelta(days=random.randint(1, 20)),
        drawdown_duration_days=random.randint(1, 15),
        recovery_needed_pct=round(dd_current / (100 - dd_current) * 100, 2),
    )

    # Daily / Weekly / Monthly limits
    daily_limit = total_capital * 0.03  # 3 %
    weekly_limit = total_capital * 0.07
    monthly_limit = total_capital * 0.12

    daily_loss = round(random.uniform(0, daily_limit * 0.8), 2)
    weekly_loss = round(random.uniform(daily_loss, weekly_limit * 0.6), 2)
    monthly_loss = round(random.uniform(weekly_loss, monthly_limit * 0.5), 2)

    limits = [
        LimitUsage(
            period="daily",
            loss_limit=daily_limit,
            current_loss=daily_loss,
            usage_pct=round(daily_loss / daily_limit * 100, 1),
            remaining=round(daily_limit - daily_loss, 2),
            breached=daily_loss >= daily_limit,
        ),
        LimitUsage(
            period="weekly",
            loss_limit=weekly_limit,
            current_loss=weekly_loss,
            usage_pct=round(weekly_loss / weekly_limit * 100, 1),
            remaining=round(weekly_limit - weekly_loss, 2),
            breached=weekly_loss >= weekly_limit,
        ),
        LimitUsage(
            period="monthly",
            loss_limit=monthly_limit,
            current_loss=monthly_loss,
            usage_pct=round(monthly_loss / monthly_limit * 100, 1),
            remaining=round(monthly_limit - monthly_loss, 2),
            breached=monthly_loss >= monthly_limit,
        ),
    ]

    return RiskStatus(
        metrics=metrics,
        drawdown=drawdown,
        limits=limits,
        vix_level=vix,
        vix_status=vix_status,
        open_positions=random.randint(3, 5),
        max_positions=10,
        paper_trading=True,
        timestamp=_now_ist(),
    )


@router.get("/limits", response_model=list[LimitUsage], summary="Limit usage")
async def get_limit_usage() -> list[LimitUsage]:
    """Return current usage against daily, weekly, and monthly loss limits."""
    logger.info("Fetching limit usage")
    status = await get_risk_status()
    return status.limits
