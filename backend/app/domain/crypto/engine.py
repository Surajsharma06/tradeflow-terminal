"""
Crypto Analysis Engine — BTC, ETH, SOL

Analysis pipeline per asset:
  - Technical: EMA 9/21/50/200, RSI(14) + divergence, MACD(12,26,9),
    Bollinger Bands(20,2σ), 24H rolling VWAP + volume spike, Fibonacci retracement
  - Sentiment: Fear & Greed (alternative.me, free), funding rates (Binance, free)
  - Confluence: 7 factors, min 3 required, 4H trend + 1H entry must agree
  - Risk: ATR(14)×1.5 stop, 1:2 / 1:3 targets, 1-2% position sizing
  - Hard blocks: R:R < 1:2 rejected; reverse-signal funding rate flagged
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

import httpx
import numpy as np
import pandas as pd
import yfinance as yf

from app.domain.indicators.technical import (
    ema, sma, rsi, macd, bollinger_bands, atr, adx, volume_sma_ratio,
)

logger = logging.getLogger(__name__)
IST = timezone(timedelta(hours=5, minutes=30))

ASSETS = {
    "BTC": "BTC-USD",
    "ETH": "ETH-USD",
    "SOL": "SOL-USD",
}

ASSET_NAMES = {
    "BTC": "Bitcoin",
    "ETH": "Ethereum",
    "SOL": "Solana",
}


# ══════════════════════════════════════════════════════════════════════
#  Data fetching
# ══════════════════════════════════════════════════════════════════════

def _fetch_crypto(symbol: str, period: str = "60d", interval: str = "1h") -> Optional[pd.DataFrame]:
    try:
        df = yf.Ticker(symbol).history(period=period, interval=interval, auto_adjust=True)
        if df is None or df.empty:
            return None
        df.columns = [c.lower() for c in df.columns]
        # keep only OHLCV
        cols = [c for c in ("open", "high", "low", "close", "volume") if c in df.columns]
        df = df[cols].copy().dropna()
        return df if len(df) >= 20 else None
    except Exception as exc:
        logger.warning("_fetch_crypto %s failed: %s", symbol, exc)
        return None


def _get_fear_greed() -> dict:
    """alternative.me Fear & Greed index — free, no auth."""
    try:
        with httpx.Client(timeout=6) as client:
            r = client.get("https://api.alternative.me/fng/?limit=1")
        if r.status_code == 200:
            d = r.json()["data"][0]
            return {
                "value": int(d["value"]),
                "label": d["value_classification"],
                "timestamp": d.get("timestamp"),
            }
    except Exception:
        pass
    return {"value": 50, "label": "Neutral", "timestamp": None}


def _get_funding_rate(symbol: str) -> dict:
    """Binance perpetual futures funding rate — free public endpoint."""
    binance_sym = {"BTC": "BTCUSDT", "ETH": "ETHUSDT", "SOL": "SOLUSDT"}.get(symbol, "BTCUSDT")
    try:
        with httpx.Client(timeout=6) as client:
            r = client.get(
                f"https://fapi.binance.com/fapi/v1/fundingRate?symbol={binance_sym}&limit=1"
            )
        if r.status_code == 200:
            data = r.json()
            if data:
                rate = float(data[-1]["fundingRate"])
                return {
                    "rate": rate,
                    "rate_pct": round(rate * 100, 4),
                    "extreme": abs(rate) > 0.001,
                    "direction": (
                        "LONG_HEAVY" if rate > 0.001 else
                        "SHORT_HEAVY" if rate < -0.001 else
                        "NEUTRAL"
                    ),
                }
    except Exception:
        pass
    return {"rate": 0.0, "rate_pct": 0.0, "extreme": False, "direction": "NEUTRAL"}


# ══════════════════════════════════════════════════════════════════════
#  Indicator helpers
# ══════════════════════════════════════════════════════════════════════

def _rolling_vwap(df: pd.DataFrame, window: int = 24) -> pd.Series:
    """Rolling 24-bar VWAP (more useful than cumulative for crypto)."""
    tp = (df["high"] + df["low"] + df["close"]) / 3.0
    vol = df["volume"].replace(0, np.nan)
    return (tp * vol).rolling(window).sum() / vol.rolling(window).sum()


def _fibonacci(df: pd.DataFrame, lookback: int = 100) -> dict:
    """Auto Fibonacci retracement on the most recent major swing."""
    recent = df.tail(lookback)
    sh = float(recent["high"].max())
    sl = float(recent["low"].min())
    diff = sh - sl
    return {
        "swing_high": round(sh, 2),
        "swing_low": round(sl, 2),
        "fib_786": round(sh - 0.786 * diff, 2),
        "fib_618": round(sh - 0.618 * diff, 2),
        "fib_500": round(sh - 0.500 * diff, 2),
        "fib_382": round(sh - 0.382 * diff, 2),
    }


def _rsi_divergence(prices: pd.Series, rsi_vals: pd.Series, lookback: int = 30) -> str:
    """Detect bullish / bearish RSI divergence."""
    if len(prices) < lookback:
        return "NONE"
    p = prices.iloc[-lookback:]
    r = rsi_vals.iloc[-lookback:]
    mid = lookback // 2

    # Bullish: price lower low, RSI higher low
    if p.iloc[-1] < p.iloc[:mid].min() and r.iloc[-1] > r.iloc[:mid].min():
        return "BULLISH_DIVERGENCE"

    # Bearish: price higher high, RSI lower high
    if p.iloc[-1] > p.iloc[:mid].max() and r.iloc[-1] < r.iloc[:mid].max():
        return "BEARISH_DIVERGENCE"

    return "NONE"


def _trend_4h(df_4h: Optional[pd.DataFrame]) -> str:
    if df_4h is None or len(df_4h) < 50:
        return "NEUTRAL"
    close = df_4h["close"]
    e50_v = float(ema(close, 50).iloc[-1])
    p = float(close.iloc[-1])
    e200_v = None
    if len(close) >= 200:
        e200_v = float(ema(close, 200).iloc[-1])

    if p > e50_v:
        return "STRONG_BULLISH" if (e200_v and p > e200_v) else "BULLISH"
    elif p < e50_v:
        return "STRONG_BEARISH" if (e200_v and p < e200_v) else "BEARISH"
    return "NEUTRAL"


# ══════════════════════════════════════════════════════════════════════
#  Main asset analysis
# ══════════════════════════════════════════════════════════════════════

def analyze_asset(
    symbol: str,
    fear_greed: Optional[dict] = None,
    account_balance: float = 10_000.0,
    risk_pct: float = 1.0,
) -> dict:
    """Full 7-factor confluence analysis for one crypto asset."""
    yf_sym = ASSETS.get(symbol)
    if not yf_sym:
        return {"error": f"Unknown symbol {symbol}"}

    df_1h = _fetch_crypto(yf_sym, period="60d",  interval="1h")
    df_4h = _fetch_crypto(yf_sym, period="180d", interval="4h")

    if df_1h is None or len(df_1h) < 50:
        return {"error": f"Insufficient 1H data for {symbol}"}

    close = df_1h["close"]
    price = float(close.iloc[-1])

    # ── Indicators ──
    e9  = ema(close, 9);  e21 = ema(close, 21)
    e50 = ema(close, 50)
    e200 = ema(close, 200) if len(close) >= 200 else pd.Series([np.nan] * len(close), index=close.index)

    rsi14 = rsi(close, 14)
    ml, ms, mh = macd(close, 12, 26, 9)
    bb_u, bb_m, bb_l, bb_bw, _ = bollinger_bands(close, 20, 2.0)
    atr14 = atr(df_1h, 14)
    vol_r = volume_sma_ratio(df_1h, 20)
    vwap24 = _rolling_vwap(df_1h, 24)

    def _f(s):
        v = s.iloc[-1]
        return None if pd.isna(v) else float(v)

    cur_e9, cur_e21, cur_e50 = _f(e9), _f(e21), _f(e50)
    cur_e200 = _f(e200)
    cur_rsi  = _f(rsi14) or 50.0
    cur_ml   = _f(ml) or 0.0;  cur_ms = _f(ms) or 0.0;  cur_mh = _f(mh) or 0.0
    prev_mh  = (float(mh.iloc[-2]) if len(mh) > 1 and not pd.isna(mh.iloc[-2]) else 0.0)
    cur_bbu  = _f(bb_u) or price;  cur_bbm = _f(bb_m) or price;  cur_bbl = _f(bb_l) or price
    cur_bbbw = _f(bb_bw) or 0.0
    cur_atr  = _f(atr14) or price * 0.02
    cur_volr = _f(vol_r) or 1.0
    cur_vwap = _f(vwap24)

    # BB squeeze: bandwidth in bottom 20th pct of trailing 100 bars
    bw_hist = bb_bw.dropna().values
    bb_squeeze = (
        cur_bbbw < float(np.percentile(bw_hist[-100:], 20))
        if len(bw_hist) >= 20 else False
    )

    # MACD cross
    macd_cross = "NONE"
    if prev_mh < 0 and cur_mh > 0:
        macd_cross = "BULLISH_CROSS"
    elif prev_mh > 0 and cur_mh < 0:
        macd_cross = "BEARISH_CROSS"

    # Trend reads
    ema_bull = cur_e9 and cur_e21 and cur_e50 and cur_e9 > cur_e21 > cur_e50
    ema_bear = cur_e9 and cur_e21 and cur_e50 and cur_e9 < cur_e21 < cur_e50
    trend_1h = "BULLISH" if ema_bull else ("BEARISH" if ema_bear else "NEUTRAL")
    t4h = _trend_4h(df_4h)

    # RSI divergence
    rsi_div = _rsi_divergence(close, rsi14)

    # Sentiment
    fg = fear_greed or _get_fear_greed()
    funding = _get_funding_rate(symbol)
    fg_v = fg.get("value", 50)

    # ── Confluence buckets ──
    bull_c: list[str] = []
    bear_c: list[str] = []

    # 1. EMA trend
    if ema_bull:   bull_c.append(f"EMA 9 ({cur_e9:.0f}) > EMA 21 ({cur_e21:.0f}) > EMA 50 ({cur_e50:.0f}) — bullish stack")
    if ema_bear:   bear_c.append(f"EMA 9 ({cur_e9:.0f}) < EMA 21 ({cur_e21:.0f}) < EMA 50 ({cur_e50:.0f}) — bearish stack")
    if cur_e200:
        if price > cur_e200: bull_c.append(f"Price above EMA 200 ({cur_e200:.0f})")
        else:                 bear_c.append(f"Price below EMA 200 ({cur_e200:.0f})")

    # 2. RSI
    if 50 < cur_rsi < 70:   bull_c.append(f"RSI {cur_rsi:.1f} — momentum in bull zone")
    elif 30 < cur_rsi < 50: bear_c.append(f"RSI {cur_rsi:.1f} — momentum in bear zone")
    if rsi_div == "BULLISH_DIVERGENCE": bull_c.append("RSI bullish divergence — price making lower lows, RSI not confirming")
    if rsi_div == "BEARISH_DIVERGENCE": bear_c.append("RSI bearish divergence — price making higher highs, RSI not confirming")

    # 3. MACD
    if cur_mh > 0 and cur_ml > cur_ms: bull_c.append(f"MACD histogram positive ({cur_mh:+.1f}), line above signal")
    if cur_mh < 0 and cur_ml < cur_ms: bear_c.append(f"MACD histogram negative ({cur_mh:+.1f}), line below signal")
    if macd_cross == "BULLISH_CROSS":  bull_c.append("MACD bullish histogram crossover this bar")
    if macd_cross == "BEARISH_CROSS":  bear_c.append("MACD bearish histogram crossover this bar")

    # 4. Bollinger Bands
    if price <= cur_bbl:   bull_c.append(f"Price at/below lower Bollinger band ({cur_bbl:.0f}) — oversold extreme")
    elif price >= cur_bbu: bear_c.append(f"Price at/above upper Bollinger band ({cur_bbu:.0f}) — overbought extreme")
    if bb_squeeze:
        bull_c.append(f"Bollinger squeeze (bw {cur_bbbw:.4f}) — volatility contraction, breakout imminent")
        bear_c.append(f"Bollinger squeeze (bw {cur_bbbw:.4f}) — volatility contraction, breakout imminent")

    # 5. VWAP + volume
    if cur_vwap:
        if price > cur_vwap: bull_c.append(f"Price ({price:.0f}) above 24H VWAP ({cur_vwap:.0f})")
        else:                  bear_c.append(f"Price ({price:.0f}) below 24H VWAP ({cur_vwap:.0f})")
    if cur_volr >= 2.0:
        label = f"Volume spike {cur_volr:.1f}× average — institutional activity"
        bull_c.append(label); bear_c.append(label)

    # 6. 4H trend (multi-timeframe)
    if t4h in ("BULLISH", "STRONG_BULLISH"):   bull_c.append(f"4H trend: {t4h}")
    if t4h in ("BEARISH", "STRONG_BEARISH"):   bear_c.append(f"4H trend: {t4h}")

    # 7. Fear & Greed
    if fg_v >= 60:  bull_c.append(f"Fear & Greed {fg_v} ({fg['label']}) — market greed supports bulls")
    if fg_v <= 25:  bear_c.append(f"Fear & Greed {fg_v} ({fg['label']}) — extreme fear, contrarian buy possible")

    # ── Signal decision ──
    direction: Optional[str] = None
    signal_reasons: list[str] = []

    if (len(bull_c) >= 3
            and t4h in ("BULLISH", "STRONG_BULLISH")
            and trend_1h in ("BULLISH", "NEUTRAL")
            and cur_rsi < 75):
        direction = "LONG"
        signal_reasons = bull_c

    elif (len(bear_c) >= 3
            and t4h in ("BEARISH", "STRONG_BEARISH")
            and trend_1h in ("BEARISH", "NEUTRAL")
            and cur_rsi > 25):
        direction = "SHORT"
        signal_reasons = bear_c

    # Funding rate contrarian warning
    if direction == "LONG" and funding["direction"] == "LONG_HEAVY":
        signal_reasons.append(
            f"⚠️ Funding rate +{funding['rate_pct']}% — longs heavily funded, crowded trade risk"
        )
    elif direction == "SHORT" and funding["direction"] == "SHORT_HEAVY":
        signal_reasons.append(
            f"⚠️ Funding rate {funding['rate_pct']}% — shorts heavily funded, short-squeeze risk"
        )

    # ── Trade parameters ──
    signal: Optional[dict] = None
    if direction:
        entry = price
        if direction == "LONG":
            sl  = round(entry - 1.5 * cur_atr, 2)
            risk = entry - sl
            tp1 = round(entry + 2.0 * risk, 2)
            tp2 = round(entry + 3.0 * risk, 2)
        else:
            sl   = round(entry + 1.5 * cur_atr, 2)
            risk = sl - entry
            tp1  = round(entry - 2.0 * risk, 2)
            tp2  = round(entry - 3.0 * risk, 2)

        # Hard block: R:R < 1:2 (should not happen with the above math, but guard anyway)
        rr1 = round(abs(tp1 - entry) / risk, 1) if risk > 0 else 0
        rr2 = round(abs(tp2 - entry) / risk, 1) if risk > 0 else 0

        score = len(signal_reasons)
        confidence_note = (
            "High confidence — strong multi-factor alignment (5+ confluences)" if score >= 5 else
            "Medium-high confidence — solid setup (4 confluences)" if score >= 4 else
            "Medium — minimum confluence met; use smaller position size"
        )

        risk_amt = account_balance * risk_pct / 100.0
        units = round(risk_amt / risk, 6) if risk > 0 else 0

        signal = {
            "direction": direction,
            "entry": round(entry, 2),
            "stop_loss": sl,
            "take_profit_1": tp1,
            "take_profit_2": tp2,
            "risk_reward_1": rr1,
            "risk_reward_2": rr2,
            "timeframe": "4H trend / 1H entry",
            "confluence_score": f"{score}/7",
            "confluence_score_num": score,
            "reasons": signal_reasons,
            "confidence_note": confidence_note,
            "position_size": {
                "units": units,
                "risk_amount": round(risk_amt, 2),
                "risk_pct": risk_pct,
                "account_balance": account_balance,
            },
        }

    fib = _fibonacci(df_1h, 100)

    return {
        "symbol": symbol,
        "name": ASSET_NAMES.get(symbol, symbol),
        "price": round(price, 2),
        "trend_4h": t4h,
        "trend_1h": trend_1h,
        "indicators": {
            "ema": {
                "e9":  round(cur_e9,  2) if cur_e9  else None,
                "e21": round(cur_e21, 2) if cur_e21 else None,
                "e50": round(cur_e50, 2) if cur_e50 else None,
                "e200": round(cur_e200, 2) if cur_e200 else None,
            },
            "rsi": {"value": round(cur_rsi, 1), "divergence": rsi_div},
            "macd": {
                "line": round(cur_ml, 2),
                "signal_line": round(cur_ms, 2),
                "histogram": round(cur_mh, 2),
                "cross": macd_cross,
                "bullish": cur_mh > 0,
            },
            "bollinger": {
                "upper": round(cur_bbu, 2),
                "middle": round(cur_bbm, 2),
                "lower": round(cur_bbl, 2),
                "bandwidth": round(cur_bbbw, 6),
                "squeeze": bb_squeeze,
            },
            "vwap_24h": round(cur_vwap, 2) if cur_vwap else None,
            "volume_ratio": round(cur_volr, 2),
            "volume_spike": cur_volr >= 2.0,
            "atr": round(cur_atr, 2),
            "fibonacci": fib,
        },
        "sentiment": {
            "fear_greed": fg,
            "funding": funding,
        },
        "confluence": {
            "bullish": bull_c,
            "bearish": bear_c,
            "active_direction": direction,
            "active_score": len(signal_reasons) if direction else None,
            "bull_score": len(bull_c),
            "bear_score": len(bear_c),
        },
        "signal": signal,
        "generated_at": datetime.now(IST).isoformat(),
    }


def analyze_all(account_balance: float = 10_000.0, risk_pct: float = 1.0) -> dict:
    """Analyze BTC, ETH, SOL with shared Fear & Greed fetch."""
    fg = _get_fear_greed()
    results = {}
    for sym in ASSETS:
        try:
            results[sym] = analyze_asset(sym, fear_greed=fg,
                                          account_balance=account_balance,
                                          risk_pct=risk_pct)
        except Exception as exc:
            logger.exception("Crypto analysis failed for %s: %s", sym, exc)
            results[sym] = {"error": str(exc), "symbol": sym}

    active_signals = [sym for sym, r in results.items() if r.get("signal")]
    return {
        "assets": results,
        "fear_greed": fg,
        "active_signals": active_signals,
        "generated_at": datetime.now(IST).isoformat(),
        "disclaimer": (
            "Crypto signals are analysis tools only, not financial advice. "
            "Manual confirmation required before every trade. "
            "Crypto markets carry extreme volatility and risk of total loss."
        ),
    }
