"""
Smart Money Forex Engine — ICT / SMC Concepts
===============================================
Concepts Used:
  1. Fair Value Gap  (FVG) — Bullish & Bearish
  2. Liquidity Sweep — Buy-side & Sell-side
  3. EMA 9 / 15 / 200 — Trend & momentum
  4. Multi-timeframe — 15min (entry) + 4H (bias)

Signal Logic:
  BUY  -> 4H bullish bias + 15m sell-side liquidity sweep + bullish FVG + EMA9 > EMA15
  SELL -> 4H bearish bias + 15m buy-side liquidity sweep  + bearish FVG + EMA9 < EMA15

Data: Twelve Data API (REAL-TIME — no delay)
"""

from __future__ import annotations

import logging
import warnings
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
logger = logging.getLogger(__name__)

IST = ZoneInfo("Asia/Kolkata")

# ── Pairs (same names as Twelve Data uses) ───────────────────────────────
FOREX_PAIRS = {
    "EUR/USD": "EUR/USD",
    "GBP/USD": "GBP/USD",
    "USD/JPY": "USD/JPY",
    "AUD/USD": "AUD/USD",
    "USD/CAD": "USD/CAD",
    "NZD/USD": "NZD/USD",
    "USD/CHF": "USD/CHF",
    "GBP/JPY": "GBP/JPY",
    "USD/INR": "USD/INR",
}


# ── Data Classes ──────────────────────────────────────────────────────────

@dataclass
class FVGZone:
    kind: str           # "bullish" | "bearish"
    top: float
    bottom: float
    formed_at: str      # timestamp string
    filled: bool = False


@dataclass
class LiqSweep:
    kind: str           # "buy_side" | "sell_side"
    swept_level: float
    candle_time: str


@dataclass
class SMCSignal:
    pair: str
    direction: str          # BUY | SELL
    entry: float
    stop_loss: float
    tp1: float
    tp2: float
    tp3: float
    pips_risk: float
    rr_ratio: float
    confidence: int         # 0–100

    # Confluence factors (what fired)
    ema_aligned: bool
    fvg_present: bool
    liq_sweep: bool
    htf_bias: str           # "bullish" | "bearish" | "neutral"
    fvg_zone: Optional[tuple]   # (top, bottom) of nearest FVG
    sweep_level: Optional[float]

    ema9: float
    ema15: float
    ema200: float
    current_price: float

    timeframe_entry: str = "15m"
    timeframe_bias:  str = "4H"
    timestamp: str = field(
        default_factory=lambda: datetime.now(IST).strftime("%d %b %Y %I:%M %p IST")
    )
    reason: str = ""


# ── Data Fetching (Twelve Data — Real-Time) ───────────────────────────────

def fetch_15m(pair: str) -> Optional[pd.DataFrame]:
    """15-minute candles via Twelve Data (real-time, cached 14 min)."""
    from app.domain.trading.twelve_data import fetch_15m as _td_15m
    df = _td_15m(pair)
    if df is not None and not df.empty:
        return df
    # Fallback to yfinance if Twelve Data fails
    logger.warning("Twelve Data failed for %s 15m — falling back to yfinance", pair)
    return _yf_fetch_15m(pair)


def fetch_4h(pair: str) -> Optional[pd.DataFrame]:
    """4H candles via Twelve Data (real-time, cached 3h50m)."""
    from app.domain.trading.twelve_data import fetch_4h as _td_4h
    df = _td_4h(pair)
    if df is not None and not df.empty:
        return df
    # Fallback to yfinance
    logger.warning("Twelve Data failed for %s 4H — falling back to yfinance", pair)
    return _yf_fetch_4h(pair)


# ── yfinance fallback (used only if Twelve Data fails) ────────────────────

def _yf_fetch_15m(pair: str) -> Optional[pd.DataFrame]:
    """yfinance fallback for 15m data."""
    YF_TICKERS = {
        "EUR/USD": "EURUSD=X", "GBP/USD": "GBPUSD=X", "USD/JPY": "JPY=X",
        "AUD/USD": "AUDUSD=X", "USD/CAD": "CAD=X",   "NZD/USD": "NZDUSD=X",
        "USD/CHF": "CHF=X",   "GBP/JPY": "GBPJPY=X", "USD/INR": "INR=X",
    }
    ticker = YF_TICKERS.get(pair)
    if not ticker:
        return None
    try:
        import yfinance as yf
        import warnings
        warnings.filterwarnings("ignore")
        df = yf.download(ticker, period="5d", interval="15m", auto_adjust=True, progress=False)
        if df.empty:
            return None
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = [c[0].lower() for c in df.columns]
        else:
            df.columns = [c.lower() for c in df.columns]
        df.index.name = "date"
        if "volume" not in df.columns:
            df["volume"] = 0
        return df[["open", "high", "low", "close", "volume"]].dropna(
            subset=["open", "high", "low", "close"]
        )
    except Exception as e:
        logger.error("yfinance 15m fallback failed %s: %s", pair, e)
        return None


def _yf_fetch_4h(pair: str) -> Optional[pd.DataFrame]:
    """yfinance fallback for 4H data (1H resampled)."""
    df = _yf_fetch_15m(pair)  # reuse same logic won't work, use 1H
    YF_TICKERS = {
        "EUR/USD": "EURUSD=X", "GBP/USD": "GBPUSD=X", "USD/JPY": "JPY=X",
        "AUD/USD": "AUDUSD=X", "USD/CAD": "CAD=X",   "NZD/USD": "NZDUSD=X",
        "USD/CHF": "CHF=X",   "GBP/JPY": "GBPJPY=X", "USD/INR": "INR=X",
    }
    ticker = YF_TICKERS.get(pair)
    if not ticker:
        return None
    try:
        import yfinance as yf
        import warnings
        warnings.filterwarnings("ignore")
        df_1h = yf.download(ticker, period="30d", interval="1h", auto_adjust=True, progress=False)
        if df_1h.empty:
            return None
        if isinstance(df_1h.columns, pd.MultiIndex):
            df_1h.columns = [c[0].lower() for c in df_1h.columns]
        else:
            df_1h.columns = [c.lower() for c in df_1h.columns]
        if "volume" not in df_1h.columns:
            df_1h["volume"] = 0
        return df_1h.resample("4h").agg({
            "open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"
        }).dropna()
    except Exception as e:
        logger.error("yfinance 4H fallback failed %s: %s", pair, e)
        return None


# ── Indicators ────────────────────────────────────────────────────────────

def ema(series: pd.Series, n: int) -> pd.Series:
    return series.ewm(span=n, adjust=False).mean()


def atr(df: pd.DataFrame, n: int = 14) -> pd.Series:
    hl = df["high"] - df["low"]
    hc = (df["high"] - df["close"].shift()).abs()
    lc = (df["low"]  - df["close"].shift()).abs()
    tr = pd.concat([hl, hc, lc], axis=1).max(axis=1)
    return tr.rolling(n).mean()


def pip_size(pair: str) -> float:
    if "JPY" in pair or "INR" in pair:
        return 0.01
    return 0.0001


def to_pips(diff: float, pair: str) -> float:
    return round(abs(diff) / pip_size(pair), 1)


# ── Fair Value Gap Detection ──────────────────────────────────────────────

def detect_fvg(df: pd.DataFrame, lookback: int = 30) -> list[FVGZone]:
    """
    Fair Value Gap:
      Bullish FVG: candle[i-2].high < candle[i].low   → gap between (candle[i-2].high, candle[i].low)
      Bearish FVG: candle[i-2].low  > candle[i].high  → gap between (candle[i].high, candle[i-2].low)

    Only keep unfilled gaps from the recent `lookback` candles.
    """
    zones: list[FVGZone] = []
    recent = df.tail(lookback + 2)

    for i in range(2, len(recent)):
        c0 = recent.iloc[i - 2]   # candle 1
        c1 = recent.iloc[i - 1]   # candle 2 (impulse)
        c2 = recent.iloc[i]       # candle 3

        ts = str(recent.index[i])

        # Bullish FVG — gap left by strong up-move
        if c0["high"] < c2["low"]:
            bottom = float(c0["high"])
            top    = float(c2["low"])
            # Check if filled by subsequent candles
            filled = (recent.iloc[i:]["low"].min() < bottom)
            zones.append(FVGZone("bullish", top, bottom, ts, filled))

        # Bearish FVG — gap left by strong down-move
        elif c0["low"] > c2["high"]:
            top    = float(c0["low"])
            bottom = float(c2["high"])
            filled = (recent.iloc[i:]["high"].max() > top)
            zones.append(FVGZone("bearish", top, bottom, ts, filled))

    # Return only unfilled, most recent
    unfilled = [z for z in zones if not z.filled]
    return unfilled[-5:]   # last 5 unfilled gaps


# ── Liquidity Sweep Detection ─────────────────────────────────────────────

def detect_liq_sweep(df: pd.DataFrame, swing_lookback: int = 10) -> Optional[LiqSweep]:
    """
    Liquidity Sweep:
      Buy-side  sweep: Price spikes ABOVE recent swing HIGH then closes BELOW it
                       → Smart money swept buy-side liquidity → expect SELL
      Sell-side sweep: Price spikes BELOW recent swing LOW  then closes ABOVE it
                       → Smart money swept sell-side liquidity → expect BUY

    Only checks the last 3 candles for recency.
    """
    if len(df) < swing_lookback + 3:
        return None

    # Swing high/low from the lookback window (excluding last 3 candles)
    swing_window = df.iloc[-(swing_lookback + 3): -3]
    if swing_window.empty:
        return None

    swing_high = float(swing_window["high"].max())
    swing_low  = float(swing_window["low"].min())

    last3 = df.tail(3)

    for i in range(len(last3)):
        row  = last3.iloc[i]
        time = str(last3.index[i])

        # Sell-side liquidity swept → BUY signal
        if row["low"] < swing_low and row["close"] > swing_low:
            logger.debug("Sell-side sweep at %.5f for %s", swing_low, time)
            return LiqSweep("sell_side", swing_low, time)

        # Buy-side liquidity swept → SELL signal
        if row["high"] > swing_high and row["close"] < swing_high:
            logger.debug("Buy-side sweep at %.5f for %s", swing_high, time)
            return LiqSweep("buy_side", swing_high, time)

    return None


# ── Order Block Detection ─────────────────────────────────────────────────

def detect_order_blocks(df: pd.DataFrame, lookback: int = 50) -> list[dict]:
    """
    ICT Order Block Detection.

    Bullish OB  = last bearish candle (close < open) immediately before a strong
                  bullish impulse move (next 3 candles gain > 2× ATR).
    Bearish OB  = last bullish candle (close > open) immediately before a strong
                  bearish impulse move.

    Returns list of OB dicts sorted by recency (newest first), max 6.
    """
    if df is None or len(df) < 10:
        return []

    recent = df.tail(lookback).copy()
    atr_series = atr(recent, 14).ffill()
    obs: list[dict] = []

    for i in range(2, len(recent) - 3):
        candle = recent.iloc[i]
        c_open  = float(candle["open"])
        c_close = float(candle["close"])
        c_high  = float(candle["high"])
        c_low   = float(candle["low"])
        c_atr   = float(atr_series.iloc[i]) if not pd.isna(atr_series.iloc[i]) else 0.0001
        ts      = str(recent.index[i])

        # Next 3 candles impulse strength
        fwd = recent.iloc[i + 1: i + 4]
        fwd_move_up   = float(fwd["close"].max() - fwd["open"].iloc[0])
        fwd_move_down = float(fwd["open"].iloc[0] - fwd["close"].min())

        # ── Bullish OB: bearish candle → strong up-move follows ──
        if c_close < c_open and fwd_move_up > c_atr * 1.5:
            # OB zone = full body of the bearish candle
            obs.append({
                "type":      "bullish",
                "top":       round(max(c_open, c_close), 6),
                "bottom":    round(min(c_open, c_close), 6),
                "high":      round(c_high, 6),
                "low":       round(c_low, 6),
                "timestamp": ts,
                "strength":  round(fwd_move_up / c_atr, 2),
            })

        # ── Bearish OB: bullish candle → strong down-move follows ──
        elif c_close > c_open and fwd_move_down > c_atr * 1.5:
            obs.append({
                "type":      "bearish",
                "top":       round(max(c_open, c_close), 6),
                "bottom":    round(min(c_open, c_close), 6),
                "high":      round(c_high, 6),
                "low":       round(c_low, 6),
                "timestamp": ts,
                "strength":  round(fwd_move_down / c_atr, 2),
            })

    # Sort strongest first, keep last 6
    obs.sort(key=lambda x: x["strength"], reverse=True)
    return obs[:6]


def detect_key_levels(df_4h: pd.DataFrame, df_1d: Optional[pd.DataFrame] = None) -> dict:
    """
    Detect key price levels: Previous Day High/Low, Weekly Open,
    round numbers, and S/R clusters.
    """
    levels: dict = {"pdh": None, "pdl": None, "weekly_open": None, "round_levels": []}
    if df_4h is None or df_4h.empty:
        return levels

    try:
        # Previous day high/low (last complete day)
        daily = df_4h.resample("D").agg({"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()
        if len(daily) >= 2:
            prev_day = daily.iloc[-2]
            levels["pdh"] = round(float(prev_day["high"]), 6)
            levels["pdl"] = round(float(prev_day["low"]), 6)

        # Weekly open
        weekly = df_4h.resample("W").agg({"open": "first"}).dropna()
        if not weekly.empty:
            levels["weekly_open"] = round(float(weekly.iloc[-1]["open"]), 6)

        # Round number levels (psychological levels)
        current = float(df_4h["close"].iloc[-1])
        pip = 0.01 if current < 10 else (1.0 if current < 500 else 100.0)
        step = pip * 50   # every 50 pips
        base = round(current / step) * step
        levels["round_levels"] = [round(base + step * i, 6) for i in range(-3, 4)]

    except Exception as exc:
        logger.warning("Key levels detection failed: %s", exc)

    return levels


# ── 4H Bias ───────────────────────────────────────────────────────────────

def get_4h_bias(df_4h: pd.DataFrame) -> str:
    """
    4H trend bias using EMA 9, 15 + trend EMA (200 if available, else 50, else 20).
      bullish  -> price > trend_ema AND EMA9 > EMA15
      bearish  -> price < trend_ema AND EMA9 < EMA15
      neutral  -> mixed
    """
    if len(df_4h) < 15:
        return "neutral"

    close = df_4h["close"]
    e9    = ema(close, 9).iloc[-1]
    e15   = ema(close, 15).iloc[-1]
    price = float(close.iloc[-1])

    if len(close) >= 202:
        trend_ema = ema(close, 200).iloc[-1]
    elif len(close) >= 52:
        trend_ema = ema(close, 50).iloc[-1]
    else:
        trend_ema = ema(close, 20).iloc[-1]

    if any(np.isnan(x) for x in [e9, e15, trend_ema]):
        return "neutral"

    if price > trend_ema and e9 > e15:
        return "bullish"
    if price < trend_ema and e9 < e15:
        return "bearish"
    return "neutral"


# ── Signal Generator ──────────────────────────────────────────────────────

def generate_signal(pair: str) -> Optional[SMCSignal]:
    """
    Full multi-timeframe Smart Money signal for a forex pair.

    Returns SMCSignal or None if no valid setup found.
    """
    # ── Fetch data ────────────────────────────────────────────
    df_15m = fetch_15m(pair)
    df_4h  = fetch_4h(pair)

    if df_15m is None or len(df_15m) < 50:
        logger.warning("Not enough 15m data for %s", pair)
        return None
    if df_4h is None or len(df_4h) < 20:
        logger.warning("Not enough 4H data for %s", pair)
        return None

    # ── 4H Bias ───────────────────────────────────────────────
    htf_bias = get_4h_bias(df_4h)

    # ── 15m Indicators ───────────────────────────────────────
    close  = df_15m["close"]
    e9     = ema(close, 9)
    e15    = ema(close, 15)
    e200   = ema(close, 200) if len(close) >= 202 else pd.Series([float("nan")] * len(close))
    atr14  = atr(df_15m)

    price  = float(close.iloc[-1])
    e9v    = float(e9.iloc[-1])
    e15v   = float(e15.iloc[-1])
    e200v  = float(e200.iloc[-1]) if not np.isnan(e200.iloc[-1]) else price

    if np.isnan(e9v) or np.isnan(e15v) or np.isnan(atr14.iloc[-1]):
        return None

    atr_val = float(atr14.iloc[-1])

    # ── FVG ───────────────────────────────────────────────────
    fvgs   = detect_fvg(df_15m, lookback=40)
    b_fvgs = [z for z in fvgs if z.kind == "bullish"]
    s_fvgs = [z for z in fvgs if z.kind == "bearish"]

    # ── Liquidity Sweep ───────────────────────────────────────
    sweep  = detect_liq_sweep(df_15m, swing_lookback=15)

    # ── EMA Alignment (15m) ───────────────────────────────────
    ema_bull = e9v > e15v and price > e15v
    ema_bear = e9v < e15v and price < e15v

    pip = pip_size(pair)

    # ══════════════════════════════════════════════════════════
    # BUY Setup
    # Conditions: 4H bullish | sell-side sweep | bullish FVG | EMA bullish
    # ══════════════════════════════════════════════════════════
    buy_score = 0
    buy_reasons = []

    if htf_bias == "bullish":
        buy_score += 30
        buy_reasons.append("4H bias: BULLISH (above EMA200)")

    if sweep and sweep.kind == "sell_side":
        buy_score += 35
        buy_reasons.append(f"Sell-side liquidity swept @ {sweep.swept_level:.5f}")

    if b_fvgs:
        # Check if price is in/near a bullish FVG
        nearest_bfvg = min(b_fvgs, key=lambda z: abs(price - z.bottom))
        if nearest_bfvg.bottom <= price <= nearest_bfvg.top * 1.002 or price < nearest_bfvg.top:
            buy_score += 25
            buy_reasons.append(f"Bullish FVG zone: {nearest_bfvg.bottom:.5f}–{nearest_bfvg.top:.5f}")
    else:
        nearest_bfvg = None

    if ema_bull:
        buy_score += 10
        buy_reasons.append("EMA9 > EMA15 (15m bullish)")

    # ══════════════════════════════════════════════════════════
    # SELL Setup
    # Conditions: 4H bearish | buy-side sweep | bearish FVG | EMA bearish
    # ══════════════════════════════════════════════════════════
    sell_score = 0
    sell_reasons = []

    if htf_bias == "bearish":
        sell_score += 30
        sell_reasons.append("4H bias: BEARISH (below EMA200)")

    if sweep and sweep.kind == "buy_side":
        sell_score += 35
        sell_reasons.append(f"Buy-side liquidity swept @ {sweep.swept_level:.5f}")

    if s_fvgs:
        nearest_sfvg = min(s_fvgs, key=lambda z: abs(price - z.top))
        if nearest_sfvg.bottom * 0.998 <= price <= nearest_sfvg.top:
            sell_score += 25
            sell_reasons.append(f"Bearish FVG zone: {nearest_sfvg.bottom:.5f}–{nearest_sfvg.top:.5f}")
    else:
        nearest_sfvg = None

    if ema_bear:
        sell_score += 10
        sell_reasons.append("EMA9 < EMA15 (15m bearish)")

    # ── Pick best direction ───────────────────────────────────
    if buy_score >= 35 and buy_score >= sell_score:
        direction = "BUY"
        score     = buy_score
        reasons   = buy_reasons
        # SL = below swing low or 1.5x ATR (whichever is further)
        swing_low = df_15m["low"].tail(10).min()
        sl_atr    = price - 1.5 * atr_val
        sl_swing  = swing_low - atr_val * 0.3
        sl        = round(min(sl_atr, sl_swing), 5)
        _risk     = abs(price - sl)              # actual risk in price
        # TP based on 1:1, 1:2, 1:3 R:R
        tp1 = round(price + 1.0 * _risk, 5)
        tp2 = round(price + 2.0 * _risk, 5)
        tp3 = round(price + 3.0 * _risk, 5)
        fvg_zone = (nearest_bfvg.top, nearest_bfvg.bottom) if nearest_bfvg else None

    elif sell_score >= 35 and sell_score > buy_score:
        direction = "SELL"
        score     = sell_score
        reasons   = sell_reasons
        # SL = above swing high or 1.5x ATR (whichever is further)
        swing_high = df_15m["high"].tail(10).max()
        sl_atr     = price + 1.5 * atr_val
        sl_swing   = swing_high + atr_val * 0.3
        sl         = round(max(sl_atr, sl_swing), 5)
        _risk      = abs(price - sl)             # actual risk in price
        # TP based on 1:1, 1:2, 1:3 R:R
        tp1 = round(price - 1.0 * _risk, 5)
        tp2 = round(price - 2.0 * _risk, 5)
        tp3 = round(price - 3.0 * _risk, 5)
        fvg_zone = (nearest_sfvg.top, nearest_sfvg.bottom) if nearest_sfvg else None

    else:
        logger.debug("%s: no setup (buy=%d sell=%d)", pair, buy_score, sell_score)
        return None

    risk  = abs(price - sl)
    rew   = abs(tp3 - price)      # measure against TP3 (1:3)
    rr    = round(rew / risk, 2) if risk > 0 else 0  # should always be 3.0

    # ── MTF Confluence ────────────────────────────────────────
    try:
        from app.domain.trading.mtf_confluence import get_mtf_confluence
        mtf = get_mtf_confluence(pair, direction)
    except Exception:
        mtf = {"mtf_score": 0, "mtf_detail": {}, "mtf_aligned": False}

    # Lower confidence if MTF disagrees
    if mtf["mtf_score"] < 2:
        score = int(score * 0.6)
    else:
        reasons.append(f"MTF aligned {mtf['mtf_score']}/3 TFs")

    # ── News Filter ───────────────────────────────────────────
    try:
        from app.domain.trading.news_filter import check_news
        news = check_news(pair, score)
    except Exception:
        news = {"news_warning": False, "news_events": [], "confidence_penalty": 0}

    score = max(0, score - news["confidence_penalty"])

    sig = SMCSignal(
        pair=pair,
        direction=direction,
        entry=price,
        stop_loss=sl,
        tp1=tp1,
        tp2=tp2,
        tp3=tp3,
        pips_risk=to_pips(risk, pair),
        rr_ratio=rr,
        confidence=min(score, 99),
        ema_aligned=(ema_bull if direction == "BUY" else ema_bear),
        fvg_present=bool(b_fvgs if direction == "BUY" else s_fvgs),
        liq_sweep=sweep is not None and (
            (direction == "BUY"  and sweep.kind == "sell_side") or
            (direction == "SELL" and sweep.kind == "buy_side")
        ),
        htf_bias=htf_bias,
        fvg_zone=fvg_zone,
        sweep_level=sweep.swept_level if sweep else None,
        ema9=round(e9v, 5),
        ema15=round(e15v, 5),
        ema200=round(e200v, 5),
        current_price=round(price, 5),
        reason=" | ".join(reasons),
    )
    # ── Order Blocks + Key Levels ─────────────────────────────
    try:
        obs_15m = detect_order_blocks(df_15m, lookback=60)
        obs_4h  = detect_order_blocks(df_4h,  lookback=30)
        key_lvl = detect_key_levels(df_4h)
    except Exception:
        obs_15m, obs_4h, key_lvl = [], [], {}

    # Attach extra attrs (added to dict at serialisation)
    sig._mtf      = mtf          # type: ignore[attr-defined]
    sig._news     = news         # type: ignore[attr-defined]
    sig._obs_15m  = obs_15m      # type: ignore[attr-defined]
    sig._obs_4h   = obs_4h       # type: ignore[attr-defined]
    sig._key_lvl  = key_lvl      # type: ignore[attr-defined]

    logger.info(
        "SMC Signal: %s %s @ %.5f | SL %.5f | conf %d%% | MTF %d/3",
        sig.direction, sig.pair, sig.entry, sig.stop_loss, sig.confidence,
        mtf["mtf_score"],
    )
    return sig


# ── Scan All Pairs ────────────────────────────────────────────────────────

def scan_all(pairs: Optional[list[str]] = None) -> list[SMCSignal]:
    """Scan all pairs and return valid signals sorted by confidence."""
    if pairs is None:
        pairs = list(FOREX_PAIRS.keys())

    results: list[SMCSignal] = []
    for p in pairs:
        try:
            sig = generate_signal(p)
            if sig:
                results.append(sig)
        except Exception as e:
            logger.error("Error scanning %s: %s", p, e)

    results.sort(key=lambda s: s.confidence, reverse=True)
    return results


def signal_to_dict(sig: SMCSignal) -> dict:
    mtf     = getattr(sig, "_mtf",     {"mtf_score": 0, "mtf_detail": {}, "mtf_aligned": False})
    news    = getattr(sig, "_news",    {"news_warning": False, "news_events": [], "confidence_penalty": 0})
    obs_15m = getattr(sig, "_obs_15m", [])
    obs_4h  = getattr(sig, "_obs_4h",  [])
    key_lvl = getattr(sig, "_key_lvl", {})
    return {
        "pair":          sig.pair,
        "direction":     sig.direction,
        "entry":         sig.entry,
        "stop_loss":     sig.stop_loss,
        "tp1":           sig.tp1,
        "tp2":           sig.tp2,
        "tp3":           sig.tp3,
        "pips_risk":     sig.pips_risk,
        "rr_ratio":      sig.rr_ratio,
        "confidence":    sig.confidence,
        "ema9":          sig.ema9,
        "ema15":         sig.ema15,
        "ema200":        sig.ema200,
        "current_price": sig.current_price,
        "htf_bias":      sig.htf_bias,
        "ema_aligned":   sig.ema_aligned,
        "fvg_present":   sig.fvg_present,
        "liq_sweep":     sig.liq_sweep,
        "fvg_zone":      sig.fvg_zone,
        "sweep_level":   sig.sweep_level,
        "reason":        sig.reason,
        "timestamp":     sig.timestamp,
        "timeframe_entry": sig.timeframe_entry,
        "timeframe_bias":  sig.timeframe_bias,
        # MTF confluence
        "mtf_score":    mtf.get("mtf_score", 0),
        "mtf_detail":   mtf.get("mtf_detail", {}),
        "mtf_aligned":  mtf.get("mtf_aligned", False),
        # News filter
        "news_warning": news.get("news_warning", False),
        "news_events":  news.get("news_events", []),
        # Order Blocks
        "order_blocks_15m": obs_15m,
        "order_blocks_4h":  obs_4h,
        # Key levels
        "key_levels": key_lvl,
    }


# ── Quick CLI test ────────────────────────────────────────────────────────
if __name__ == "__main__":
    import json
    logging.basicConfig(level=logging.INFO)
    print("\n🔍 Scanning forex pairs — Smart Money Concepts...\n")
    sigs = scan_all(["EUR/USD", "GBP/USD", "USD/JPY", "AUD/USD", "USD/CAD"])
    if sigs:
        for s in sigs:
            print(json.dumps(signal_to_dict(s), indent=2))
    else:
        print("No SMC setups found right now. Check back in 15 min.")
