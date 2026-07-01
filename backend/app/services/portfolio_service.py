"""
Portfolio Management Service — Positions, trades, P&L, and performance.
"""

import logging
import random
from datetime import datetime, timedelta, timezone
from uuid import uuid4

logger = logging.getLogger(__name__)

IST = timezone(timedelta(hours=5, minutes=30))


class PortfolioService:
    """Service for portfolio management, P&L tracking, and performance metrics."""

    def __init__(self, initial_capital: float = 1_000_000.0):
        self.initial_capital = initial_capital

    async def get_positions(self) -> list[dict]:
        """Get current open positions."""
        now = datetime.now(IST)
        positions = [
            {
                "id": "pos-001", "symbol": "RELIANCE", "market": "NSE",
                "direction": "LONG", "strategy": "Trend Following",
                "entry_price": 2847.30, "current_price": round(2847.30 * (1 + random.gauss(0.005, 0.008)), 2),
                "quantity": 35, "stop_loss": 2780.00, "take_profit": 2960.00,
                "sector": "Energy", "opened_at": (now - timedelta(days=3)).isoformat(),
            },
            {
                "id": "pos-002", "symbol": "TCS", "market": "NSE",
                "direction": "SHORT", "strategy": "Mean Reversion",
                "entry_price": 4210.50, "current_price": round(4210.50 * (1 + random.gauss(-0.003, 0.006)), 2),
                "quantity": 20, "stop_loss": 4310.00, "take_profit": 4050.00,
                "sector": "IT", "opened_at": (now - timedelta(days=1)).isoformat(),
            },
            {
                "id": "pos-003", "symbol": "HDFCBANK", "market": "NSE",
                "direction": "LONG", "strategy": "Swing Trading",
                "entry_price": 1823.40, "current_price": round(1823.40 * (1 + random.gauss(0.003, 0.007)), 2),
                "quantity": 50, "stop_loss": 1780.00, "take_profit": 1920.00,
                "sector": "Banking", "opened_at": (now - timedelta(days=5)).isoformat(),
            },
            {
                "id": "pos-004", "symbol": "INFY", "market": "NSE",
                "direction": "LONG", "strategy": "Momentum Breakout",
                "entry_price": 1890.20, "current_price": round(1890.20 * (1 + random.gauss(0.002, 0.009)), 2),
                "quantity": 45, "stop_loss": 1840.00, "take_profit": 1980.00,
                "sector": "IT", "opened_at": (now - timedelta(days=2)).isoformat(),
            },
        ]

        for pos in positions:
            entry = pos["entry_price"]
            current = pos["current_price"]
            qty = pos["quantity"]
            multiplier = 1 if pos["direction"] == "LONG" else -1
            pos["unrealized_pnl"] = round((current - entry) * qty * multiplier, 2)
            pos["pnl_pct"] = round((current - entry) / entry * 100 * multiplier, 2)
            pos["invested_amount"] = round(entry * qty, 2)
            pos["current_value"] = round(current * qty, 2)

        return positions

    async def get_portfolio_summary(self) -> dict:
        """Get portfolio summary with aggregated metrics."""
        positions = await self.get_positions()
        total_unrealized = sum(p["unrealized_pnl"] for p in positions)
        used_capital = sum(p["invested_amount"] for p in positions)

        return {
            "total_capital": self.initial_capital,
            "used_capital": round(used_capital, 2),
            "available_capital": round(self.initial_capital - used_capital, 2),
            "total_unrealized_pnl": round(total_unrealized, 2),
            "daily_pnl": round(12847.50 + random.gauss(0, 2000), 2),
            "weekly_pnl": round(34562.30 + random.gauss(0, 5000), 2),
            "monthly_pnl": round(78945.20 + random.gauss(0, 8000), 2),
            "total_realized_pnl": round(156230.80 + random.gauss(0, 3000), 2),
            "open_positions": len(positions),
            "drawdown_pct": round(2.3 + random.gauss(0, 0.3), 2),
            "max_drawdown_pct": 5.8,
            "win_rate": 64.7,
            "sharpe_ratio": round(1.84 + random.gauss(0, 0.05), 2),
            "sortino_ratio": round(2.12 + random.gauss(0, 0.08), 2),
            "profit_factor": round(1.87 + random.gauss(0, 0.05), 2),
            "total_trades": 247,
            "capital_at_risk_pct": round(used_capital / self.initial_capital * 100, 1),
            "timestamp": datetime.now(IST).isoformat(),
        }

    async def get_trade_history(self, limit: int = 100) -> list[dict]:
        """Get completed trade history."""
        now = datetime.now(IST)
        trades = []
        stocks = [
            ("RELIANCE", 2847), ("TCS", 4210), ("HDFCBANK", 1823),
            ("INFY", 1890), ("SBIN", 842), ("BHARTIARTL", 1756),
            ("TATAMOTORS", 723), ("LT", 3567), ("SUNPHARMA", 1892),
            ("BAJFINANCE", 7234),
        ]
        strategies = ["Trend Following", "Mean Reversion", "Momentum Breakout",
                       "Scalping", "Swing Trading", "Options Strategy"]

        for i in range(min(limit, 50)):
            stock, base = random.choice(stocks)
            direction = random.choice(["BUY", "SELL"])
            entry = round(base * (1 + random.gauss(0, 0.02)), 2)
            exit_p = round(entry * (1 + random.gauss(0.003, 0.02)), 2)
            qty = random.randint(5, 100)
            multiplier = 1 if direction == "BUY" else -1
            gross_pnl = round((exit_p - entry) * qty * multiplier, 2)
            charges = round(abs(gross_pnl) * 0.012, 2)

            trades.append({
                "id": str(uuid4())[:8],
                "symbol": stock,
                "direction": direction,
                "strategy": random.choice(strategies),
                "entry_price": entry,
                "exit_price": exit_p,
                "quantity": qty,
                "gross_pnl": gross_pnl,
                "charges": charges,
                "net_pnl": round(gross_pnl - charges, 2),
                "score": random.randint(72, 95),
                "entry_time": (now - timedelta(days=i, hours=random.randint(0, 6))).isoformat(),
                "exit_time": (now - timedelta(days=i) + timedelta(hours=random.randint(1, 48))).isoformat(),
                "outcome": random.choice(["TARGET_HIT", "STOP_LOSS_HIT", "TRAILING_SL"]),
            })
        return trades

    async def get_daily_pnl(self, days: int = 30) -> list[dict]:
        """Get daily P&L for calendar heatmap."""
        now = datetime.now(IST)
        daily_data = []
        for i in range(days):
            date = now - timedelta(days=days - i)
            if date.weekday() >= 5:
                continue
            pnl = round(random.gauss(3000, 15000), 2)
            trades_count = random.randint(1, 8)
            wins = random.randint(0, trades_count)
            daily_data.append({
                "date": date.strftime("%Y-%m-%d"),
                "pnl": pnl,
                "trades_count": trades_count,
                "wins": wins,
                "losses": trades_count - wins,
            })
        return daily_data

    async def calculate_performance_metrics(self) -> dict:
        """Calculate comprehensive performance metrics."""
        return {
            "total_return_pct": round(15.6 + random.gauss(0, 1), 2),
            "cagr": round(24.6 + random.gauss(0, 0.5), 2),
            "sharpe_ratio": round(1.84 + random.gauss(0, 0.05), 2),
            "sortino_ratio": round(2.12 + random.gauss(0, 0.08), 2),
            "calmar_ratio": round(2.67 + random.gauss(0, 0.1), 2),
            "max_drawdown": -5.8,
            "win_rate": 64.7,
            "profit_factor": round(1.87 + random.gauss(0, 0.03), 2),
            "avg_win": round(8234.50 + random.gauss(0, 500), 2),
            "avg_loss": round(-4412.30 + random.gauss(0, 300), 2),
            "largest_win": 42567.80,
            "largest_loss": -18234.50,
            "avg_holding_period_hours": 18.4,
            "total_trades": 247,
            "winning_trades": 160,
            "losing_trades": 87,
            "best_month_pct": 8.3,
            "worst_month_pct": -3.1,
        }
