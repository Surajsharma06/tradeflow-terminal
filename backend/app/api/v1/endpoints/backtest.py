"""
Backtest endpoints.

Accepts backtest requests and returns mock backtest results with
equity curves, metrics, and monthly return breakdowns.
"""

import logging
import random
from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Query

from app.schemas.backtest import (
    BacktestMetrics,
    BacktestRequest,
    BacktestResponse,
    EquityCurvePoint,
)

logger = logging.getLogger(__name__)
router = APIRouter()

IST = timezone(timedelta(hours=5, minutes=30))


def _now_ist() -> datetime:
    return datetime.now(IST)


def _generate_equity_curve(
    start: date, end: date, initial: float
) -> list[EquityCurvePoint]:
    """Generate a realistic-looking equity curve via random walk."""
    points: list[EquityCurvePoint] = []
    equity = initial
    benchmark = initial
    peak = initial
    current = start

    while current <= end:
        # Skip weekends
        if current.weekday() < 5:
            daily_return = random.gauss(0.0005, 0.012)  # slight positive drift
            equity = round(equity * (1 + daily_return), 2)
            peak = max(peak, equity)
            dd = round((peak - equity) / peak * 100, 2)

            bench_return = random.gauss(0.0003, 0.010)
            benchmark = round(benchmark * (1 + bench_return), 2)

            points.append(EquityCurvePoint(
                date=current,
                equity=equity,
                drawdown=dd,
                benchmark=benchmark,
            ))

        current += timedelta(days=1)

    return points


def _generate_monthly_returns(start: date, end: date) -> list[dict]:
    """Generate mock monthly return data."""
    months = []
    current = start.replace(day=1)
    while current <= end:
        ret = round(random.gauss(1.5, 4.0), 2)
        months.append({
            "year": current.year,
            "month": current.month,
            "return_pct": ret,
            "trades": random.randint(5, 30),
        })
        # Move to next month
        if current.month == 12:
            current = current.replace(year=current.year + 1, month=1)
        else:
            current = current.replace(month=current.month + 1)
    return months


@router.post("/run", response_model=BacktestResponse, summary="Run backtest")
async def run_backtest(request: BacktestRequest) -> BacktestResponse:
    """
    Accept a BacktestRequest and return a mock BacktestResponse with
    full metrics, equity curve, and monthly returns.
    """
    logger.info(
        "Running backtest — %s on %s from %s to %s",
        request.strategy,
        request.symbol,
        request.start_date,
        request.end_date,
    )

    equity_curve = _generate_equity_curve(
        request.start_date, request.end_date, request.initial_capital
    )

    final_equity = equity_curve[-1].equity if equity_curve else request.initial_capital
    total_return_pct = round(
        (final_equity - request.initial_capital) / request.initial_capital * 100, 2
    )

    days = (request.end_date - request.start_date).days
    years = max(days / 365.25, 0.1)
    cagr = round(((final_equity / request.initial_capital) ** (1 / years) - 1) * 100, 2)

    max_dd = max((p.drawdown for p in equity_curve), default=0.0)

    total_trades = random.randint(40, 200)
    win_rate = round(random.uniform(50, 70), 1)
    wins = int(total_trades * win_rate / 100)
    losses = total_trades - wins

    avg_win = round(random.uniform(2000, 8000), 2)
    avg_loss = round(random.uniform(1500, 5000), 2)
    pf = round((wins * avg_win) / max(losses * avg_loss, 1), 2)

    metrics = BacktestMetrics(
        total_return=total_return_pct,
        cagr=cagr,
        sharpe=round(random.uniform(0.8, 2.8), 2),
        sortino=round(random.uniform(1.0, 3.5), 2),
        max_drawdown=round(max_dd, 2),
        win_rate=win_rate,
        profit_factor=pf,
        total_trades=total_trades,
        winning_trades=wins,
        losing_trades=losses,
        avg_win=avg_win,
        avg_loss=avg_loss,
        largest_win=round(avg_win * random.uniform(2.5, 5.0), 2),
        largest_loss=round(avg_loss * random.uniform(2.0, 4.0), 2),
        avg_holding_period_days=round(random.uniform(1, 15), 1),
        expectancy=round((win_rate / 100 * avg_win) - ((100 - win_rate) / 100 * avg_loss), 2),
        recovery_factor=round(total_return_pct / max(max_dd, 0.01), 2),
        calmar_ratio=round(cagr / max(max_dd, 0.01), 2),
    )

    return BacktestResponse(
        id=random.randint(1, 9999),
        symbol=request.symbol,
        strategy=request.strategy,
        start_date=request.start_date,
        end_date=request.end_date,
        initial_capital=request.initial_capital,
        final_capital=final_equity,
        metrics=metrics,
        equity_curve=equity_curve,
        monthly_returns=_generate_monthly_returns(request.start_date, request.end_date),
        created_at=_now_ist(),
    )


@router.get("/results", summary="Saved backtest results")
async def list_backtest_results(
    limit: int = Query(10, ge=1, le=50),
) -> list[dict]:
    """Return a list of previously saved backtest results (mock)."""
    logger.info("Listing backtest results — limit=%d", limit)
    strategies = ["momentum", "mean_reversion", "breakout", "trend_following", "macd_crossover"]
    symbols = ["RELIANCE", "TCS", "HDFCBANK", "INFY", "ICICIBANK", "SBIN", "ITC"]

    results = []
    for i in range(limit):
        end_d = date.today() - timedelta(days=random.randint(1, 30))
        start_d = end_d - timedelta(days=random.randint(180, 720))
        results.append({
            "id": i + 1,
            "symbol": random.choice(symbols),
            "strategy": random.choice(strategies),
            "start_date": start_d.isoformat(),
            "end_date": end_d.isoformat(),
            "total_return": round(random.uniform(-10, 45), 2),
            "sharpe": round(random.uniform(0.5, 2.5), 2),
            "max_drawdown": round(random.uniform(5, 20), 2),
            "win_rate": round(random.uniform(45, 70), 1),
            "total_trades": random.randint(30, 200),
            "created_at": _now_ist().isoformat(),
        })
    return results
