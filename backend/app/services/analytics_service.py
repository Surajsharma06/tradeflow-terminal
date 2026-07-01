"""
Analytics Service — Performance analytics, strategy breakdown, and correlations.
"""

import logging
import random
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)

IST = timezone(timedelta(hours=5, minutes=30))


class AnalyticsService:
    """Service for portfolio analytics and performance reporting."""

    async def get_performance_data(self, period: str = "1Y") -> dict:
        """Get portfolio equity curve vs benchmark."""
        days_map = {"1W": 7, "1M": 30, "3M": 90, "6M": 180, "1Y": 365, "ALL": 730}
        days = days_map.get(period, 365)
        now = datetime.now(IST)

        portfolio_value = 1_000_000.0
        benchmark_value = 1_000_000.0
        data_points = []

        for i in range(days):
            dt = now - timedelta(days=days - i)
            if dt.weekday() >= 5:
                continue
            portfolio_value *= (1 + random.gauss(0.0008, 0.012))
            benchmark_value *= (1 + random.gauss(0.0005, 0.010))
            data_points.append({
                "date": dt.strftime("%Y-%m-%d"),
                "portfolio": round(portfolio_value, 2),
                "benchmark": round(benchmark_value, 2),
                "alpha": round(portfolio_value - benchmark_value, 2),
            })

        return {
            "period": period,
            "data": data_points,
            "summary": {
                "portfolio_return": round((portfolio_value / 1_000_000 - 1) * 100, 2),
                "benchmark_return": round((benchmark_value / 1_000_000 - 1) * 100, 2),
                "alpha": round((portfolio_value - benchmark_value) / 1_000_000 * 100, 2),
                "benchmark_name": "NIFTY 50",
            },
        }

    async def get_strategy_breakdown(self) -> list[dict]:
        """Get per-strategy performance stats."""
        strategies = [
            {"name": "Trend Following", "total_trades": 87, "win_rate": 62.1,
             "avg_win": 12450, "avg_loss": -6780, "profit_factor": 1.92,
             "total_pnl": 234560, "sharpe": 1.95},
            {"name": "Mean Reversion", "total_trades": 64, "win_rate": 68.8,
             "avg_win": 8920, "avg_loss": -5430, "profit_factor": 2.15,
             "total_pnl": 189340, "sharpe": 2.12},
            {"name": "Momentum Breakout", "total_trades": 42, "win_rate": 57.1,
             "avg_win": 18760, "avg_loss": -8950, "profit_factor": 1.78,
             "total_pnl": 156780, "sharpe": 1.67},
            {"name": "Scalping", "total_trades": 156, "win_rate": 71.2,
             "avg_win": 3450, "avg_loss": -2890, "profit_factor": 1.65,
             "total_pnl": 98760, "sharpe": 1.45},
            {"name": "Swing Trading", "total_trades": 38, "win_rate": 63.2,
             "avg_win": 22340, "avg_loss": -11230, "profit_factor": 1.89,
             "total_pnl": 178450, "sharpe": 1.82},
            {"name": "Options Strategy", "total_trades": 52, "win_rate": 73.1,
             "avg_win": 15670, "avg_loss": -12340, "profit_factor": 1.56,
             "total_pnl": 145230, "sharpe": 1.38},
        ]
        # Add slight randomization
        for s in strategies:
            s["total_pnl"] = round(s["total_pnl"] + random.gauss(0, 5000), 2)
            s["sharpe"] = round(s["sharpe"] + random.gauss(0, 0.05), 2)
        return strategies

    async def get_drawdown_data(self) -> dict:
        """Get underwater drawdown chart data."""
        days = 365
        now = datetime.now(IST)
        data = []
        peak = 1_000_000.0
        value = peak
        max_dd = 0

        for i in range(days):
            dt = now - timedelta(days=days - i)
            if dt.weekday() >= 5:
                continue
            value *= (1 + random.gauss(0.0005, 0.013))
            if value > peak:
                peak = value
            dd = (peak - value) / peak * 100
            if dd > max_dd:
                max_dd = dd
            data.append({
                "date": dt.strftime("%Y-%m-%d"),
                "drawdown": round(-dd, 3),
            })

        # Count recovery periods
        recoveries = 0
        in_dd = False
        for point in data:
            if point["drawdown"] < -1.0 and not in_dd:
                in_dd = True
            elif point["drawdown"] > -0.5 and in_dd:
                recoveries += 1
                in_dd = False

        return {
            "data": data,
            "summary": {
                "max_drawdown": round(-max_dd, 2),
                "avg_drawdown": round(sum(d["drawdown"] for d in data) / len(data), 2),
                "current_drawdown": data[-1]["drawdown"] if data else 0,
                "recoveries": recoveries,
                "longest_recovery_days": random.randint(8, 25),
            },
        }

    async def get_streak_data(self) -> dict:
        """Get win/loss streak data."""
        streaks = []
        trades_visual = []

        current_streak = 0
        streak_type = None

        for i in range(50):
            win = random.random() < 0.647
            trades_visual.append({
                "index": i,
                "result": "WIN" if win else "LOSS",
                "pnl": round(random.uniform(2000, 25000) if win else random.uniform(-15000, -1000), 2),
            })

            if win:
                if streak_type == "WIN":
                    current_streak += 1
                else:
                    if streak_type is not None:
                        streaks.append({"type": streak_type, "count": current_streak})
                    current_streak = 1
                    streak_type = "WIN"
            else:
                if streak_type == "LOSS":
                    current_streak += 1
                else:
                    if streak_type is not None:
                        streaks.append({"type": streak_type, "count": current_streak})
                    current_streak = 1
                    streak_type = "LOSS"

        if streak_type:
            streaks.append({"type": streak_type, "count": current_streak})

        win_streaks = [s["count"] for s in streaks if s["type"] == "WIN"]
        loss_streaks = [s["count"] for s in streaks if s["type"] == "LOSS"]

        return {
            "streaks": streaks,
            "trades": trades_visual,
            "current_streak": {"type": streak_type, "count": current_streak},
            "best_win_streak": max(win_streaks) if win_streaks else 0,
            "worst_loss_streak": max(loss_streaks) if loss_streaks else 0,
            "avg_win_streak": round(sum(win_streaks) / len(win_streaks), 1) if win_streaks else 0,
            "avg_loss_streak": round(sum(loss_streaks) / len(loss_streaks), 1) if loss_streaks else 0,
        }

    async def get_correlation_matrix(self) -> dict:
        """Get asset correlation matrix."""
        assets = ["NIFTY", "S&P 500", "BTC", "Gold", "Crude", "DXY", "EUR/USD"]
        n = len(assets)
        matrix = [[0.0] * n for _ in range(n)]

        # Realistic correlation values
        correlations = {
            (0, 1): 0.72, (0, 2): 0.35, (0, 3): -0.15, (0, 4): -0.28,
            (0, 5): -0.45, (0, 6): 0.38,
            (1, 2): 0.42, (1, 3): -0.22, (1, 4): -0.18, (1, 5): -0.52, (1, 6): 0.41,
            (2, 3): 0.15, (2, 4): 0.08, (2, 5): -0.38, (2, 6): 0.25,
            (3, 4): 0.32, (3, 5): -0.65, (3, 6): 0.58,
            (4, 5): 0.42, (4, 6): -0.35,
            (5, 6): -0.88,
        }

        for i in range(n):
            matrix[i][i] = 1.0
            for j in range(i + 1, n):
                val = correlations.get((i, j), round(random.uniform(-0.3, 0.3), 2))
                val = round(val + random.gauss(0, 0.03), 3)
                matrix[i][j] = val
                matrix[j][i] = val

        return {"assets": assets, "matrix": matrix}
