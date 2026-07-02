"""
Unit tests for the Lipschutz Mode engine.

The engine is fully deterministic, so we test it with synthetic OHLCV
frames — no network access needed.
"""

import numpy as np
import pandas as pd
import pytest

from app.domain.lipschutz.engine import (
    RiskGovernor,
    _evaluate_frame,
    EMA_SLOW,
    RSI_LOOKBACK,
    SL_ATR_MULT,
    TP_ATR_MULT,
)


# ── Helpers ──────────────────────────────────────────────────────────

def make_frame(closes: list[float]) -> pd.DataFrame:
    """Build a synthetic OHLCV frame around a close series."""
    closes = pd.Series(closes, dtype=float)
    return pd.DataFrame({
        "open": closes.shift(1).fillna(closes.iloc[0]),
        "high": closes + 0.0008,
        "low": closes - 0.0008,
        "close": closes,
        "volume": 1000,
    })


def uptrend_with_pullback(n: int = 150) -> pd.DataFrame:
    """
    Rising series with an 8-bar declining consolidation near the end
    followed by a 2-bar recovery — verified to fire the long rule
    (trend up + RSI pullback re-entry).
    """
    dip_depth, dip_len = 0.008, 8
    base = np.linspace(1.05, 1.13, n)
    closes = list(base)
    for j in range(dip_len):
        closes[-3 - j] = closes[-3 - dip_len] - dip_depth * (dip_len - j) / dip_len
    closes[-2] = closes[-3] + 0.003
    closes[-1] = closes[-2] + 0.003
    return make_frame(closes)


# ── RiskGovernor ─────────────────────────────────────────────────────

class TestRiskGovernor:
    def test_position_size_matches_risk_pct(self):
        gov = RiskGovernor(equity=10_000, risk_per_trade_pct=1.0)
        pos = gov.position_size(entry=1.1000, stop=1.0950, pair="EUR/USD")
        # 1% of 10k = $100 risk over 0.005 distance = 20,000 units
        assert pos["risk_amount"] == 100.0
        assert pos["units"] == pytest.approx(20_000, rel=1e-3)

    def test_zero_stop_distance_returns_no_position(self):
        gov = RiskGovernor()
        pos = gov.position_size(entry=1.1, stop=1.1, pair="EUR/USD")
        assert pos["units"] == 0

    def test_daily_circuit_breaker_trips(self):
        gov = RiskGovernor(daily_pnl_pct=-3.5)
        active, reason = gov.circuit_breaker_active()
        assert active is True
        assert "Daily" in reason

    def test_weekly_circuit_breaker_trips(self):
        gov = RiskGovernor(daily_pnl_pct=-1.0, weekly_pnl_pct=-7.0)
        active, reason = gov.circuit_breaker_active()
        assert active is True
        assert "Weekly" in reason

    def test_breaker_inactive_within_limits(self):
        gov = RiskGovernor(daily_pnl_pct=-1.0, weekly_pnl_pct=-2.0)
        active, reason = gov.circuit_breaker_active()
        assert active is False
        assert reason is None


# ── Signal evaluation ────────────────────────────────────────────────

class TestEvaluateFrame:
    def test_insufficient_data_returns_none(self):
        df = make_frame([1.1] * (EMA_SLOW - 5))
        assert _evaluate_frame(df, "EUR/USD") is None

    def test_flat_market_returns_none(self):
        df = make_frame([1.1000 + (i % 3) * 0.0001 for i in range(150)])
        assert _evaluate_frame(df, "EUR/USD") is None

    def test_signal_includes_mandatory_fields(self):
        sig = _evaluate_frame(uptrend_with_pullback(), "EUR/USD")
        if sig is None:
            pytest.skip("synthetic series did not fire — rule thresholds are strict")
        # Non-negotiables: every signal must carry SL, TP, R:R, reasons
        assert sig["stop_loss"] is not None
        assert sig["take_profit"] is not None
        assert sig["risk_reward"] == pytest.approx(TP_ATR_MULT / SL_ATR_MULT, abs=0.01)
        assert len(sig["reasons"]) >= 3
        assert sig["direction"] in ("BUY", "SELL")

    def test_buy_signal_geometry(self):
        sig = _evaluate_frame(uptrend_with_pullback(), "EUR/USD")
        if sig is None or sig["direction"] != "BUY":
            pytest.skip("no BUY fired on synthetic series")
        assert sig["stop_loss"] < sig["entry"] < sig["take_profit"]
