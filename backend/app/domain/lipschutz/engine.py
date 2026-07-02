"""
Lipschutz Mode — disciplined, rules-based trading signal engine.

Philosophy (after Bill Lipschutz): the edge is not prediction, it is
risk management. Every signal here is fully deterministic and
auditable — each one carries the exact conditions that triggered it.
No ML black box, no guarantees, no overpromising.

Rules (documented, fixed):
  Trend filter   : EMA(20) vs EMA(50) on 1H candles.
                   Long setups only when EMA20 > EMA50 AND close > EMA20.
                   Short setups mirror this.
  Entry trigger  : RSI(14) pullback re-entry.
                   Long : RSI dipped below 40 within the last 5 bars and
                          has now closed back above 40 (buying the dip
                          inside an uptrend).
                   Short: RSI rose above 60 within the last 5 bars and
                          has now closed back below 60.
  Stop placement : SL = entry ∓ 1.5 × ATR(14)  (volatility-based).
  Target         : TP = entry ± 2.25 × ATR(14) → fixed 1.5R reward.

Risk layer (the core, not an afterthought):
  * Position size = equity × risk% / stop distance (never exceeds cap).
  * Every signal MUST include stop-loss, take-profit and R:R.
  * Circuit breaker pauses new signals when daily/weekly loss limits hit.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Optional

import pandas as pd

from app.domain.indicators.technical import ema, rsi, atr
from app.domain.backtesting.backtester import _fetch_ohlcv, _normalise_pair, _pip_size

logger = logging.getLogger(__name__)

IST = timezone(timedelta(hours=5, minutes=30))

# ── Engine parameters (deterministic, documented) ────────────────────
EMA_FAST = 20
EMA_SLOW = 50
RSI_PERIOD = 14
RSI_LONG_LEVEL = 40.0
RSI_SHORT_LEVEL = 60.0
RSI_LOOKBACK = 5          # bars to look back for the pullback
ATR_PERIOD = 14
SL_ATR_MULT = 1.5
TP_ATR_MULT = 2.25        # 1.5R fixed reward multiple

DEFAULT_PAIRS = ["EUR/USD", "GBP/USD", "USD/JPY", "AUD/USD", "USD/CAD"]


# ══════════════════════════════════════════════════════════════════════
#  Risk Governor — circuit breaker + position sizing
# ══════════════════════════════════════════════════════════════════════

@dataclass
class RiskGovernor:
    """Account-level risk rules. All percentages are of current equity."""

    equity: float = 10_000.0
    risk_per_trade_pct: float = 1.0     # max risk per position
    max_daily_loss_pct: float = 3.0     # circuit breaker (day)
    max_weekly_loss_pct: float = 6.0    # circuit breaker (week)

    daily_pnl_pct: float = 0.0
    weekly_pnl_pct: float = 0.0

    def circuit_breaker_active(self) -> tuple[bool, Optional[str]]:
        if self.daily_pnl_pct <= -self.max_daily_loss_pct:
            return True, (
                f"Daily loss limit hit ({self.daily_pnl_pct:.1f}% ≤ "
                f"-{self.max_daily_loss_pct:.1f}%). New signals paused until tomorrow."
            )
        if self.weekly_pnl_pct <= -self.max_weekly_loss_pct:
            return True, (
                f"Weekly loss limit hit ({self.weekly_pnl_pct:.1f}% ≤ "
                f"-{self.max_weekly_loss_pct:.1f}%). New signals paused until next week."
            )
        return False, None

    def position_size(self, entry: float, stop: float, pair: str) -> dict:
        """Units such that (entry-stop) loss == risk_per_trade_pct of equity."""
        stop_dist = abs(entry - stop)
        if stop_dist <= 0:
            return {"units": 0, "risk_amount": 0.0, "risk_pct": 0.0}
        risk_amount = self.equity * (self.risk_per_trade_pct / 100.0)
        units = risk_amount / stop_dist
        pip = _pip_size(pair)
        return {
            "units": round(units, 2),
            "risk_amount": round(risk_amount, 2),
            "risk_pct": self.risk_per_trade_pct,
            "stop_distance_pips": round(stop_dist / pip, 1),
        }


# ══════════════════════════════════════════════════════════════════════
#  Signal generation — deterministic rules, explicit reasons
# ══════════════════════════════════════════════════════════════════════

def _evaluate_frame(df: pd.DataFrame, pair: str) -> Optional[dict]:
    """
    Evaluate the LAST closed bar of `df` against the rules.
    Returns a signal dict with explicit `reasons`, or None.
    """
    if df is None or len(df) < EMA_SLOW + RSI_LOOKBACK + 2:
        return None

    close = df["close"]
    ema_f = ema(close, EMA_FAST)
    ema_s = ema(close, EMA_SLOW)
    rsi_v = rsi(close, RSI_PERIOD)
    atr_v = atr(df, ATR_PERIOD)

    c = float(close.iloc[-1])
    ef, es = float(ema_f.iloc[-1]), float(ema_s.iloc[-1])
    r_now = float(rsi_v.iloc[-1])
    r_window = rsi_v.iloc[-(RSI_LOOKBACK + 1):-1]  # previous N bars
    a = float(atr_v.iloc[-1])
    if pd.isna(a) or a <= 0 or pd.isna(r_now):
        return None

    uptrend = ef > es and c > ef
    downtrend = ef < es and c < ef

    direction = None
    reasons: list[str] = []

    if uptrend and r_now > RSI_LONG_LEVEL and (r_window < RSI_LONG_LEVEL).any():
        direction = "BUY"
        reasons = [
            f"Uptrend filter: EMA{EMA_FAST} ({ef:.5f}) above EMA{EMA_SLOW} ({es:.5f})",
            f"Price {c:.5f} trading above EMA{EMA_FAST}",
            f"RSI({RSI_PERIOD}) pullback: dipped below {RSI_LONG_LEVEL:.0f} within last "
            f"{RSI_LOOKBACK} bars (min {float(r_window.min()):.1f}), now recovered to {r_now:.1f}",
            f"Volatility stop: 1.5×ATR({ATR_PERIOD}) = {SL_ATR_MULT * a:.5f}",
        ]
    elif downtrend and r_now < RSI_SHORT_LEVEL and (r_window > RSI_SHORT_LEVEL).any():
        direction = "SELL"
        reasons = [
            f"Downtrend filter: EMA{EMA_FAST} ({ef:.5f}) below EMA{EMA_SLOW} ({es:.5f})",
            f"Price {c:.5f} trading below EMA{EMA_FAST}",
            f"RSI({RSI_PERIOD}) pullback: rose above {RSI_SHORT_LEVEL:.0f} within last "
            f"{RSI_LOOKBACK} bars (max {float(r_window.max()):.1f}), now rejected to {r_now:.1f}",
            f"Volatility stop: 1.5×ATR({ATR_PERIOD}) = {SL_ATR_MULT * a:.5f}",
        ]

    if direction is None:
        return None

    entry = c
    if direction == "BUY":
        sl = entry - SL_ATR_MULT * a
        tp = entry + TP_ATR_MULT * a
    else:
        sl = entry + SL_ATR_MULT * a
        tp = entry - TP_ATR_MULT * a

    rr = round(abs(tp - entry) / abs(entry - sl), 2)

    return {
        "pair": pair,
        "direction": direction,
        "entry": round(entry, 5),
        "stop_loss": round(sl, 5),
        "take_profit": round(tp, 5),
        "risk_reward": rr,
        "atr": round(a, 5),
        "rsi": round(r_now, 1),
        "reasons": reasons,
        "strategy": "EMA trend + RSI pullback + ATR stops",
        "timeframe": "1H",
        "generated_at": datetime.now(IST).isoformat(),
    }


def generate_signals(
    pairs: Optional[list[str]] = None,
    governor: Optional[RiskGovernor] = None,
) -> dict:
    """
    Scan `pairs` on live 1H data and return rule-triggered signals.
    Applies the risk governor: sizing per signal, circuit breaker gate.
    """
    governor = governor or RiskGovernor()
    pairs = [_normalise_pair(p) for p in (pairs or DEFAULT_PAIRS)]

    breaker, reason = governor.circuit_breaker_active()
    if breaker:
        return {
            "signals": [],
            "circuit_breaker": True,
            "circuit_breaker_reason": reason,
            "scanned_pairs": pairs,
            "generated_at": datetime.now(IST).isoformat(),
        }

    signals = []
    for pair in pairs:
        try:
            df = _fetch_ohlcv(pair, days=30)
            sig = _evaluate_frame(df, pair)
            if sig:
                sig["position"] = governor.position_size(
                    sig["entry"], sig["stop_loss"], pair
                )
                signals.append(sig)
        except Exception as exc:
            logger.warning("Lipschutz scan failed for %s: %s", pair, exc)

    return {
        "signals": signals,
        "circuit_breaker": False,
        "circuit_breaker_reason": None,
        "scanned_pairs": pairs,
        "rules": {
            "trend_filter": f"EMA({EMA_FAST}) vs EMA({EMA_SLOW}), price on trend side",
            "entry_trigger": f"RSI({RSI_PERIOD}) pullback re-entry through "
                             f"{RSI_LONG_LEVEL:.0f}/{RSI_SHORT_LEVEL:.0f}",
            "stop_loss": f"{SL_ATR_MULT}×ATR({ATR_PERIOD})",
            "take_profit": f"{TP_ATR_MULT}×ATR({ATR_PERIOD}) (fixed 1.5R)",
        },
        "generated_at": datetime.now(IST).isoformat(),
    }


# ══════════════════════════════════════════════════════════════════════
#  Backtest — same rules replayed bar-by-bar, honest stats
# ══════════════════════════════════════════════════════════════════════

def backtest(pair: str, days: int = 180, governor: Optional[RiskGovernor] = None) -> dict:
    """
    Replay the exact live rules over history. One position at a time,
    exits only at SL or TP (no discretionary exits), risk-managed sizing.
    Returns win rate, average R multiple, profit factor, max drawdown.
    """
    governor = governor or RiskGovernor()
    pair = _normalise_pair(pair)
    df = _fetch_ohlcv(pair, days=days)
    if df is None or len(df) < EMA_SLOW * 2:
        return {"error": f"Not enough historical data for {pair}"}

    close = df["close"]
    ema_f = ema(close, EMA_FAST)
    ema_s = ema(close, EMA_SLOW)
    rsi_v = rsi(close, RSI_PERIOD)
    atr_v = atr(df, ATR_PERIOD)

    equity = governor.equity
    start_equity = equity
    peak = equity
    max_dd = 0.0

    trades: list[dict] = []
    open_pos: Optional[dict] = None
    equity_curve: list[float] = []

    for i in range(EMA_SLOW + RSI_LOOKBACK + 1, len(df)):
        hi = float(df["high"].iloc[i])
        lo = float(df["low"].iloc[i])

        # ── Manage open position ──
        if open_pos:
            exit_price = None
            if open_pos["direction"] == "BUY":
                if lo <= open_pos["sl"]:
                    exit_price, result = open_pos["sl"], "loss"
                elif hi >= open_pos["tp"]:
                    exit_price, result = open_pos["tp"], "win"
            else:
                if hi >= open_pos["sl"]:
                    exit_price, result = open_pos["sl"], "loss"
                elif lo <= open_pos["tp"]:
                    exit_price, result = open_pos["tp"], "win"

            if exit_price is not None:
                risk_amt = equity * governor.risk_per_trade_pct / 100.0
                r_mult = 1.5 if result == "win" else -1.0
                pnl = risk_amt * r_mult
                equity += pnl
                trades.append({
                    "direction": open_pos["direction"],
                    "entry": open_pos["entry"],
                    "exit": round(exit_price, 5),
                    "result": result,
                    "r_multiple": r_mult,
                    "pnl": round(pnl, 2),
                })
                open_pos = None
                peak = max(peak, equity)
                dd = (peak - equity) / peak * 100.0
                max_dd = max(max_dd, dd)

        # ── Look for a new entry (one position at a time) ──
        if open_pos is None:
            c = float(close.iloc[i])
            ef, es = float(ema_f.iloc[i]), float(ema_s.iloc[i])
            r_now = float(rsi_v.iloc[i])
            r_window = rsi_v.iloc[i - RSI_LOOKBACK:i]
            a = float(atr_v.iloc[i])
            if pd.isna(a) or a <= 0 or pd.isna(r_now):
                equity_curve.append(equity)
                continue

            if ef > es and c > ef and r_now > RSI_LONG_LEVEL and (r_window < RSI_LONG_LEVEL).any():
                open_pos = {"direction": "BUY", "entry": c,
                            "sl": c - SL_ATR_MULT * a, "tp": c + TP_ATR_MULT * a}
            elif ef < es and c < ef and r_now < RSI_SHORT_LEVEL and (r_window > RSI_SHORT_LEVEL).any():
                open_pos = {"direction": "SELL", "entry": c,
                            "sl": c + SL_ATR_MULT * a, "tp": c - TP_ATR_MULT * a}

        equity_curve.append(equity)

    wins = [t for t in trades if t["result"] == "win"]
    losses = [t for t in trades if t["result"] == "loss"]
    gross_win = sum(t["pnl"] for t in wins)
    gross_loss = abs(sum(t["pnl"] for t in losses))

    n = len(trades)
    # Sample the equity curve down to ≤200 points for the frontend chart.
    step = max(1, len(equity_curve) // 200)
    curve = [round(v, 2) for v in equity_curve[::step]]

    return {
        "pair": pair,
        "days": days,
        "timeframe": "1H",
        "total_trades": n,
        "wins": len(wins),
        "losses": len(losses),
        "win_rate_pct": round(len(wins) / n * 100, 1) if n else 0.0,
        "avg_r_multiple": round(sum(t["r_multiple"] for t in trades) / n, 2) if n else 0.0,
        "profit_factor": round(gross_win / gross_loss, 2) if gross_loss else None,
        "net_pnl": round(equity - start_equity, 2),
        "return_pct": round((equity - start_equity) / start_equity * 100, 2),
        "max_drawdown_pct": round(max_dd, 2),
        "start_equity": start_equity,
        "end_equity": round(equity, 2),
        "equity_curve": curve,
        "trades_sample": trades[-20:],
        "rules": {
            "trend_filter": f"EMA({EMA_FAST}) vs EMA({EMA_SLOW})",
            "entry_trigger": f"RSI({RSI_PERIOD}) pullback re-entry",
            "stop_loss": f"{SL_ATR_MULT}×ATR({ATR_PERIOD})",
            "take_profit": f"{TP_ATR_MULT}×ATR({ATR_PERIOD})",
            "risk_per_trade_pct": governor.risk_per_trade_pct,
        },
        "disclaimer": (
            "Backtested performance does not guarantee future results. "
            "This is a decision-support tool, not financial advice."
        ),
        "generated_at": datetime.now(IST).isoformat(),
    }
