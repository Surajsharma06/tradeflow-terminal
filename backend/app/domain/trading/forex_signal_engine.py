"""
Forex Signal Engine — ADX + Session + ATR-based ICT/SMC signals
================================================================
Covers all major, minor, and exotic forex pairs plus XAU/USD, XAG/USD,
BTC/USD, ETH/USD.

Signal Logic:
  BUY  → EMA trend up + ADX > 20 + RSI not overbought + session active
  SELL → EMA trend down + ADX > 20 + RSI not oversold + session active

Targets:
  SL  = entry ± 1.5 × ATR(14)
  TP1 = entry ± 1.0 × ATR
  TP2 = entry ± 2.0 × ATR
  TP3 = entry ± 3.0 × ATR

Confidence score = weighted combination of ADX strength, EMA alignment,
RSI position, trend consistency, and session quality.

Saves output to data/signals/signals.json.
"""

from __future__ import annotations

import json
import logging
import os
import warnings
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
logger = logging.getLogger(__name__)

UTC = timezone.utc

# ── Project root (3 levels up from this file) ───────────────────────────────
_ROOT = Path(__file__).resolve().parents[4]
_DATA_DIR = _ROOT / "data" / "forex"
_SIGNALS_FILE = _ROOT / "data" / "signals" / "signals.json"

# ── All supported pairs ──────────────────────────────────────────────────────
ALL_PAIRS: list[str] = [
    # Majors
    "EUR/USD", "GBP/USD", "USD/JPY", "USD/CHF",
    "AUD/USD", "USD/CAD", "NZD/USD",
    # EUR crosses
    "EUR/GBP", "EUR/JPY", "EUR/AUD", "EUR/CAD", "EUR/CHF", "EUR/NZD",
    # GBP crosses
    "GBP/JPY", "GBP/AUD", "GBP/CAD", "GBP/CHF", "GBP/NZD",
    # AUD/NZD/CAD crosses
    "AUD/CAD", "AUD/CHF", "AUD/JPY", "AUD/NZD",
    "CAD/CHF", "CAD/JPY",
    "CHF/JPY",
    "NZD/CAD", "NZD/CHF", "NZD/JPY",
    # Metals
    "XAU/USD", "XAG/USD",
    # Crypto
    "BTC/USD", "ETH/USD",
]

# Map pair → yfinance ticker
_YF_MAP: dict[str, str] = {
    "EUR/USD": "EURUSD=X", "GBP/USD": "GBPUSD=X", "USD/JPY": "USDJPY=X",
    "USD/CHF": "USDCHF=X", "AUD/USD": "AUDUSD=X", "USD/CAD": "USDCAD=X",
    "NZD/USD": "NZDUSD=X", "EUR/GBP": "EURGBP=X", "EUR/JPY": "EURJPY=X",
    "EUR/AUD": "EURAUD=X", "EUR/CAD": "EURCAD=X", "EUR/CHF": "EURCHF=X",
    "EUR/NZD": "EURNZD=X", "GBP/JPY": "GBPJPY=X", "GBP/AUD": "GBPAUD=X",
    "GBP/CAD": "GBPCAD=X", "GBP/CHF": "GBPCHF=X", "GBP/NZD": "GBPNZD=X",
    "AUD/CAD": "AUDCAD=X", "AUD/CHF": "AUDCHF=X", "AUD/JPY": "AUDJPY=X",
    "AUD/NZD": "AUDNZD=X", "CAD/CHF": "CADCHF=X", "CAD/JPY": "CADJPY=X",
    "CHF/JPY": "CHFJPY=X", "NZD/CAD": "NZDCAD=X", "NZD/CHF": "NZDCHF=X",
    "NZD/JPY": "NZDJPY=X",
    "XAU/USD": "GC=F",   "XAG/USD": "SI=F",
    "BTC/USD": "BTC-USD", "ETH/USD": "ETH-USD",
}

# Map pair → local CSV stem (hourly)
_CSV_MAP: dict[str, str] = {
    "EUR/USD": "EURUSD", "GBP/USD": "GBPUSD", "USD/JPY": "USDJPY",
    "USD/CHF": "USDCHF", "AUD/USD": "AUDUSD", "USD/CAD": "USDCAD",
    "NZD/USD": "NZDUSD", "EUR/GBP": "EURGBP", "EUR/JPY": "EURJPY",
    "EUR/AUD": "EURAUD", "EUR/CAD": "EURCAD", "EUR/CHF": "EURCHF",
    "GBP/JPY": "GBPJPY", "GBP/AUD": "GBPAUD", "GBP/CHF": "GBPCHF",
    "AUD/CAD": "AUDCAD", "AUD/JPY": "AUDJPY",
    "CAD/JPY": "CADJPY",  "NZD/JPY": "NZDJPY",
    "XAU/USD": "XAUUSD", "XAG/USD": "XAGUSD",
    "BTC/USD": "BTCUSD", "ETH/USD": "ETHUSD",
}

# Pairs where price is JPY-based (need different pip precision)
_JPY_PAIRS = {p for p in ALL_PAIRS if "/JPY" in p or "JPY/" in p}


# ── Session windows (UTC hours) ──────────────────────────────────────────────
SESSIONS = {
    "Asian":   (0, 8),
    "London":  (8, 16),
    "NY":      (13, 21),
    "Overlap": (13, 16),   # London-NY overlap
}


def get_active_sessions(dt: Optional[datetime] = None) -> list[str]:
    """Return list of currently active sessions."""
    if dt is None:
        dt = datetime.now(UTC)
    h = dt.hour
    active = []
    for name, (start, end) in SESSIONS.items():
        if start <= h < end:
            active.append(name)
    return active or ["Off-hours"]


# ── Data classes ─────────────────────────────────────────────────────────────

@dataclass
class ForexSignal:
    pair: str
    direction: str          # BUY | SELL
    entry: float
    stop_loss: float
    tp1: float
    tp2: float
    tp3: float
    pips_risk: float
    confidence: int         # 0–100
    adx: float
    atr: float
    ema9: float
    ema15: float
    ema200: float
    rsi: float
    sessions: list[str] = field(default_factory=list)
    reason: str = ""
    timestamp: str = ""
    htf_bias: str = "neutral"


# ── Indicator helpers ────────────────────────────────────────────────────────

def _ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()


def _atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    hl = df["high"] - df["low"]
    hc = (df["high"] - df["close"].shift(1)).abs()
    lc = (df["low"] - df["close"].shift(1)).abs()
    tr = pd.concat([hl, hc, lc], axis=1).max(axis=1)
    return tr.ewm(span=period, adjust=False).mean()


def _adx(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Compute ADX without external library."""
    high, low, close = df["high"], df["low"], df["close"]
    plus_dm = high.diff()
    minus_dm = -low.diff()
    plus_dm = plus_dm.where((plus_dm > minus_dm) & (plus_dm > 0), 0.0)
    minus_dm = minus_dm.where((minus_dm > plus_dm) & (minus_dm > 0), 0.0)

    tr = pd.concat([
        high - low,
        (high - close.shift(1)).abs(),
        (low - close.shift(1)).abs(),
    ], axis=1).max(axis=1)

    atr_s = tr.ewm(span=period, adjust=False).mean()
    plus_di = 100 * plus_dm.ewm(span=period, adjust=False).mean() / atr_s.replace(0, np.nan)
    minus_di = 100 * minus_dm.ewm(span=period, adjust=False).mean() / atr_s.replace(0, np.nan)
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
    return dx.ewm(span=period, adjust=False).mean()


def _rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.where(delta > 0, 0.0).ewm(span=period, adjust=False).mean()
    loss = (-delta.where(delta < 0, 0.0)).ewm(span=period, adjust=False).mean()
    rs = gain / loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


# ── Data loading ─────────────────────────────────────────────────────────────

def _load_from_csv(pair: str) -> Optional[pd.DataFrame]:
    stem = _CSV_MAP.get(pair)
    if not stem:
        return None
    path = _DATA_DIR / "hourly" / f"{stem}_1h.csv"
    if not path.exists():
        return None
    try:
        df = pd.read_csv(path)
        # Normalise column names
        df.columns = [c.lower() for c in df.columns]
        time_col = "datetime" if "datetime" in df.columns else "date"
        df["time"] = pd.to_datetime(df[time_col], utc=True)
        df = df.rename(columns={"open": "open", "high": "high", "low": "low", "close": "close"})
        df = df[["time", "open", "high", "low", "close"]].dropna().sort_values("time")
        df = df.tail(300).reset_index(drop=True)
        for col in ["open", "high", "low", "close"]:
            df[col] = pd.to_numeric(df[col], errors="coerce")
        df = df.dropna()
        return df if len(df) >= 50 else None
    except Exception as e:
        logger.debug("CSV load failed %s: %s", pair, e)
        return None


def _load_from_yfinance(pair: str) -> Optional[pd.DataFrame]:
    ticker = _YF_MAP.get(pair)
    if not ticker:
        return None
    try:
        import yfinance as yf
        raw = yf.download(ticker, period="10d", interval="1h",
                          progress=False, auto_adjust=True)
        if raw.empty:
            return None
        raw = raw.reset_index()
        # yfinance multi-level columns
        if isinstance(raw.columns, pd.MultiIndex):
            raw.columns = [c[0].lower() if c[1] == "" else c[0].lower() for c in raw.columns]
        else:
            raw.columns = [c.lower() for c in raw.columns]
        time_col = "datetime" if "datetime" in raw.columns else "date"
        raw = raw.rename(columns={time_col: "time"})
        raw["time"] = pd.to_datetime(raw["time"], utc=True)
        df = raw[["time", "open", "high", "low", "close"]].dropna().sort_values("time")
        df = df.tail(300).reset_index(drop=True)
        for col in ["open", "high", "low", "close"]:
            df[col] = pd.to_numeric(df[col], errors="coerce")
        df = df.dropna()
        return df if len(df) >= 50 else None
    except Exception as e:
        logger.debug("yfinance load failed %s: %s", pair, e)
        return None


def load_data(pair: str) -> Optional[pd.DataFrame]:
    df = _load_from_csv(pair)
    if df is None:
        df = _load_from_yfinance(pair)
    return df


# ── Signal generation ─────────────────────────────────────────────────────────

def _pip_value(pair: str, price: float) -> float:
    """Return the size of 1 pip for a given pair."""
    if pair in _JPY_PAIRS:
        return 0.01
    if "XAU" in pair:
        return 0.1
    if "XAG" in pair:
        return 0.001
    if "BTC" in pair or "ETH" in pair:
        return 1.0
    return 0.0001


def _compute_indicators(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["ema9"]   = _ema(df["close"], 9)
    df["ema15"]  = _ema(df["close"], 15)
    df["ema200"] = _ema(df["close"], 200)
    df["atr"]    = _atr(df, 14)
    df["adx"]    = _adx(df, 14)
    df["rsi"]    = _rsi(df["close"], 14)
    return df


def _score(adx: float, ema_aligned: bool, rsi: float, direction: str,
           sessions: list[str]) -> int:
    """Compute confidence score 0–100."""
    score = 0.0

    # ADX strength (0–35 pts)
    if adx >= 40:
        score += 35
    elif adx >= 30:
        score += 25
    elif adx >= 20:
        score += 15

    # EMA aligned (0–25 pts)
    if ema_aligned:
        score += 25

    # RSI position (0–20 pts)
    if direction == "BUY" and 40 <= rsi <= 65:
        score += 20
    elif direction == "BUY" and 30 <= rsi < 40:
        score += 10
    elif direction == "SELL" and 35 <= rsi <= 60:
        score += 20
    elif direction == "SELL" and 60 < rsi <= 70:
        score += 10

    # Session quality (0–20 pts)
    if "Overlap" in sessions:
        score += 20
    elif "London" in sessions or "NY" in sessions:
        score += 15
    elif "Asian" in sessions:
        score += 8

    return min(int(score), 100)


def generate_signal(pair: str, dt: Optional[datetime] = None) -> Optional[ForexSignal]:
    """Generate a single signal for one forex pair. Returns None if no setup."""
    df = load_data(pair)
    if df is None or len(df) < 50:
        logger.debug("No data for %s", pair)
        return None

    df = _compute_indicators(df)
    df = df.dropna(subset=["ema9", "ema15", "ema200", "atr", "adx", "rsi"])
    if len(df) < 20:
        return None

    row = df.iloc[-1]
    close   = float(row["close"])
    ema9    = float(row["ema9"])
    ema15   = float(row["ema15"])
    ema200  = float(row["ema200"])
    atr     = float(row["atr"])
    adx     = float(row["adx"])
    rsi     = float(row["rsi"])

    if atr == 0:
        return None

    # ADX filter
    if adx < 20:
        logger.debug("%s ADX=%.1f < 20, skip", pair, adx)
        return None

    # Session filter
    sessions = get_active_sessions(dt)
    if "Off-hours" in sessions:
        logger.debug("%s off-hours, skip", pair)
        return None

    # Determine direction from EMA alignment
    bull_ema = ema9 > ema15 > ema200
    bear_ema = ema9 < ema15 < ema200

    if not bull_ema and not bear_ema:
        logger.debug("%s EMAs not aligned, skip", pair)
        return None

    direction = "BUY" if bull_ema else "SELL"

    # RSI filter — don't buy overbought, don't sell oversold
    if direction == "BUY" and rsi > 70:
        return None
    if direction == "SELL" and rsi < 30:
        return None

    # ATR-based entry and levels
    entry = close
    if direction == "BUY":
        sl  = round(entry - 1.5 * atr, 6)
        tp1 = round(entry + 1.0 * atr, 6)
        tp2 = round(entry + 2.0 * atr, 6)
        tp3 = round(entry + 3.0 * atr, 6)
    else:
        sl  = round(entry + 1.5 * atr, 6)
        tp1 = round(entry - 1.0 * atr, 6)
        tp2 = round(entry - 2.0 * atr, 6)
        tp3 = round(entry - 3.0 * atr, 6)

    pip = _pip_value(pair, entry)
    pips_risk = round(abs(entry - sl) / pip, 1) if pip > 0 else 0.0

    confidence = _score(adx, True, rsi, direction, sessions)

    # Compute HTF bias from EMA200 vs close
    if close > ema200:
        htf_bias = "bullish"
    elif close < ema200:
        htf_bias = "bearish"
    else:
        htf_bias = "neutral"

    reason_parts = [
        f"ADX={adx:.1f}",
        f"EMA9={'>' if bull_ema else '<'}EMA15={'>' if bull_ema else '<'}EMA200",
        f"RSI={rsi:.1f}",
        f"Sessions={','.join(sessions)}",
    ]

    return ForexSignal(
        pair=pair,
        direction=direction,
        entry=round(entry, 6),
        stop_loss=sl,
        tp1=tp1,
        tp2=tp2,
        tp3=tp3,
        pips_risk=pips_risk,
        confidence=confidence,
        adx=round(adx, 2),
        atr=round(atr, 6),
        ema9=round(ema9, 6),
        ema15=round(ema15, 6),
        ema200=round(ema200, 6),
        rsi=round(rsi, 1),
        sessions=sessions,
        reason=" | ".join(reason_parts),
        timestamp=datetime.now(UTC).isoformat(),
        htf_bias=htf_bias,
    )


def scan_all_pairs(
    pairs: Optional[list[str]] = None,
    min_confidence: int = 55,
) -> list[dict]:
    """
    Scan multiple pairs and return signals above min_confidence.
    Always scans in a deterministic order; skips on data errors.
    """
    target = pairs or ALL_PAIRS
    now = datetime.now(UTC)
    results = []

    for pair in target:
        try:
            sig = generate_signal(pair, now)
            if sig and sig.confidence >= min_confidence:
                results.append(signal_to_dict(sig))
                logger.info("Signal: %s %s conf=%d%%", pair, sig.direction, sig.confidence)
        except Exception as e:
            logger.warning("Error scanning %s: %s", pair, e)

    results.sort(key=lambda s: s["confidence"], reverse=True)
    _save_signals(results)
    return results


def signal_to_dict(sig: ForexSignal) -> dict:
    d = asdict(sig)
    # Round all floats for cleaner JSON
    for k in ("entry", "stop_loss", "tp1", "tp2", "tp3", "atr",
               "ema9", "ema15", "ema200"):
        if k in d and isinstance(d[k], float):
            d[k] = round(d[k], 6)
    return d


def _save_signals(signals: list[dict]) -> None:
    try:
        _SIGNALS_FILE.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "updated_at": datetime.now(UTC).isoformat(),
            "count": len(signals),
            "signals": signals,
        }
        with open(_SIGNALS_FILE, "w") as f:
            json.dump(payload, f, indent=2, default=str)
        logger.info("Saved %d signals to %s", len(signals), _SIGNALS_FILE)
    except Exception as e:
        logger.error("Failed to save signals: %s", e)


def load_saved_signals() -> dict:
    try:
        if _SIGNALS_FILE.exists():
            with open(_SIGNALS_FILE) as f:
                return json.load(f)
    except Exception:
        pass
    return {"updated_at": None, "count": 0, "signals": []}


# ── OHLCV for chart endpoint ─────────────────────────────────────────────────

def get_ohlcv_for_chart(
    pair: str,
    interval: str = "1h",
    outputsize: int = 200,
) -> list[dict]:
    """
    Load OHLCV candles for a pair, suitable for the frontend chart.
    Returns list of {time (unix seconds), open, high, low, close, volume}.
    """
    df = None

    # Try TwelveData first if key available
    try:
        from app.domain.trading.twelve_data import _fetch_raw, INTERVAL_MAP, FOREX_PAIRS as TD_PAIRS
        td_symbol = TD_PAIRS.get(pair)
        td_interval = INTERVAL_MAP.get(interval, interval)
        if td_symbol:
            df_raw = _fetch_raw(td_symbol, td_interval, outputsize)
            if df_raw is not None and not df_raw.empty:
                df = df_raw.reset_index()
                df = df.rename(columns={"date": "time"})
                df["volume"] = df.get("volume", 0)
    except Exception as e:
        logger.debug("TwelveData chart load skipped: %s", e)

    # Fall back to local CSV
    if df is None:
        df_local = load_data(pair)
        if df_local is not None:
            df = df_local.rename(columns={"time": "time"})
            df["volume"] = 0

    # Fall back to yfinance
    if df is None:
        df = _load_from_yfinance(pair)
        if df is not None:
            df["volume"] = 0

    if df is None or df.empty:
        return []

    df = df.tail(outputsize)
    result = []
    for _, row in df.iterrows():
        try:
            t = row.get("time") or row.get("Datetime") or row.get("datetime")
            if hasattr(t, "timestamp"):
                ts = int(t.timestamp())
            else:
                ts = int(pd.Timestamp(t).timestamp())
            result.append({
                "time": ts,
                "open":  round(float(row["open"]),  6),
                "high":  round(float(row["high"]),  6),
                "low":   round(float(row["low"]),   6),
                "close": round(float(row["close"]), 6),
                "volume": int(row.get("volume", 0) or 0),
            })
        except Exception:
            continue
    return result
