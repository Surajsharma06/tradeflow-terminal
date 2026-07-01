"""
Multi-Timeframe Confluence (MTF) — checks 1H, 4H, Daily agreement.
Returns mtf_score (0-3) and per-TF details.
"""
from __future__ import annotations

import logging
from typing import Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def _ema(s: pd.Series, n: int) -> float:
    if len(s) < n:
        return float(s.iloc[-1])
    return float(s.ewm(span=n, adjust=False).mean().iloc[-1])


def _rsi(s: pd.Series, n: int = 14) -> float:
    delta = s.diff()
    gain = delta.where(delta > 0, 0.0).ewm(span=n, adjust=False).mean()
    loss = (-delta.where(delta < 0, 0.0)).ewm(span=n, adjust=False).mean()
    if loss.iloc[-1] == 0:
        return 100.0
    rs = gain.iloc[-1] / loss.iloc[-1]
    return float(100 - 100 / (1 + rs))


def _tf_direction(df: pd.DataFrame) -> str:
    """BUY / SELL / NEUTRAL for a single timeframe dataframe."""
    if df is None or len(df) < 20:
        return "NEUTRAL"
    close = df["close"]
    price = float(close.iloc[-1])
    e9  = _ema(close, 9)
    e21 = _ema(close, 21)
    e200 = _ema(close, min(200, len(close) - 1))
    rsi = _rsi(close)

    bull_pts = 0
    bear_pts = 0

    if price > e200:
        bull_pts += 1
    else:
        bear_pts += 1

    if e9 > e21:
        bull_pts += 1
    else:
        bear_pts += 1

    if rsi > 50:
        bull_pts += 1
    else:
        bear_pts += 1

    if bull_pts >= 2:
        return "BUY"
    if bear_pts >= 2:
        return "SELL"
    return "NEUTRAL"


def _fetch_tf(pair: str, interval: str) -> Optional[pd.DataFrame]:
    """Fetch OHLCV for a given interval using TwelveData or yfinance fallback."""
    try:
        from app.domain.trading.twelve_data import _fetch_raw, FOREX_PAIRS as TD_PAIRS
        symbol = TD_PAIRS.get(pair)
        if symbol:
            td_interval = {"1h": "1h", "4h": "4h", "1day": "1day"}.get(interval, interval)
            df = _fetch_raw(symbol, td_interval, outputsize=200)
            if df is not None and not df.empty:
                return df
    except Exception:
        pass

    # yfinance fallback
    YF = {
        "EUR/USD": "EURUSD=X", "GBP/USD": "GBPUSD=X", "USD/JPY": "JPY=X",
        "USD/CHF": "CHF=X",   "AUD/USD": "AUDUSD=X", "USD/CAD": "CAD=X",
        "NZD/USD": "NZDUSD=X","EUR/GBP": "EURGBP=X", "EUR/JPY": "EURJPY=X",
        "GBP/JPY": "GBPJPY=X","XAU/USD": "GC=F",     "XAG/USD": "SI=F",
        "BTC/USD": "BTC-USD",  "ETH/USD": "ETH-USD",
    }
    ticker = YF.get(pair, pair.replace("/", "") + "=X")
    try:
        import warnings, yfinance as yf
        warnings.filterwarnings("ignore")
        if interval == "1h":
            df = yf.download(ticker, period="10d",  interval="1h",  auto_adjust=True, progress=False)
        elif interval == "4h":
            df_1h = yf.download(ticker, period="60d", interval="1h", auto_adjust=True, progress=False)
            if df_1h.empty:
                return None
            if isinstance(df_1h.columns, pd.MultiIndex):
                df_1h.columns = [c[0].lower() for c in df_1h.columns]
            else:
                df_1h.columns = [c.lower() for c in df_1h.columns]
            df_1h["volume"] = df_1h.get("volume", 0)
            df = df_1h.resample("4h").agg({"open":"first","high":"max","low":"min","close":"last","volume":"sum"}).dropna()
            return df
        else:
            df = yf.download(ticker, period="200d", interval="1d",  auto_adjust=True, progress=False)
        if df.empty:
            return None
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = [c[0].lower() for c in df.columns]
        else:
            df.columns = [c.lower() for c in df.columns]
        df["volume"] = df.get("volume", 0)
        return df
    except Exception as e:
        logger.debug("MTF yfinance fallback failed %s %s: %s", pair, interval, e)
        return None


def get_mtf_confluence(pair: str, signal_direction: str) -> dict:
    """
    Returns:
        {
            mtf_score: int (0-3),
            mtf_detail: { "1H": "BUY"|"SELL"|"NEUTRAL", "4H": ..., "1D": ... },
            mtf_aligned: bool,
        }
    Always returns a dict — never raises.
    """
    result = {
        "mtf_score": 0,
        "mtf_detail": {"1H": "NEUTRAL", "4H": "NEUTRAL", "1D": "NEUTRAL"},
        "mtf_aligned": False,
    }
    try:
        tfs = {"1H": "1h", "4H": "4h", "1D": "1day"}
        detail = {}
        score = 0
        for label, interval in tfs.items():
            df = _fetch_tf(pair, interval)
            direction = _tf_direction(df)
            detail[label] = direction
            if direction == signal_direction:
                score += 1
        result["mtf_score"] = score
        result["mtf_detail"] = detail
        result["mtf_aligned"] = score >= 2
    except Exception as e:
        logger.debug("MTF confluence error for %s: %s", pair, e)
    return result
