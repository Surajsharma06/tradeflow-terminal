"""
Legends Mode — multi-strategy ensemble built from the documented rules
of history's great forex/futures traders, gated by market-regime
detection and governed by a risk layer that outranks every signal.

Why this exists: single-strategy systems die when the market regime
changes. A trend system prints money in trends and bleeds in ranges.
The legends survived decades because they either switched tactics with
the regime or stood aside. This engine encodes that.

The roster and the rule each contributes:

  Richard Dennis / Turtles  — Donchian-20 breakouts, 2N volatility
                              stops, only trade with the trend.
  Ed Seykota                — ride winners: move stop to breakeven at
                              +1R, then trail 2×ATR; cut losses fast.
  Paul Tudor Jones          — the 200-SMA is the line between offense
                              and defense: no longs below it, no shorts
                              above it; demand asymmetric R:R (≥2.5:1
                              on breakouts); never average a loser.
  Linda Raschke             — in ranges, fade extremes: RSI + Bollinger
                              touch, target the middle band.
  Jesse Livermore           — "Money is made by sitting": in choppy,
                              dead markets the position is NO position.
  Ray Dalio                 — never stack correlated bets; correlated
                              positions are one big bet in disguise.
  Stanley Druckenmiller     — size up only with conviction (here:
                              multi-strategy confluence), never beyond
                              the risk cap.
  Bill Lipschutz            — the risk governor itself: fixed-fraction
                              sizing, mandatory stops, loss-limit
                              circuit breakers (see lipschutz.engine).

Every signal carries `trader`, `rule` and `reasons` — full attribution,
no black box. None of this guarantees profit; it manages losing well,
which is the only edge that compounds.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

import numpy as np
import pandas as pd

from app.domain.indicators.technical import ema, sma, rsi, atr, adx, bollinger_bands
from app.domain.backtesting.backtester import _fetch_ohlcv, _normalise_pair, _pip_size
from app.domain.lipschutz.engine import RiskGovernor

logger = logging.getLogger(__name__)

IST = timezone(timedelta(hours=5, minutes=30))

DEFAULT_PAIRS = ["EUR/USD", "GBP/USD", "USD/JPY", "AUD/USD", "USD/CAD", "NZD/USD"]

# ── Regime thresholds ────────────────────────────────────────────────
ADX_TREND = 25.0          # ADX above → trending
ADX_RANGE = 18.0          # ADX below → ranging
ATR_DEAD_PCTL = 20.0      # ATR percentile below → dead/choppy market

# ── Strategy parameters (documented, deterministic) ──────────────────
DONCHIAN_N = 20           # Turtle System-1 entry channel
TURTLE_STOP_N = 2.0       # 2N stop (N = ATR20)
TURTLE_TARGET_N = 4.0     # 2:1 initial target before trailing
PULLBACK_EMA_FAST = 20
PULLBACK_EMA_SLOW = 50
PTJ_SMA = 200             # Tudor Jones' line in the sand
PTJ_MIN_RR = 2.5
RASCHKE_RSI_LO = 30.0
RASCHKE_RSI_HI = 70.0
TRAIL_BE_AT_R = 1.0       # Seykota: breakeven at +1R
TRAIL_ATR_MULT = 2.0      # then trail 2×ATR behind best price

# Dalio correlation guard — approximate long-run correlations between
# majors. Two same-direction signals in pairs with |r| > 0.75 are one
# bet in disguise; keep only the higher-conviction one.
PAIR_CORRELATION = {
    ("EUR/USD", "GBP/USD"): 0.85,
    ("AUD/USD", "NZD/USD"): 0.87,
    ("EUR/USD", "USD/CHF"): -0.90,
    ("AUD/USD", "USD/CAD"): -0.65,
    ("EUR/USD", "USD/JPY"): -0.30,
    ("GBP/USD", "USD/JPY"): -0.25,
}


def _corr(a: str, b: str) -> float:
    return PAIR_CORRELATION.get((a, b)) or PAIR_CORRELATION.get((b, a)) or 0.0


# ══════════════════════════════════════════════════════════════════════
#  Precomputed indicator context — computed once per frame so the
#  backtest is O(n) instead of recomputing every series at every bar.
# ══════════════════════════════════════════════════════════════════════

def _precompute(df: pd.DataFrame) -> dict:
    adx_v, _, _ = adx(df, 14)
    upper, middle, lower, _, _ = bollinger_bands(df["close"], 20, 2.0)
    return {
        "adx14": adx_v,
        "atr14": atr(df, 14),
        "atr20": atr(df, 20),
        "ema20": ema(df["close"], PULLBACK_EMA_FAST),
        "ema50": ema(df["close"], PULLBACK_EMA_SLOW),
        "ema200": ema(df["close"], 200),
        "sma200": sma(df["close"], PTJ_SMA),
        "rsi14": rsi(df["close"], 14),
        "bb_u": upper, "bb_m": middle, "bb_l": lower,
        # Prior 20-bar channel (excludes current bar, matches iloc[i-20:i])
        "hi20": df["high"].rolling(DONCHIAN_N).max().shift(1),
        "lo20": df["low"].rolling(DONCHIAN_N).min().shift(1),
    }


# ══════════════════════════════════════════════════════════════════════
#  Regime detection
# ══════════════════════════════════════════════════════════════════════

def detect_regime(df: pd.DataFrame, i: Optional[int] = None,
                  ctx: Optional[dict] = None) -> dict:
    """
    Classify the market at bar `i` (default: last bar).

    TRENDING_UP / TRENDING_DOWN : ADX ≥ 25 with EMA50/200 alignment
    RANGING                     : ADX ≤ 18 with normal volatility
    CHOPPY                      : dead volatility or conflicting reads
    """
    i = len(df) - 1 if i is None else i
    if i < PTJ_SMA:
        return {"regime": "CHOPPY", "adx": None,
                "detail": "Not enough history for a regime read"}

    ctx = ctx or _precompute(df)
    adx_v = ctx["adx14"]
    atr_v = ctx["atr14"]
    e50 = ctx["ema50"]
    e200 = ctx["ema200"]

    a = float(adx_v.iloc[i]) if not pd.isna(adx_v.iloc[i]) else 0.0
    c = float(df["close"].iloc[i])
    up_aligned = c > float(e50.iloc[i]) > float(e200.iloc[i])
    dn_aligned = c < float(e50.iloc[i]) < float(e200.iloc[i])

    # ATR percentile over trailing 100 bars — dead-market detector
    window = atr_v.iloc[max(0, i - 100):i + 1].dropna()
    atr_pctl = float((window <= window.iloc[-1]).mean() * 100) if len(window) > 10 else 50.0

    if atr_pctl < ATR_DEAD_PCTL and a < ADX_RANGE:
        regime = "CHOPPY"
        detail = (f"Dead market: ATR in {atr_pctl:.0f}th percentile, ADX {a:.1f} — "
                  f"Livermore rule: sit out")
    elif a >= ADX_TREND and up_aligned:
        regime, detail = "TRENDING_UP", f"ADX {a:.1f} with price > EMA50 > EMA200"
    elif a >= ADX_TREND and dn_aligned:
        regime, detail = "TRENDING_DOWN", f"ADX {a:.1f} with price < EMA50 < EMA200"
    elif a <= ADX_RANGE:
        regime, detail = "RANGING", f"ADX {a:.1f} ≤ {ADX_RANGE:.0f} — no directional conviction"
    else:
        regime = "CHOPPY"
        detail = f"Transitional: ADX {a:.1f} without clean EMA alignment"

    return {"regime": regime, "adx": round(a, 1), "atr_percentile": round(atr_pctl, 0),
            "detail": detail}


# ══════════════════════════════════════════════════════════════════════
#  Individual legend strategies
#  Each returns a signal dict (direction, entry, sl, tp, trader, rule,
#  reasons) or None. All evaluate bar `i` using ONLY data up to `i`.
# ══════════════════════════════════════════════════════════════════════

def turtle_breakout(df: pd.DataFrame, i: int, regime: str,
                    ctx: Optional[dict] = None) -> Optional[dict]:
    """Richard Dennis: Donchian-20 breakout in the trend direction, 2N stop."""
    if regime not in ("TRENDING_UP", "TRENDING_DOWN") or i < DONCHIAN_N + 20:
        return None
    ctx = ctx or _precompute(df)
    c = float(df["close"].iloc[i])
    n = float(ctx["atr20"].iloc[i])
    if pd.isna(n) or n <= 0:
        return None
    hi20 = float(ctx["hi20"].iloc[i])
    lo20 = float(ctx["lo20"].iloc[i])
    if pd.isna(hi20) or pd.isna(lo20):
        return None

    # Decisive breaks only: clear the channel by ≥0.1N to skip the
    # marginal pokes that churn commissions and stop out on noise.
    if regime == "TRENDING_UP" and c > hi20 + 0.1 * n:
        return {
            "direction": "BUY", "entry": c,
            "stop_loss": c - TURTLE_STOP_N * n,
            "take_profit": c + TURTLE_TARGET_N * n,
            "trader": "Richard Dennis (Turtle)",
            "rule": "Donchian-20 breakout with 2N stop",
            "reasons": [
                f"Close {c:.5f} broke above the 20-bar high {hi20:.5f}",
                f"Regime is TRENDING_UP — Turtles only trade with the trend",
                f"Stop 2N below entry (N=ATR20={n:.5f}); initial target 4N (2:1)",
            ],
        }
    if regime == "TRENDING_DOWN" and c < lo20 - 0.1 * n:
        return {
            "direction": "SELL", "entry": c,
            "stop_loss": c + TURTLE_STOP_N * n,
            "take_profit": c - TURTLE_TARGET_N * n,
            "trader": "Richard Dennis (Turtle)",
            "rule": "Donchian-20 breakdown with 2N stop",
            "reasons": [
                f"Close {c:.5f} broke below the 20-bar low {lo20:.5f}",
                f"Regime is TRENDING_DOWN — Turtles only trade with the trend",
                f"Stop 2N above entry (N=ATR20={n:.5f}); initial target 4N (2:1)",
            ],
        }
    return None


def seykota_pullback(df: pd.DataFrame, i: int, regime: str,
                     ctx: Optional[dict] = None) -> Optional[dict]:
    """Ed Seykota: enter trend on RSI pullback re-entry, ride with trail."""
    if regime not in ("TRENDING_UP", "TRENDING_DOWN") or i < PULLBACK_EMA_SLOW + 6:
        return None
    ctx = ctx or _precompute(df)
    c = float(df["close"].iloc[i])
    ef = float(ctx["ema20"].iloc[i])
    es = float(ctx["ema50"].iloc[i])
    r_series = ctx["rsi14"]
    r_now = float(r_series.iloc[i])
    r_win = r_series.iloc[i - 5:i]
    a = float(ctx["atr14"].iloc[i])
    if pd.isna(a) or a <= 0 or pd.isna(r_now):
        return None

    if regime == "TRENDING_UP" and ef > es and c > ef and r_now > 40 and (r_win < 40).any():
        return {
            "direction": "BUY", "entry": c,
            "stop_loss": c - 1.5 * a, "take_profit": c + 3.0 * a,
            "trader": "Ed Seykota",
            "rule": "Trend pullback re-entry; ride winners with a trail",
            "reasons": [
                f"Uptrend intact: EMA20 {ef:.5f} > EMA50 {es:.5f}, price above EMA20",
                f"RSI dipped below 40 within 5 bars (min {float(r_win.min()):.1f}) "
                f"and recovered to {r_now:.1f} — buying the dip in a trend",
                "Exit plan: breakeven at +1R, then trail 2×ATR (let it run)",
            ],
        }
    if regime == "TRENDING_DOWN" and ef < es and c < ef and r_now < 60 and (r_win > 60).any():
        return {
            "direction": "SELL", "entry": c,
            "stop_loss": c + 1.5 * a, "take_profit": c - 3.0 * a,
            "trader": "Ed Seykota",
            "rule": "Trend pullback re-entry; ride winners with a trail",
            "reasons": [
                f"Downtrend intact: EMA20 {ef:.5f} < EMA50 {es:.5f}, price below EMA20",
                f"RSI rose above 60 within 5 bars (max {float(r_win.max()):.1f}) "
                f"and rolled over to {r_now:.1f} — selling the bounce",
                "Exit plan: breakeven at +1R, then trail 2×ATR",
            ],
        }
    return None


def ptj_failed_break(df: pd.DataFrame, i: int, regime: str,
                     ctx: Optional[dict] = None) -> Optional[dict]:
    """
    Paul Tudor Jones: fade the FAILED breakout at range extremes with
    asymmetric R:R. His famous trades were reversals where the crowd
    was trapped. Only valid in RANGING markets.
    """
    if regime != "RANGING" or i < DONCHIAN_N + 5:
        return None
    ctx = ctx or _precompute(df)
    c = float(df["close"].iloc[i])
    lo = float(df["low"].iloc[i])
    hi = float(df["high"].iloc[i])
    a = float(ctx["atr14"].iloc[i])
    if pd.isna(a) or a <= 0:
        return None
    hi20 = float(ctx["hi20"].iloc[i])
    lo20 = float(ctx["lo20"].iloc[i])
    if pd.isna(hi20) or pd.isna(lo20):
        return None
    bar_range = max(hi - lo, 1e-9)

    # Failed breakdown: wick pierces the 20-bar low by ≥0.3×ATR, then a
    # STRONG rejection — close back inside AND in the top 40% of the bar.
    # (Noise wicks without real rejection were bleeding -3R in testing.)
    if lo < lo20 - 0.3 * a and c > lo20 and (c - lo) / bar_range >= 0.6:
        sl = lo - 0.25 * a
        risk = c - sl
        tp = c + PTJ_MIN_RR * risk
        return {
            "direction": "BUY", "entry": c, "stop_loss": sl, "take_profit": tp,
            "trader": "Paul Tudor Jones",
            "rule": f"Failed-breakdown reversal, min {PTJ_MIN_RR}:1 R:R",
            "reasons": [
                f"Bar wicked below the 20-bar low {lo20:.5f} (low {lo:.5f}) "
                f"but CLOSED back inside at {c:.5f} — sellers trapped",
                f"Asymmetric bet: risking {risk:.5f} for {PTJ_MIN_RR}× that",
                "Stop just beyond the failure wick — wrong means out, never average down",
            ],
        }
    # Failed breakout: wick pierces the 20-bar high by ≥0.3×ATR with a
    # strong rejection close in the bottom 40% of the bar.
    if hi > hi20 + 0.3 * a and c < hi20 and (hi - c) / bar_range >= 0.6:
        sl = hi + 0.25 * a
        risk = sl - c
        tp = c - PTJ_MIN_RR * risk
        return {
            "direction": "SELL", "entry": c, "stop_loss": sl, "take_profit": tp,
            "trader": "Paul Tudor Jones",
            "rule": f"Failed-breakout reversal, min {PTJ_MIN_RR}:1 R:R",
            "reasons": [
                f"Bar wicked above the 20-bar high {hi20:.5f} (high {hi:.5f}) "
                f"but CLOSED back inside at {c:.5f} — buyers trapped",
                f"Asymmetric bet: risking {risk:.5f} for {PTJ_MIN_RR}× that",
                "Stop just beyond the failure wick — wrong means out, never average down",
            ],
        }
    return None


def raschke_meanrev(df: pd.DataFrame, i: int, regime: str,
                    ctx: Optional[dict] = None) -> Optional[dict]:
    """Linda Raschke: fade RSI+Bollinger extremes in a range, target the mean."""
    if regime != "RANGING" or i < 25:
        return None
    ctx = ctx or _precompute(df)
    c = float(df["close"].iloc[i])
    u = float(ctx["bb_u"].iloc[i])
    m = float(ctx["bb_m"].iloc[i])
    l = float(ctx["bb_l"].iloc[i])
    r_now = float(ctx["rsi14"].iloc[i])
    a = float(ctx["atr14"].iloc[i])
    if any(pd.isna(x) for x in (u, m, l, r_now)) or pd.isna(a) or a <= 0:
        return None

    if c <= l and r_now < RASCHKE_RSI_LO:
        return {
            "direction": "BUY", "entry": c,
            "stop_loss": c - 1.0 * a, "take_profit": m,
            "trader": "Linda Raschke",
            "rule": "Range fade: RSI oversold at lower Bollinger, target mean",
            "reasons": [
                f"Close {c:.5f} at/below the lower Bollinger band {l:.5f}",
                f"RSI(14) oversold at {r_now:.1f} (< {RASCHKE_RSI_LO:.0f})",
                f"Regime is RANGING — mean reversion is the play; target middle band {m:.5f}",
            ],
        }
    if c >= u and r_now > RASCHKE_RSI_HI:
        return {
            "direction": "SELL", "entry": c,
            "stop_loss": c + 1.0 * a, "take_profit": m,
            "trader": "Linda Raschke",
            "rule": "Range fade: RSI overbought at upper Bollinger, target mean",
            "reasons": [
                f"Close {c:.5f} at/above the upper Bollinger band {u:.5f}",
                f"RSI(14) overbought at {r_now:.1f} (> {RASCHKE_RSI_HI:.0f})",
                f"Regime is RANGING — mean reversion is the play; target middle band {m:.5f}",
            ],
        }
    return None


STRATEGIES = [turtle_breakout, seykota_pullback, ptj_failed_break, raschke_meanrev]


# ══════════════════════════════════════════════════════════════════════
#  Ensemble — confluence, PTJ 200-SMA veto, Dalio correlation guard
# ══════════════════════════════════════════════════════════════════════

def _evaluate_pair(df: pd.DataFrame, pair: str, ctx: Optional[dict] = None,
                   i: Optional[int] = None) -> tuple[dict, list[dict]]:
    """Run regime detection + all strategies on bar `i` (default last)."""
    i = len(df) - 1 if i is None else i
    ctx = ctx or _precompute(df)
    reg = detect_regime(df, i, ctx)
    regime = reg["regime"]

    raw = []
    for strat in STRATEGIES:
        try:
            sig = strat(df, i, regime, ctx)
            if sig:
                raw.append(sig)
        except Exception as exc:
            logger.warning("Legend strategy %s failed on %s: %s",
                           strat.__name__, pair, exc)

    # PTJ 200-SMA veto — applies to trend entries (Turtle/Seykota):
    # no longs below the 200, no shorts above it.
    s200 = ctx["sma200"]
    c = float(df["close"].iloc[i])
    line = float(s200.iloc[i]) if not pd.isna(s200.iloc[i]) else None

    kept = []
    for sig in raw:
        trend_entry = sig["trader"].startswith(("Richard", "Ed"))
        if line is not None and trend_entry:
            if sig["direction"] == "BUY" and c < line:
                continue  # vetoed: long below the 200-SMA
            if sig["direction"] == "SELL" and c > line:
                continue  # vetoed: short above the 200-SMA
            sig["reasons"].append(
                f"Tudor Jones veto passed: price on the correct side of the "
                f"200-SMA ({line:.5f})"
            )
        kept.append(sig)

    return reg, kept


def _merge_pair_signals(pair: str, signals: list[dict], regime: dict,
                        governor: RiskGovernor) -> Optional[dict]:
    """Merge same-direction signals into one order with confluence score."""
    if not signals:
        return None
    buys = [s for s in signals if s["direction"] == "BUY"]
    sells = [s for s in signals if s["direction"] == "SELL"]
    # Conflicting reads = no trade (discipline over activity)
    if buys and sells:
        return None
    group = buys or sells
    lead = group[0]  # strategy order encodes priority (trend first)
    confluence = len(group)

    # Druckenmiller conviction sizing: base risk 0.75%, bump to the
    # governor's full risk% only when ≥2 legends agree. Never above cap.
    base_risk = min(0.75, governor.risk_per_trade_pct)
    risk_pct = governor.risk_per_trade_pct if confluence >= 2 else base_risk
    sized_gov = RiskGovernor(
        equity=governor.equity, risk_per_trade_pct=risk_pct,
        max_daily_loss_pct=governor.max_daily_loss_pct,
        max_weekly_loss_pct=governor.max_weekly_loss_pct,
    )

    entry, sl, tp = lead["entry"], lead["stop_loss"], lead["take_profit"]
    rr = round(abs(tp - entry) / abs(entry - sl), 2) if entry != sl else 0.0

    return {
        "pair": pair,
        "direction": lead["direction"],
        "entry": round(entry, 5),
        "stop_loss": round(sl, 5),
        "take_profit": round(tp, 5),
        "risk_reward": rr,
        "confluence": confluence,
        "conviction": "HIGH" if confluence >= 2 else "NORMAL",
        "regime": regime["regime"],
        "regime_detail": regime["detail"],
        "trader": lead["trader"],
        "rule": lead["rule"],
        "agreeing_legends": [s["trader"] for s in group],
        "reasons": [r for s in group for r in s["reasons"]],
        "trailing": {
            "breakeven_at_r": TRAIL_BE_AT_R,
            "trail_atr_mult": TRAIL_ATR_MULT,
            "note": "Seykota exit: stop to breakeven at +1R, then trail 2×ATR",
        },
        "position": sized_gov.position_size(entry, sl, pair),
        "risk_pct_used": risk_pct,
        "timeframe": "1H",
        "generated_at": datetime.now(IST).isoformat(),
    }


# ── Edge Gate (Druckenmiller/Livermore meta-rule) ────────────────────
# The system measures its OWN trailing 90-day performance per pair.
# If the ensemble has been losing there (PF < 1 over enough trades),
# it refuses to trade that pair: no edge, no trade. Self-correcting —
# this is exactly what "it was profitable before, now it loses" needs.
_EDGE_TTL = 6 * 3600.0
_edge_cache: dict[str, tuple[float, dict]] = {}

EDGE_MIN_TRADES = 8
EDGE_MIN_PF = 1.0


def _edge_check(pair: str, df: pd.DataFrame) -> dict:
    import time as _time
    hit = _edge_cache.get(pair)
    if hit and (_time.time() - hit[0]) < _EDGE_TTL:
        return hit[1]

    bt = _backtest_frame(df, pair, RiskGovernor())
    pf = bt.get("profit_factor")
    n = bt.get("total_trades", 0)
    has_edge = not (n >= EDGE_MIN_TRADES and (pf is None or pf < EDGE_MIN_PF))
    result = {
        "has_edge": has_edge,
        "trailing_trades": n,
        "trailing_profit_factor": pf,
        "detail": (
            f"Trailing edge OK (PF {pf}, {n} trades)" if has_edge else
            f"NO EDGE: trailing PF {pf} over {n} trades — Livermore rule: "
            f"standing aside on this pair until the edge returns"
        ),
    }
    _edge_cache[pair] = (_time.time(), result)
    return result


def generate_signals(pairs: Optional[list[str]] = None,
                     governor: Optional[RiskGovernor] = None) -> dict:
    """Scan pairs with the full legends ensemble."""
    governor = governor or RiskGovernor()
    pairs = [_normalise_pair(p) for p in (pairs or DEFAULT_PAIRS)]

    breaker, reason = governor.circuit_breaker_active()
    if breaker:
        return {"signals": [], "circuit_breaker": True,
                "circuit_breaker_reason": reason,
                "regimes": {}, "scanned_pairs": pairs,
                "generated_at": datetime.now(IST).isoformat()}

    merged: list[dict] = []
    regimes: dict[str, dict] = {}
    edges: dict[str, dict] = {}
    for pair in pairs:
        try:
            df = _fetch_ohlcv(pair, days=90)
            if df is None or len(df) < PTJ_SMA + 10:
                regimes[pair] = {"regime": "NO_DATA", "detail": "insufficient history"}
                continue

            edge = _edge_check(pair, df)
            edges[pair] = edge

            reg, sigs = _evaluate_pair(df, pair)
            regimes[pair] = reg

            if not edge["has_edge"]:
                continue  # no edge on this pair — stand aside

            sig = _merge_pair_signals(pair, sigs, reg, governor)
            if sig:
                sig["edge"] = edge
                merged.append(sig)
        except Exception as exc:
            logger.warning("Legends scan failed for %s: %s", pair, exc)

    # Dalio correlation guard: same-direction signals in highly
    # correlated pairs are one bet — keep the higher-conviction one.
    merged.sort(key=lambda s: (-s["confluence"], s["pair"]))
    final: list[dict] = []
    dropped: list[dict] = []
    for sig in merged:
        clash = next(
            (k for k in final
             if abs(_corr(k["pair"], sig["pair"])) > 0.75
             and ((_corr(k["pair"], sig["pair"]) > 0) == (k["direction"] == sig["direction"]))),
            None,
        )
        if clash:
            dropped.append({
                "pair": sig["pair"], "direction": sig["direction"],
                "reason": (f"Dalio correlation guard: {sig['pair']} is one bet with "
                           f"{clash['pair']} (r={_corr(clash['pair'], sig['pair']):+.2f}) — "
                           f"kept the higher-conviction signal"),
            })
        else:
            final.append(sig)

    return {
        "signals": final,
        "suppressed_by_correlation": dropped,
        "regimes": regimes,
        "edges": edges,
        "circuit_breaker": False,
        "circuit_breaker_reason": None,
        "scanned_pairs": pairs,
        "generated_at": datetime.now(IST).isoformat(),
    }


# ══════════════════════════════════════════════════════════════════════
#  Backtest — ensemble replayed bar-by-bar with Seykota trailing exits
# ══════════════════════════════════════════════════════════════════════

def backtest(pair: str, days: int = 180,
             governor: Optional[RiskGovernor] = None) -> dict:
    governor = governor or RiskGovernor()
    pair = _normalise_pair(pair)
    df = _fetch_ohlcv(pair, days=days)
    if df is None or len(df) < PTJ_SMA + 30:
        return {"error": f"Not enough historical data for {pair}"}
    result = _backtest_frame(df, pair, governor)
    result["days"] = days
    return result


def _backtest_frame(df: pd.DataFrame, pair: str,
                    governor: RiskGovernor) -> dict:
    """Core ensemble replay on an already-fetched frame (O(n))."""
    equity = governor.equity
    start_equity = equity
    peak, max_dd = equity, 0.0
    trades: list[dict] = []
    pos: Optional[dict] = None
    curve: list[float] = []
    ctx = _precompute(df)
    atr_series = ctx["atr14"]

    for i in range(PTJ_SMA + 1, len(df)):
        hi, lo = float(df["high"].iloc[i]), float(df["low"].iloc[i])
        a = float(atr_series.iloc[i]) if not pd.isna(atr_series.iloc[i]) else None

        # ── Manage open position (stop / target / trail) ──
        if pos:
            exited, exit_price, result = False, None, None
            risk0 = abs(pos["entry"] - pos["sl0"])

            if pos["direction"] == "BUY":
                pos["best"] = max(pos["best"], hi)
                # Seykota trail: breakeven at +1R, then 2×ATR behind best
                if pos["best"] >= pos["entry"] + TRAIL_BE_AT_R * risk0:
                    trail = (pos["best"] - TRAIL_ATR_MULT * a) if a else pos["entry"]
                    pos["sl"] = max(pos["sl"], pos["entry"], trail)
                if lo <= pos["sl"]:
                    exited, exit_price = True, pos["sl"]
                elif hi >= pos["tp"]:
                    exited, exit_price = True, pos["tp"]
            else:
                pos["best"] = min(pos["best"], lo)
                if pos["best"] <= pos["entry"] - TRAIL_BE_AT_R * risk0:
                    trail = (pos["best"] + TRAIL_ATR_MULT * a) if a else pos["entry"]
                    pos["sl"] = min(pos["sl"], pos["entry"], trail)
                if hi >= pos["sl"]:
                    exited, exit_price = True, pos["sl"]
                elif lo <= pos["tp"]:
                    exited, exit_price = True, pos["tp"]

            if exited:
                if pos["direction"] == "BUY":
                    r_mult = (exit_price - pos["entry"]) / risk0
                else:
                    r_mult = (pos["entry"] - exit_price) / risk0
                r_mult = round(r_mult, 2)
                risk_amt = equity * pos["risk_pct"] / 100.0
                pnl = risk_amt * r_mult
                equity += pnl
                trades.append({
                    "direction": pos["direction"], "trader": pos["trader"],
                    "regime": pos["regime"],
                    "entry": round(pos["entry"], 5), "exit": round(exit_price, 5),
                    "r_multiple": r_mult, "pnl": round(pnl, 2),
                    "result": "win" if pnl > 0 else ("loss" if pnl < 0 else "flat"),
                })
                pos = None
                peak = max(peak, equity)
                max_dd = max(max_dd, (peak - equity) / peak * 100.0)

        # ── New entry (one position at a time) ──
        if pos is None:
            reg, sigs = _evaluate_pair(df, pair, ctx=ctx, i=i)
            sig = _merge_pair_signals(pair, sigs, reg, governor)
            if sig:
                pos = {
                    "direction": sig["direction"], "entry": sig["entry"],
                    "sl": sig["stop_loss"], "sl0": sig["stop_loss"],
                    "tp": sig["take_profit"],
                    "best": sig["entry"], "trader": sig["trader"],
                    "regime": sig["regime"], "risk_pct": sig["risk_pct_used"],
                }

        curve.append(equity)

    wins = [t for t in trades if t["result"] == "win"]
    losses = [t for t in trades if t["result"] == "loss"]
    gross_w = sum(t["pnl"] for t in wins)
    gross_l = abs(sum(t["pnl"] for t in losses))
    n = len(trades)

    def _bucket(key: str) -> dict:
        out: dict[str, dict] = {}
        for t in trades:
            k = t[key]
            b = out.setdefault(k, {"trades": 0, "wins": 0, "net_r": 0.0})
            b["trades"] += 1
            b["wins"] += t["result"] == "win"
            b["net_r"] = round(b["net_r"] + t["r_multiple"], 2)
        for b in out.values():
            b["win_rate_pct"] = round(b["wins"] / b["trades"] * 100, 1)
        return out

    step = max(1, len(curve) // 200)
    return {
        "pair": pair, "timeframe": "1H",
        "total_trades": n,
        "wins": len(wins), "losses": len(losses),
        "win_rate_pct": round(len(wins) / n * 100, 1) if n else 0.0,
        "avg_r_multiple": round(sum(t["r_multiple"] for t in trades) / n, 2) if n else 0.0,
        "profit_factor": round(gross_w / gross_l, 2) if gross_l else None,
        "net_pnl": round(equity - start_equity, 2),
        "return_pct": round((equity - start_equity) / start_equity * 100, 2),
        "max_drawdown_pct": round(max_dd, 2),
        "start_equity": start_equity, "end_equity": round(equity, 2),
        "by_trader": _bucket("trader"),
        "by_regime": _bucket("regime"),
        "equity_curve": [round(v, 2) for v in curve[::step]],
        "trades_sample": trades[-20:],
        "disclaimer": (
            "Backtested performance does not guarantee future results. "
            "Legends Mode is decision support with strict risk management, "
            "not a promise of profit."
        ),
        "generated_at": datetime.now(IST).isoformat(),
    }


# ══════════════════════════════════════════════════════════════════════
#  Roster — served to the UI for full transparency
# ══════════════════════════════════════════════════════════════════════

TRADER_ROSTER = [
    {"name": "Richard Dennis", "tag": "Turtle Trading",
     "rule": "Donchian-20 breakouts, 2N volatility stops, trend only",
     "active_in": ["TRENDING_UP", "TRENDING_DOWN"]},
    {"name": "Ed Seykota", "tag": "Trend Rider",
     "rule": "Buy trend pullbacks; breakeven at +1R, trail 2×ATR — ride winners",
     "active_in": ["TRENDING_UP", "TRENDING_DOWN"]},
    {"name": "Paul Tudor Jones", "tag": "Contrarian Risk",
     "rule": "200-SMA veto on all trend entries; fade failed breakouts at ≥2.5:1",
     "active_in": ["RANGING", "veto everywhere"]},
    {"name": "Linda Raschke", "tag": "Range Specialist",
     "rule": "Fade RSI+Bollinger extremes inside ranges, target the mean",
     "active_in": ["RANGING"]},
    {"name": "Jesse Livermore", "tag": "Patience",
     "rule": "Choppy/dead market → no position. Sitting is a strategy",
     "active_in": ["CHOPPY (stand aside)"]},
    {"name": "Ray Dalio", "tag": "Diversification",
     "rule": "Correlated same-direction signals collapse into one bet — drop extras",
     "active_in": ["portfolio guard"]},
    {"name": "Stanley Druckenmiller", "tag": "Conviction Sizing",
     "rule": "Full risk only when ≥2 legends agree; 0.75% otherwise",
     "active_in": ["position sizing"]},
    {"name": "Bill Lipschutz", "tag": "Risk Governor",
     "rule": "Mandatory stops, fixed-fraction sizing, -3%/day & -6%/week breakers",
     "active_in": ["always on"]},
]
