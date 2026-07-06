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


# ── Quality scoring & best-trade selection ───────────────────────────

from app.domain.legends.engine import _quality_score, _grade, BEST_TRADE_MIN_SCORE


class TestQualityScore:
    def _sig(self, confluence=1, rr=1.5, trader="Ed Seykota"):
        return {"pair": "EUR/USD", "confluence": confluence,
                "risk_reward": rr, "trader": trader}

    def _edge(self, pf=1.4, by_trader=None):
        return {"trailing_profit_factor": pf, "by_trader": by_trader or {}}

    def _regime(self, regime="TRENDING_UP", adx=32.0):
        return {"regime": regime, "adx": adx}

    def test_score_bounded_0_100(self):
        score, factors = _quality_score(
            self._sig(confluence=3, rr=3.0),
            self._edge(pf=2.5, by_trader={"Ed Seykota": {"net_r": 5.0, "trades": 6}}),
            self._regime(adx=45),
        )
        assert 0 <= score <= 100
        assert score >= 90  # everything maxed
        assert len(factors) == 5
        assert all(0 <= f["points"] <= f["max"] for f in factors)

    def test_confluence_raises_score(self):
        lo, _ = _quality_score(self._sig(confluence=1), self._edge(), self._regime())
        hi, _ = _quality_score(self._sig(confluence=2), self._edge(), self._regime())
        assert hi > lo

    def test_losing_local_record_scores_zero_factor(self):
        edge = self._edge(by_trader={"Ed Seykota": {"net_r": -2.0, "trades": 5}})
        _, factors = _quality_score(self._sig(), edge, self._regime())
        rec = next(f for f in factors if f["factor"] == "Legend's record here")
        assert rec["points"] == 0

    def test_weak_pf_scores_zero_edge_factor(self):
        _, factors = _quality_score(self._sig(), self._edge(pf=0.8), self._regime())
        e = next(f for f in factors if "PF" in f["factor"] or "edge" in f["factor"].lower())
        assert e["points"] == 0

    def test_grades(self):
        assert _grade(85) == "A+ ELITE"
        assert _grade(72) == "A STRONG"
        assert _grade(BEST_TRADE_MIN_SCORE) == "B+ SOLID"
        assert _grade(40) == "B WATCH"
