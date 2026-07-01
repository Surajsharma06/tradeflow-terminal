"""
Portfolio endpoints.

Returns mock open positions, portfolio summary, trade history,
and daily PnL data for calendar views. All Indian prices in ₹.
"""

import logging
import random
from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Query

from app.core.constants import INDIAN_STOCKS, StrategyName
from app.schemas.portfolio import (
    DailyPnLResponse,
    PortfolioSummary,
    PositionResponse,
    TradeResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter()

IST = timezone(timedelta(hours=5, minutes=30))


def _now_ist() -> datetime:
    return datetime.now(IST)


def _today_ist() -> date:
    return datetime.now(IST).date()


# ═════════════════════════════════════════════════════════════════════

@router.get("/positions", response_model=list[PositionResponse], summary="Open positions")
async def get_positions() -> list[PositionResponse]:
    """
    Return 3-5 mock open positions with realistic Indian stock data.

    Each position shows entry price, current price, unrealised P&L,
    stop loss, take profit, and holding period.
    """
    logger.info("Fetching open positions")
    symbols = random.sample(list(INDIAN_STOCKS.keys()), k=random.randint(3, 5))
    positions = []

    for i, sym in enumerate(symbols, start=1):
        stock = INDIAN_STOCKS[sym]
        base = stock["base_price"]
        direction = random.choice(["long", "short"])
        entry = round(base * random.uniform(0.96, 1.02), 2)
        current = round(base * random.uniform(0.97, 1.05), 2)
        qty = random.choice([5, 10, 15, 20, 25, 50])
        opened = _now_ist() - timedelta(days=random.randint(1, 30))

        if direction == "long":
            pnl = round((current - entry) * qty, 2)
            sl = round(entry * 0.975, 2)
            tp = round(entry * 1.06, 2)
        else:
            pnl = round((entry - current) * qty, 2)
            sl = round(entry * 1.025, 2)
            tp = round(entry * 0.94, 2)

        pnl_pct = round((pnl / (entry * qty)) * 100, 2)
        holding = (_now_ist() - opened).days

        positions.append(PositionResponse(
            id=i,
            symbol=sym,
            market="indian_equity",
            direction=direction,
            entry_price=entry,
            current_price=current,
            quantity=qty,
            unrealized_pnl=pnl,
            unrealized_pnl_pct=pnl_pct,
            stop_loss=sl,
            take_profit=tp,
            strategy=random.choice(list(StrategyName)).value,
            opened_at=opened,
            holding_period_days=holding,
        ))

    return positions


@router.get("/summary", response_model=PortfolioSummary, summary="Portfolio summary")
async def get_portfolio_summary() -> PortfolioSummary:
    """Return aggregate portfolio statistics including P&L and risk metrics."""
    logger.info("Computing portfolio summary")
    total_capital = 1_000_000.0
    used_pct = round(random.uniform(25, 65), 1)
    used = round(total_capital * used_pct / 100, 2)
    cash = round(total_capital - used, 2)

    daily = round(random.uniform(-15000, 25000), 2)
    weekly = round(random.uniform(-30000, 50000), 2)
    monthly = round(random.uniform(-40000, 120000), 2)
    total_pnl = round(random.uniform(50000, 250000), 2)

    return PortfolioSummary(
        total_capital=total_capital + total_pnl,
        cash=cash,
        used_capital=used,
        used_capital_pct=used_pct,
        daily_pnl=daily,
        daily_pnl_pct=round(daily / total_capital * 100, 2),
        weekly_pnl=weekly,
        monthly_pnl=monthly,
        total_pnl=total_pnl,
        total_pnl_pct=round(total_pnl / total_capital * 100, 2),
        open_positions=random.randint(3, 5),
        total_trades=random.randint(80, 250),
        win_rate=round(random.uniform(55, 72), 1),
        current_drawdown=round(random.uniform(0.5, 5.0), 2),
        max_drawdown=round(random.uniform(5.0, 12.0), 2),
        is_paper=True,
        timestamp=_now_ist(),
    )


@router.get("/trades", response_model=list[TradeResponse], summary="Trade history")
async def get_trade_history(
    limit: int = Query(20, ge=1, le=200),
) -> list[TradeResponse]:
    """Return mock completed trade history with P&L and charges."""
    logger.info("Fetching trade history — limit=%d", limit)
    trades = []
    symbols = list(INDIAN_STOCKS.keys())

    for i in range(limit):
        sym = random.choice(symbols)
        stock = INDIAN_STOCKS[sym]
        base = stock["base_price"]
        direction = random.choice(["long", "short"])
        strategy = random.choice(list(StrategyName)).value
        entry = round(base * random.uniform(0.95, 1.05), 2)
        qty = random.choice([5, 10, 15, 20, 25, 50])

        # Exit with some win bias
        if random.random() < 0.6:  # 60 % win rate
            if direction == "long":
                exit_p = round(entry * random.uniform(1.01, 1.08), 2)
            else:
                exit_p = round(entry * random.uniform(0.92, 0.99), 2)
        else:
            if direction == "long":
                exit_p = round(entry * random.uniform(0.95, 0.995), 2)
            else:
                exit_p = round(entry * random.uniform(1.005, 1.05), 2)

        if direction == "long":
            pnl = round((exit_p - entry) * qty, 2)
        else:
            pnl = round((entry - exit_p) * qty, 2)

        charges = round(abs(entry * qty) * 0.001 + abs(exit_p * qty) * 0.001, 2)
        net = round(pnl - charges, 2)

        entry_time = _now_ist() - timedelta(days=random.randint(1, 90))
        exit_time = entry_time + timedelta(hours=random.randint(1, 120))

        trades.append(TradeResponse(
            id=200 + i,
            symbol=sym,
            market="indian_equity",
            direction=direction,
            strategy=strategy,
            entry_price=entry,
            exit_price=exit_p,
            quantity=qty,
            pnl=pnl,
            charges=charges,
            net_pnl=net,
            score=round(random.uniform(50, 95), 1),
            status="closed",
            entry_time=entry_time,
            exit_time=exit_time,
        ))

    # Sort by most recent first
    trades.sort(key=lambda t: t.entry_time, reverse=True)
    return trades


@router.get("/pnl/daily", response_model=list[DailyPnLResponse], summary="Daily PnL")
async def get_daily_pnl(
    days: int = Query(90, ge=7, le=365),
) -> list[DailyPnLResponse]:
    """Return daily PnL data for calendar heatmap visualisation."""
    logger.info("Generating daily PnL — days=%d", days)
    today = _today_ist()
    result = []
    cumulative = 0.0

    for d in range(days):
        day = today - timedelta(days=days - d - 1)
        # Skip weekends
        if day.weekday() >= 5:
            continue

        trades_count = random.randint(0, 8)
        if trades_count == 0:
            pnl = 0.0
            wins = 0
            losses = 0
        else:
            wins = random.randint(0, trades_count)
            losses = trades_count - wins
            pnl = round(random.uniform(-20000, 30000), 2)

        cumulative += pnl
        result.append(DailyPnLResponse(
            date=day,
            pnl=pnl,
            trades_count=trades_count,
            wins=wins,
            losses=losses,
            cumulative_pnl=round(cumulative, 2),
        ))

    return result
