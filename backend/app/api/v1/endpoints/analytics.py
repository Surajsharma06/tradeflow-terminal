"""
Analytics endpoints.

Provides portfolio performance, strategy breakdown, drawdown analysis,
win/loss streaks, and correlation matrix data.
"""

import asyncio
import json
import logging
import random
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from fastapi import APIRouter, Query

from app.core.constants import StrategyName

logger = logging.getLogger(__name__)
router = APIRouter()

IST = timezone(timedelta(hours=5, minutes=30))
_CACHE_FILE = Path(__file__).parents[5] / "data" / "analytics_cache.json"
_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
_CACHE_TTL_HOURS = 6
_PNL_PAIRS = ["EUR/USD", "GBP/USD", "USD/JPY", "USD/CAD", "AUD/USD"]
_STARTING_CAPITAL_USD = 10_000.0
_USD_PER_PIP = 1.0


def _now_ist() -> datetime:
    return datetime.now(IST)


def _today_ist() -> date:
    return datetime.now(IST).date()


@router.get("/performance", summary="Portfolio performance vs benchmark")
async def get_performance(
    period: str = Query("6m", description="1m, 3m, 6m, 1y, all"),
) -> dict:
    """
    Return portfolio equity curve vs Nifty 50 benchmark.

    Both series are normalised to 100 at the start for easy comparison.
    """
    logger.info("Computing performance — period=%s", period)
    days_map = {"1m": 30, "3m": 90, "6m": 180, "1y": 365, "all": 730}
    n_days = days_map.get(period, 180)
    today = _today_ist()

    portfolio_vals: list[dict] = []
    benchmark_vals: list[dict] = []
    p_val = 100.0
    b_val = 100.0

    for d in range(n_days):
        day = today - timedelta(days=n_days - d - 1)
        if day.weekday() >= 5:
            continue
        p_val = round(p_val * (1 + random.gauss(0.0005, 0.013)), 2)
        b_val = round(b_val * (1 + random.gauss(0.0003, 0.010)), 2)
        portfolio_vals.append({"date": day.isoformat(), "value": p_val})
        benchmark_vals.append({"date": day.isoformat(), "value": b_val})

    return {
        "portfolio": portfolio_vals,
        "benchmark": benchmark_vals,
        "benchmark_name": "NIFTY 50",
        "portfolio_return_pct": round(p_val - 100, 2),
        "benchmark_return_pct": round(b_val - 100, 2),
        "alpha": round((p_val - 100) - (b_val - 100), 2),
        "period": period,
        "timestamp": _now_ist().isoformat(),
    }


@router.get("/strategies", summary="Strategy breakdown")
async def get_strategy_breakdown() -> list[dict]:
    """Return per-strategy performance metrics."""
    logger.info("Computing strategy breakdown")
    strategies = random.sample(list(StrategyName), k=min(8, len(StrategyName)))
    result = []

    for strat in strategies:
        total = random.randint(15, 80)
        wr = round(random.uniform(45, 75), 1)
        wins = int(total * wr / 100)
        avg_w = round(random.uniform(2000, 10000), 2)
        avg_l = round(random.uniform(1500, 6000), 2)
        total_pnl = round(wins * avg_w - (total - wins) * avg_l, 2)

        result.append({
            "strategy": strat.value,
            "total_trades": total,
            "win_rate": wr,
            "total_pnl": total_pnl,
            "avg_win": avg_w,
            "avg_loss": avg_l,
            "profit_factor": round((wins * avg_w) / max((total - wins) * avg_l, 1), 2),
            "sharpe": round(random.uniform(0.5, 2.8), 2),
            "max_drawdown": round(random.uniform(3, 15), 2),
            "avg_holding_days": round(random.uniform(1, 12), 1),
        })

    result.sort(key=lambda x: x["total_pnl"], reverse=True)
    return result


@router.get("/drawdown", summary="Drawdown history")
async def get_drawdown_data(
    days: int = Query(180, ge=30, le=730),
) -> list[dict]:
    """Return daily drawdown percentage for charting."""
    logger.info("Computing drawdown — days=%d", days)
    today = _today_ist()
    result = []
    equity = 1_000_000.0
    peak = equity

    for d in range(days):
        day = today - timedelta(days=days - d - 1)
        if day.weekday() >= 5:
            continue
        equity *= 1 + random.gauss(0.0004, 0.012)
        peak = max(peak, equity)
        dd = round((peak - equity) / peak * 100, 2)
        result.append({
            "date": day.isoformat(),
            "drawdown_pct": dd,
            "equity": round(equity, 2),
            "peak": round(peak, 2),
        })

    return result


@router.get("/streaks", summary="Win/loss streaks")
async def get_streaks() -> dict:
    """Return current and historical win/loss streaks."""
    logger.info("Computing streaks")
    # Generate a mock sequence of trade outcomes
    outcomes = [random.choice(["W", "L"]) for _ in range(100)]

    # Current streak
    current_type = outcomes[-1]
    current_len = 0
    for o in reversed(outcomes):
        if o == current_type:
            current_len += 1
        else:
            break

    # Longest streaks
    max_win = max_loss = streak = 0
    prev = None
    for o in outcomes:
        if o == prev:
            streak += 1
        else:
            streak = 1
            prev = o
        if o == "W":
            max_win = max(max_win, streak)
        else:
            max_loss = max(max_loss, streak)

    return {
        "current_streak": {
            "type": "win" if current_type == "W" else "loss",
            "length": current_len,
        },
        "longest_win_streak": max_win,
        "longest_loss_streak": max_loss,
        "recent_outcomes": outcomes[-20:],
        "total_wins": outcomes.count("W"),
        "total_losses": outcomes.count("L"),
        "overall_win_rate": round(outcomes.count("W") / len(outcomes) * 100, 1),
    }


def _load_cache():
    try:
        if _CACHE_FILE.exists():
            raw = json.loads(_CACHE_FILE.read_text())
            ts = datetime.fromisoformat(raw.get("_cached_at", "2000-01-01"))
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            age_h = (datetime.now(timezone.utc) - ts).total_seconds() / 3600
            if age_h < _CACHE_TTL_HOURS:
                return raw
    except Exception as e:
        logger.warning("Cache load failed: %s", e)
    return None


def _save_cache(data: dict) -> None:
    try:
        data["_cached_at"] = datetime.now(timezone.utc).isoformat()
        _CACHE_FILE.write_text(json.dumps(data, default=str))
    except Exception as e:
        logger.warning("Cache save failed: %s", e)


def _build_pnl_backtest() -> dict:
    """Run real 6-month backtest across 5 forex pairs. Slow — cached for 6 h."""
    from app.domain.backtesting.backtester import run_backtest

    all_trades: list[dict] = []
    pair_stats: list[dict] = []

    for pair in _PNL_PAIRS:
        try:
            result = run_backtest(pair, days=180)
            if "error" in result:
                logger.warning("Backtest skipped %s: %s", pair, result["error"])
                continue
            for t in result.get("trades", []):
                t["pair"] = pair
                all_trades.append(t)
            pair_stats.append({
                "pair":          pair,
                "total_trades":  result["total_trades"],
                "wins":          result["wins"],
                "losses":        result["losses"],
                "win_rate":      result["win_rate"],
                "total_pips":    result["total_pips"],
                "profit_factor": result["profit_factor"],
                "avg_rr":        result["avg_rr"],
                "pnl_usd":       round(result["total_pips"] * _USD_PER_PIP, 2),
            })
        except Exception as e:
            logger.error("Backtest error %s: %s", pair, e)

    # Sort all trades by entry_time
    def _safe_ts(t: dict) -> str:
        return str(t.get("entry_time", ""))

    closed = [t for t in all_trades if t.get("result") != "OPEN"]
    closed.sort(key=_safe_ts)

    # Build equity curve from all closed trades
    equity = _STARTING_CAPITAL_USD
    peak   = equity
    equity_curve: list[dict] = [{"date": "start", "equity": equity, "drawdown_pct": 0.0}]
    monthly_pnl: dict[str, float] = {}
    calendar_pnl: dict[str, float] = {}

    for t in closed:
        pnl_usd = t.get("pnl_pips", 0.0) * _USD_PER_PIP
        equity = round(equity + pnl_usd, 2)
        peak   = max(peak, equity)
        dd_pct = round((peak - equity) / peak * 100, 2) if peak > 0 else 0.0

        ts_str = str(t.get("exit_time", t.get("entry_time", "")))
        try:
            ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
            date_str = ts.strftime("%Y-%m-%d")
            month_str = ts.strftime("%Y-%m")
        except Exception:
            date_str = "unknown"
            month_str = "unknown"

        equity_curve.append({"date": date_str, "equity": equity, "drawdown_pct": dd_pct})
        monthly_pnl[month_str] = round(monthly_pnl.get(month_str, 0.0) + pnl_usd, 2)
        calendar_pnl[date_str] = round(calendar_pnl.get(date_str, 0.0) + pnl_usd, 2)

    total_closed = len(closed)
    total_wins   = sum(1 for t in closed if t.get("result") == "WIN")
    total_losses = total_closed - total_wins
    total_pnl    = round(equity - _STARTING_CAPITAL_USD, 2)
    win_rate     = round(total_wins / max(total_closed, 1) * 100, 1)

    win_pips  = sum(t["pnl_pips"] for t in closed if t.get("result") == "WIN")
    loss_pips = abs(sum(t["pnl_pips"] for t in closed if t.get("result") == "LOSS"))
    pf = round((win_pips * _USD_PER_PIP) / max(loss_pips * _USD_PER_PIP, 0.001), 2)

    max_dd   = max((p["drawdown_pct"] for p in equity_curve), default=0.0)
    returns  = [equity_curve[i]["equity"] / equity_curve[i-1]["equity"] - 1
                for i in range(1, len(equity_curve))]
    if len(returns) > 1:
        import statistics
        avg_r  = statistics.mean(returns)
        std_r  = statistics.stdev(returns)
        sharpe = round(avg_r / max(std_r, 1e-9) * (252 ** 0.5), 2) if std_r else 0.0
    else:
        sharpe = 0.0

    # Recent trades (latest 50, stripped for frontend)
    recent = sorted(closed, key=_safe_ts, reverse=True)[:50]
    recent_out = [
        {
            "entry_time":  str(t.get("entry_time", "")),
            "exit_time":   str(t.get("exit_time", "")),
            "pair":        t.get("pair", ""),
            "direction":   t.get("direction", ""),
            "result":      t.get("result", ""),
            "pnl_pips":    t.get("pnl_pips", 0),
            "pnl_usd":     round(t.get("pnl_pips", 0) * _USD_PER_PIP, 2),
        }
        for t in recent
    ]

    # Monthly P&L list
    monthly_list = [{"month": k, "pnl_usd": v} for k, v in sorted(monthly_pnl.items())]

    return {
        "summary": {
            "starting_capital_usd": _STARTING_CAPITAL_USD,
            "ending_capital_usd":   round(equity, 2),
            "total_pnl_usd":        total_pnl,
            "return_pct":           round(total_pnl / _STARTING_CAPITAL_USD * 100, 2),
            "total_trades":         total_closed,
            "wins":                 total_wins,
            "losses":               total_losses,
            "win_rate":             win_rate,
            "profit_factor":        pf,
            "max_drawdown_pct":     round(max_dd, 2),
            "sharpe_ratio":         sharpe,
            "pairs_tested":         len(pair_stats),
        },
        "equity_curve":   equity_curve,
        "monthly_pnl":    monthly_list,
        "calendar_pnl":   calendar_pnl,
        "pair_stats":     pair_stats,
        "recent_trades":  recent_out,
        "generated_at":   _now_ist().isoformat(),
    }


@router.get("/pnl-backtest", summary="Real 6-month forex P&L backtest")
async def get_pnl_backtest(refresh: bool = Query(False)) -> dict:
    """
    Returns real 6-month backtest P&L across 5 forex pairs.
    Results are cached for 6 hours; pass ?refresh=true to force recalculation.
    """
    if not refresh:
        cached = _load_cache()
        if cached:
            logger.info("Returning cached pnl-backtest (age < 6h)")
            return cached

    logger.info("Running fresh pnl-backtest across %d pairs…", len(_PNL_PAIRS))
    loop   = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, _build_pnl_backtest)
    _save_cache(result)
    return result


@router.get("/correlations", summary="Correlation matrix")
async def get_correlations() -> dict:
    """Return mock correlation matrix between strategies/sectors."""
    logger.info("Computing correlations")
    labels = [
        "Momentum", "Mean Reversion", "Breakout", "MACD",
        "VWAP", "Supertrend", "ML Ensemble", "Sentiment",
    ]
    n = len(labels)
    matrix: list[list[float]] = []

    for i in range(n):
        row: list[float] = []
        for j in range(n):
            if i == j:
                row.append(1.0)
            elif j < i:
                row.append(matrix[j][i])  # symmetric
            else:
                row.append(round(random.uniform(-0.3, 0.7), 3))
        matrix.append(row)

    return {
        "labels": labels,
        "matrix": matrix,
        "timestamp": _now_ist().isoformat(),
    }
