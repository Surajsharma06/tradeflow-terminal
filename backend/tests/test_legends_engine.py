"""
Unit tests for the Legends Mode engine — synthetic frames, no network.
"""

import numpy as np
import pandas as pd
import pytest

from app.domain.legends.engine import (
    detect_regime,
    turtle_breakout,
    seykota_pullback,
    ptj_failed_break,
    raschke_meanrev,
    _merge_pair_signals,
    _corr,
    PTJ_SMA,
)
from app.domain.lipschutz.engine import RiskGovernor


def make_frame(closes, highs=None, lows=None):
    closes = pd.Series(closes, dtype=float)
    return pd.DataFrame({
        "open": closes.shift(1).fillna(closes.iloc[0]),
        "high": pd.Series(highs, dtype=float) if highs is not None else closes + 0.0008,
        "low": pd.Series(lows, dtype=float) if lows is not None else closes - 0.0008,
        "close": closes,
        "volume": 1000,
    })


def strong_uptrend(n=320):
    base = np.linspace(1.05, 1.25, n)
    wob = np.sin(np.arange(n) * 0.7) * 0.0012
    return make_frame(list(base + wob))


def flat_range(n=320, center=1.10, amp=0.004):
    xs = center + amp * np.sin(np.arange(n) * 0.35)
    return make_frame(list(xs))


# ── Regime detection ─────────────────────────────────────────────────

class TestRegime:
    def test_uptrend_detected(self):
        reg = detect_regime(strong_uptrend())
        assert reg["regime"] == "TRENDING_UP"

    def test_downtrend_detected(self):
        df = strong_uptrend()
        flipped = make_frame(list(df["close"].iloc[::-1].values))
        reg = detect_regime(flipped)
        assert reg["regime"] == "TRENDING_DOWN"

    def test_range_detected(self):
        reg = detect_regime(flat_range())
        assert reg["regime"] in ("RANGING", "CHOPPY")

    def test_insufficient_history_is_choppy(self):
        reg = detect_regime(make_frame([1.1] * 50))
        assert reg["regime"] == "CHOPPY"


# ── Strategies fire only in their regime ─────────────────────────────

class TestStrategyGating:
    def test_turtle_requires_trend(self):
        df = flat_range()
        assert turtle_breakout(df, len(df) - 1, "RANGING") is None

    def test_raschke_requires_range(self):
        df = strong_uptrend()
        assert raschke_meanrev(df, len(df) - 1, "TRENDING_UP") is None

    def test_ptj_requires_range(self):
        df = strong_uptrend()
        assert ptj_failed_break(df, len(df) - 1, "TRENDING_UP") is None

    def test_turtle_fires_on_breakout(self):
        df = strong_uptrend()
        closes = list(df["close"])
        closes[-1] = closes[-2] + 0.02  # decisive new 20-bar high
        df2 = make_frame(closes)
        sig = turtle_breakout(df2, len(df2) - 1, "TRENDING_UP")
        assert sig is not None and sig["direction"] == "BUY"
        assert sig["stop_loss"] < sig["entry"] < sig["take_profit"]
        assert "Donchian" in sig["rule"]

    def test_raschke_fires_at_lower_band(self):
        # Steep 6-bar selloff at the end of a flat range → RSI oversold
        # and close pierces the lower Bollinger band.
        df = flat_range()
        closes = list(df["close"])
        for j in range(6, 0, -1):
            closes[-j] = closes[-7] - (7 - j) * 0.004
        df2 = make_frame(closes)
        sig = raschke_meanrev(df2, len(df2) - 1, "RANGING")
        assert sig is not None and sig["direction"] == "BUY"
        assert sig["take_profit"] > sig["entry"] > sig["stop_loss"]

    def test_ptj_failed_breakdown_fires(self):
        df = flat_range()
        closes = list(df["close"])
        lows = list(df["low"])
        lo20 = min(lows[-21:-1])
        lows[-1] = lo20 - 0.003     # wick below the 20-bar low
        closes[-1] = lo20 + 0.002   # close back inside
        df2 = make_frame(closes, lows=lows)
        sig = ptj_failed_break(df2, len(df2) - 1, "RANGING")
        assert sig is not None and sig["direction"] == "BUY"
        rr = (sig["take_profit"] - sig["entry"]) / (sig["entry"] - sig["stop_loss"])
        assert rr >= 2.4  # PTJ asymmetric bet


# ── Ensemble mechanics ───────────────────────────────────────────────

class TestEnsemble:
    def _sig(self, direction="BUY", trader="Ed Seykota"):
        return {"direction": direction, "entry": 1.10, "stop_loss": 1.095,
                "take_profit": 1.11, "trader": trader, "rule": "r",
                "reasons": ["x"]}

    def test_conflicting_directions_no_trade(self):
        out = _merge_pair_signals(
            "EUR/USD",
            [self._sig("BUY"), self._sig("SELL", "Linda Raschke")],
            {"regime": "RANGING", "detail": ""}, RiskGovernor(),
        )
        assert out is None

    def test_confluence_bumps_conviction(self):
        gov = RiskGovernor(risk_per_trade_pct=1.0)
        solo = _merge_pair_signals("EUR/USD", [self._sig()],
                                   {"regime": "TRENDING_UP", "detail": ""}, gov)
        duo = _merge_pair_signals(
            "EUR/USD",
            [self._sig(), self._sig(trader="Richard Dennis (Turtle)")],
            {"regime": "TRENDING_UP", "detail": ""}, gov,
        )
        assert solo["conviction"] == "NORMAL" and solo["risk_pct_used"] == 0.75
        assert duo["conviction"] == "HIGH" and duo["risk_pct_used"] == 1.0
        assert duo["confluence"] == 2

    def test_correlation_lookup_symmetric(self):
        assert _corr("EUR/USD", "GBP/USD") == _corr("GBP/USD", "EUR/USD") == 0.85
        assert _corr("EUR/USD", "USD/ZAR") == 0.0
