"""
Signal Generation Service — Orchestrates strategy signals, scoring, and filtering.
"""

import logging
import random
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import uuid4

logger = logging.getLogger(__name__)

IST = timezone(timedelta(hours=5, minutes=30))

STRATEGIES = [
    "Trend Following", "Mean Reversion", "Momentum Breakout",
    "Scalping", "Swing Trading", "Options Strategy"
]

INDIAN_STOCKS = [
    ("RELIANCE", "Energy", 2847.30), ("TCS", "IT", 4210.50),
    ("HDFCBANK", "Banking", 1823.40), ("INFY", "IT", 1890.20),
    ("ICICIBANK", "Banking", 1345.60), ("SBIN", "Banking", 842.75),
    ("BHARTIARTL", "Telecom", 1756.80), ("TATAMOTORS", "Auto", 723.45),
    ("LT", "Infrastructure", 3567.90), ("SUNPHARMA", "Pharma", 1892.30),
    ("BAJFINANCE", "NBFC", 7234.50), ("ADANIENT", "Conglomerate", 3120.80),
    ("HCLTECH", "IT", 1945.60), ("WIPRO", "IT", 567.30),
    ("KOTAKBANK", "Banking", 2134.70),
]


class SignalService:
    """Service for generating, scoring, and managing trading signals."""

    def __init__(self):
        self._signal_history = []

    async def generate_signals(self, symbols: Optional[list] = None) -> list[dict]:
        """Generate scored signals from all active strategies."""
        now = datetime.now(IST)
        signals = []
        stocks = INDIAN_STOCKS if not symbols else [
            s for s in INDIAN_STOCKS if s[0] in symbols
        ]

        for stock_name, sector, base_price in stocks:
            if random.random() > 0.35:
                continue

            strategy = random.choice(STRATEGIES)
            direction = random.choice(["BUY", "SELL"])
            price = round(base_price * (1 + random.gauss(0, 0.01)), 2)

            atr = round(price * random.uniform(0.01, 0.03), 2)
            sl_distance = round(atr * 2, 2)
            stop_loss = round(price - sl_distance if direction == "BUY" else price + sl_distance, 2)
            target1 = round(price + sl_distance * 2 if direction == "BUY" else price - sl_distance * 2, 2)
            target2 = round(price + sl_distance * 3 if direction == "BUY" else price - sl_distance * 3, 2)
            target3 = round(price + sl_distance * 4.5 if direction == "BUY" else price - sl_distance * 4.5, 2)
            rr_ratio = round(abs(target1 - price) / abs(price - stop_loss), 2) if abs(price - stop_loss) > 0 else 0

            # Score breakdown
            technical = random.randint(22, 38)
            sentiment = random.randint(8, 18)
            volume = random.randint(6, 14)
            regime = random.randint(5, 14)
            macro = random.randint(3, 9)
            total_score = min(technical + sentiment + volume + regime + macro, 100)

            signal = {
                "id": str(uuid4())[:8],
                "symbol": stock_name,
                "market": "NSE",
                "sector": sector,
                "direction": direction,
                "strategy": strategy,
                "entry_price": price,
                "stop_loss": stop_loss,
                "targets": [target1, target2, target3],
                "rr_ratio": rr_ratio,
                "score": total_score,
                "score_breakdown": {
                    "technical": technical,
                    "sentiment": sentiment,
                    "volume": volume,
                    "regime": regime,
                    "macro": macro,
                },
                "confidence": "HIGH" if total_score >= 85 else "MEDIUM" if total_score >= 72 else "LOW",
                "status": "ACTIVE",
                "created_at": now.isoformat(),
                "indicators": {
                    "rsi": round(random.uniform(25, 75), 1),
                    "macd_signal": random.choice(["BULLISH", "BEARISH"]),
                    "ema_trend": random.choice(["UP", "DOWN", "FLAT"]),
                    "volume_ratio": round(random.uniform(0.8, 3.5), 2),
                    "adx": round(random.uniform(15, 45), 1),
                    "atr": atr,
                },
            }
            signals.append(signal)

        # Sort by score descending
        signals.sort(key=lambda s: s["score"], reverse=True)
        logger.info(f"Generated {len(signals)} signals, {sum(1 for s in signals if s['score'] >= 72)} actionable")
        return signals

    async def get_active_signals(self, min_score: int = 72) -> list[dict]:
        """Get current active signals above threshold."""
        all_signals = await self.generate_signals()
        return [s for s in all_signals if s["score"] >= min_score]

    async def get_signal_history(self, limit: int = 100) -> list[dict]:
        """Get historical signals with outcomes."""
        now = datetime.now(IST)
        history = []
        outcomes = ["TARGET_HIT", "STOP_LOSS_HIT", "TRAILING_SL", "EXPIRED", "MANUAL_EXIT"]
        
        for i in range(min(limit, 50)):
            stock = random.choice(INDIAN_STOCKS)
            direction = random.choice(["BUY", "SELL"])
            outcome = random.choice(outcomes)
            entry = round(stock[2] * (1 + random.gauss(0, 0.02)), 2)
            sl_dist = round(entry * 0.02, 2)
            
            if outcome == "TARGET_HIT":
                exit_price = round(entry + sl_dist * random.uniform(2, 4) * (1 if direction == "BUY" else -1), 2)
            elif outcome == "STOP_LOSS_HIT":
                exit_price = round(entry - sl_dist * (1 if direction == "BUY" else -1), 2)
            else:
                exit_price = round(entry * (1 + random.gauss(0, 0.01)), 2)

            pnl = round((exit_price - entry) * random.randint(10, 100) * (1 if direction == "BUY" else -1), 2)

            history.append({
                "id": str(uuid4())[:8],
                "symbol": stock[0],
                "direction": direction,
                "strategy": random.choice(STRATEGIES),
                "entry_price": entry,
                "exit_price": exit_price,
                "score": random.randint(65, 95),
                "outcome": outcome,
                "pnl": pnl,
                "duration_hours": random.randint(1, 240),
                "created_at": (now - timedelta(days=i)).isoformat(),
                "closed_at": (now - timedelta(days=i) + timedelta(hours=random.randint(1, 72))).isoformat(),
            })
        return history

    async def get_signal_by_id(self, signal_id: str) -> Optional[dict]:
        """Get a specific signal by ID."""
        signals = await self.get_active_signals(min_score=0)
        for s in signals:
            if s["id"] == signal_id:
                return s
        return None
