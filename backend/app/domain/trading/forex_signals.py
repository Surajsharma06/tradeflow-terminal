"""
Forex Signal Engine — Free, No Paid API Required.

Uses yfinance (free) to fetch forex OHLCV data and generates
BUY/SELL signals with Entry, Stop Loss, Target, and Session info.

Supported Pairs:
  EUR/USD, GBP/USD, USD/JPY, AUD/USD, USD/CAD, NZD/USD,
  GBP/JPY, EUR/GBP, USD/CHF, USD/INR, EUR/INR, GBP/INR

Sessions (IST):
  Tokyo   → 05:30 AM – 09:30 AM
  London  → 01:30 PM – 05:30 PM   ← Most volatile
  New York→ 06:30 PM – 11:30 PM
  Overlap → 06:30 PM – 09:00 PM   ← BEST TIME
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, time
from typing import Optional
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)
IST = ZoneInfo("Asia/Kolkata")
UTC = ZoneInfo("UTC")


# ── Forex session windows (IST) ──────────────────────────────────────────

FOREX_SESSIONS: dict[str, dict] = {
    "Sydney": {
        "start": time(3, 30),
        "end": time(8, 30),
        "pairs": ["AUD/USD", "NZD/USD"],
        "emoji": "🦘",
    },
    "Tokyo": {
        "start": time(5, 30),
        "end": time(9, 30),
        "pairs": ["USD/JPY", "GBP/JPY", "AUD/USD"],
        "emoji": "🗼",
    },
    "London": {
        "start": time(13, 30),
        "end": time(17, 30),
        "pairs": ["EUR/USD", "GBP/USD", "EUR/GBP", "USD/CHF"],
        "emoji": "🇬🇧",
        "best": True,
    },
    "New York": {
        "start": time(18, 30),
        "end": time(23, 30),
        "pairs": ["EUR/USD", "USD/CAD", "USD/JPY", "GBP/USD"],
        "emoji": "🗽",
    },
    "London+NY Overlap": {
        "start": time(18, 30),
        "end": time(21, 0),
        "pairs": ["EUR/USD", "GBP/USD", "USD/JPY"],
        "emoji": "🔥",
        "best": True,
    },
}

# yfinance ticker mapping (append =X for forex)
PAIR_TO_TICKER: dict[str, str] = {
    "EUR/USD": "EURUSD=X",
    "GBP/USD": "GBPUSD=X",
    "USD/JPY": "JPY=X",
    "AUD/USD": "AUDUSD=X",
    "USD/CAD": "CAD=X",
    "NZD/USD": "NZDUSD=X",
    "USD/CHF": "CHF=X",
    "GBP/JPY": "GBPJPY=X",
    "EUR/GBP": "EURGBP=X",
    "EUR/JPY": "EURJPY=X",
    "USD/INR": "INR=X",
    "EUR/INR": "EURINR=X",
    "GBP/INR": "GBPINR=X",
}

# Pip sizes
PIP_SIZE: dict[str, float] = {
    "USD/JPY": 0.01,
    "GBP/JPY": 0.01,
    "EUR/JPY": 0.01,
    "USD/INR": 0.01,
    "EUR/INR": 0.01,
    "GBP/INR": 0.01,
}


@dataclass
class ForexSignal:
    """A single forex trading signal."""
    pair: str
    direction: str            # BUY or SELL
    entry: float
    stop_loss: float
    target_1: float           # TP1 — conservative
    target_2: float           # TP2 — moderate
    target_3: float           # TP3 — aggressive
    pips_risk: float
    pips_reward: float
    risk_reward: float
    confidence: float         # 0–100
    strategy: str
    session: str
    best_session: bool
    timeframe: str
    timestamp: str = field(
        default_factory=lambda: datetime.now(IST).strftime("%d %b %Y, %I:%M %p IST")
    )
    notes: str = ""


def _pip_size(pair: str) -> float:
    return PIP_SIZE.get(pair, 0.0001)


def _pips(price_diff: float, pair: str) -> float:
    return round(abs(price_diff) / _pip_size(pair), 1)


def get_active_session() -> tuple[str, bool]:
    """Return current active forex session name and whether it's the best time."""
    now_ist = datetime.now(IST).time()
    active = "Off-Hours"
    is_best = False
    for name, info in FOREX_SESSIONS.items():
        if info["start"] <= now_ist <= info["end"]:
            active = name
            is_best = info.get("best", False)
    return active, is_best


def fetch_forex_data(pair: str, period: str = "60d", interval: str = "1d") -> Optional[pd.DataFrame]:
    """
    Fetch OHLCV data for a forex pair using yfinance (free, no API key).

    Args:
        pair: e.g. "EUR/USD"
        period: "60d", "6mo", "1y"
        interval: "1d", "1h", "15m"

    Returns:
        DataFrame with columns [open, high, low, close, volume] or None
    """
    try:
        import yfinance as yf
    except ImportError:
        logger.error("yfinance not installed. Run: pip install yfinance")
        return None

    ticker = PAIR_TO_TICKER.get(pair)
    if not ticker:
        logger.warning("Unknown forex pair: %s", pair)
        return None

    try:
        df = yf.download(ticker, period=period, interval=interval,
                         auto_adjust=True, progress=False)
        if df.empty:
            logger.warning("No data for %s", pair)
            return None

        # Handle MultiIndex columns (newer yfinance versions)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = [col[0].lower() for col in df.columns]
        else:
            df.columns = [c.lower() for c in df.columns]

        df.index.name = "date"

        # Select OHLCV columns (handle missing volume in forex)
        cols_needed = ["open", "high", "low", "close"]
        for col in cols_needed:
            if col not in df.columns:
                logger.warning("Missing column '%s' for %s", col, pair)
                return None

        if "volume" not in df.columns:
            df["volume"] = 0  # forex has no volume, use 0

        df = df[["open", "high", "low", "close", "volume"]].dropna(subset=cols_needed)
        logger.info("Fetched %d bars for %s (%s)", len(df), pair, interval)
        return df
    except Exception as e:
        logger.error("yfinance fetch failed for %s: %s", pair, e)
        return None


# ── Indicator helpers ─────────────────────────────────────────────────────

def _ema(series: pd.Series, n: int) -> pd.Series:
    return series.ewm(span=n, adjust=False).mean()


def _rsi(series: pd.Series, n: int = 14) -> pd.Series:
    delta = series.diff()
    gain  = delta.clip(lower=0).rolling(n).mean()
    loss  = (-delta.clip(upper=0)).rolling(n).mean()
    rs    = gain / loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def _macd(series: pd.Series):
    ema12 = _ema(series, 12)
    ema26 = _ema(series, 26)
    line  = ema12 - ema26
    signal = _ema(line, 9)
    hist   = line - signal
    return line, signal, hist


def _atr(df: pd.DataFrame, n: int = 14) -> pd.Series:
    hl  = df["high"] - df["low"]
    hc  = (df["high"] - df["close"].shift()).abs()
    lc  = (df["low"]  - df["close"].shift()).abs()
    tr  = pd.concat([hl, hc, lc], axis=1).max(axis=1)
    return tr.rolling(n).mean()


def _bollinger(series: pd.Series, n: int = 20, k: float = 2.0):
    mid   = series.rolling(n).mean()
    std   = series.rolling(n).std()
    upper = mid + k * std
    lower = mid - k * std
    bw    = (upper - lower) / mid
    return upper, mid, lower, bw


def _stoch(df: pd.DataFrame, k: int = 14, d: int = 3):
    low_min  = df["low"].rolling(k).min()
    high_max = df["high"].rolling(k).max()
    pct_k    = 100 * (df["close"] - low_min) / (high_max - low_min).replace(0, np.nan)
    pct_d    = pct_k.rolling(d).mean()
    return pct_k, pct_d


def _adx(df: pd.DataFrame, n: int = 14) -> pd.Series:
    up   = df["high"].diff()
    down = -df["low"].diff()
    dm_p = up.where((up > down) & (up > 0), 0.0)
    dm_m = down.where((down > up) & (down > 0), 0.0)
    atr  = _atr(df, n)
    di_p = 100 * dm_p.rolling(n).mean() / atr.replace(0, np.nan)
    di_m = 100 * dm_m.rolling(n).mean() / atr.replace(0, np.nan)
    dx   = (100 * (di_p - di_m).abs() / (di_p + di_m).replace(0, np.nan))
    return dx.ewm(span=n, adjust=False).mean()


def _support_resistance(df: pd.DataFrame, lookback: int = 20) -> tuple[float, float]:
    """Simple swing high/low based S/R."""
    recent = df.tail(lookback)
    support    = float(recent["low"].min())
    resistance = float(recent["high"].max())
    return support, resistance


# ── Signal generators ─────────────────────────────────────────────────────

def _signal_trend(df: pd.DataFrame, pair: str) -> Optional[ForexSignal]:
    """EMA 9/21/50 trend + MACD + ADX."""
    if len(df) < 55:
        return None

    close = df["close"]
    ema9  = _ema(close, 9)
    ema21 = _ema(close, 21)
    ema50 = _ema(close, 50)
    macd_line, macd_sig, _ = _macd(close)
    adx = _adx(df)
    atr = _atr(df)

    e9  = ema9.iloc[-1];  e9_prev  = ema9.iloc[-2]
    e21 = ema21.iloc[-1]; e21_prev = ema21.iloc[-2]
    e50 = ema50.iloc[-1]
    ml  = macd_line.iloc[-1]; ms = macd_sig.iloc[-1]
    adx_val = adx.iloc[-1]
    atr_val = atr.iloc[-1]
    price = float(close.iloc[-1])

    if np.isnan(adx_val) or adx_val < 20:
        return None

    # BUY: EMA crossover up + MACD bullish + price above EMA50
    cross_up   = e9 > e21 and e9_prev <= e21_prev
    cross_down = e9 < e21 and e9_prev >= e21_prev

    pip = _pip_size(pair)

    if cross_up and ml > ms and price > e50:
        sl   = round(price - 1.5 * atr_val, 5)
        tp1  = round(price + 1.0 * atr_val, 5)
        tp2  = round(price + 2.0 * atr_val, 5)
        tp3  = round(price + 3.0 * atr_val, 5)
        conf = min(60 + adx_val * 0.5, 92)
        return ForexSignal(
            pair=pair, direction="BUY", entry=price,
            stop_loss=sl, target_1=tp1, target_2=tp2, target_3=tp3,
            pips_risk=_pips(price - sl, pair),
            pips_reward=_pips(tp2 - price, pair),
            risk_reward=round((tp2 - price) / (price - sl), 2),
            confidence=round(conf, 1), strategy="EMA Trend + MACD",
            session="", best_session=False, timeframe="Daily",
            notes=f"ADX={adx_val:.1f}, EMA9>{ema21.iloc[-1]:.5f}",
        )

    if cross_down and ml < ms and price < e50:
        sl   = round(price + 1.5 * atr_val, 5)
        tp1  = round(price - 1.0 * atr_val, 5)
        tp2  = round(price - 2.0 * atr_val, 5)
        tp3  = round(price - 3.0 * atr_val, 5)
        conf = min(60 + adx_val * 0.5, 92)
        return ForexSignal(
            pair=pair, direction="SELL", entry=price,
            stop_loss=sl, target_1=tp1, target_2=tp2, target_3=tp3,
            pips_risk=_pips(sl - price, pair),
            pips_reward=_pips(price - tp2, pair),
            risk_reward=round((price - tp2) / (sl - price), 2),
            confidence=round(conf, 1), strategy="EMA Trend + MACD",
            session="", best_session=False, timeframe="Daily",
            notes=f"ADX={adx_val:.1f}, MACD bearish crossover",
        )

    return None


def _signal_mean_reversion(df: pd.DataFrame, pair: str) -> Optional[ForexSignal]:
    """Bollinger Band + RSI + Stochastic mean reversion."""
    if len(df) < 25:
        return None

    close = df["close"]
    upper, mid, lower, bw = _bollinger(close)
    rsi   = _rsi(close)
    k, d  = _stoch(df)
    atr   = _atr(df)

    price = float(close.iloc[-1])
    lo    = float(lower.iloc[-1])
    hi    = float(upper.iloc[-1])
    mi    = float(mid.iloc[-1])
    r     = float(rsi.iloc[-1])
    k_val = float(k.iloc[-1])
    atr_v = float(atr.iloc[-1])

    if any(np.isnan(x) for x in [lo, hi, r, k_val, atr_v]):
        return None

    # BUY: below lower BB + RSI oversold + Stoch oversold
    if price <= lo * 1.002 and r < 35 and k_val < 25:
        sl   = round(lo - atr_v, 5)
        tp1  = round(mi, 5)
        tp2  = round(mi + 0.5 * (hi - mi), 5)
        tp3  = round(hi, 5)
        conf = 65 + (30 - r) * 0.5 + (25 - k_val) * 0.3
        return ForexSignal(
            pair=pair, direction="BUY", entry=price,
            stop_loss=sl, target_1=tp1, target_2=tp2, target_3=tp3,
            pips_risk=_pips(price - sl, pair),
            pips_reward=_pips(tp2 - price, pair),
            risk_reward=round((tp2 - price) / (price - sl), 2) if price > sl else 0,
            confidence=round(min(conf, 90), 1), strategy="Bollinger + RSI Reversal",
            session="", best_session=False, timeframe="Daily",
            notes=f"RSI={r:.1f}, Stoch={k_val:.1f}, below lower BB",
        )

    # SELL: above upper BB + RSI overbought + Stoch overbought
    if price >= hi * 0.998 and r > 65 and k_val > 75:
        sl   = round(hi + atr_v, 5)
        tp1  = round(mi, 5)
        tp2  = round(mi - 0.5 * (mi - lo), 5)
        tp3  = round(lo, 5)
        conf = 65 + (r - 70) * 0.5 + (k_val - 75) * 0.3
        return ForexSignal(
            pair=pair, direction="SELL", entry=price,
            stop_loss=sl, target_1=tp1, target_2=tp2, target_3=tp3,
            pips_risk=_pips(sl - price, pair),
            pips_reward=_pips(price - tp2, pair),
            risk_reward=round((price - tp2) / (sl - price), 2) if sl > price else 0,
            confidence=round(min(conf, 90), 1), strategy="Bollinger + RSI Reversal",
            session="", best_session=False, timeframe="Daily",
            notes=f"RSI={r:.1f}, Stoch={k_val:.1f}, above upper BB",
        )

    return None


def _signal_breakout(df: pd.DataFrame, pair: str) -> Optional[ForexSignal]:
    """Support/Resistance breakout with volume confirmation."""
    if len(df) < 30:
        return None

    close = df["close"]
    support, resistance = _support_resistance(df, lookback=20)
    atr   = _atr(df)
    rsi   = _rsi(close)

    price = float(close.iloc[-1])
    prev  = float(close.iloc[-2])
    atr_v = float(atr.iloc[-1])
    r     = float(rsi.iloc[-1])

    if np.isnan(atr_v) or np.isnan(r):
        return None

    pip = _pip_size(pair)

    # BUY breakout: close above resistance with momentum
    if prev < resistance and price > resistance * 1.001 and 45 < r < 70:
        sl   = round(resistance - atr_v * 0.5, 5)
        tp1  = round(price + atr_v, 5)
        tp2  = round(price + 2 * atr_v, 5)
        tp3  = round(price + 3 * atr_v, 5)
        return ForexSignal(
            pair=pair, direction="BUY", entry=price,
            stop_loss=sl, target_1=tp1, target_2=tp2, target_3=tp3,
            pips_risk=_pips(price - sl, pair),
            pips_reward=_pips(tp2 - price, pair),
            risk_reward=round((tp2 - price) / (price - sl), 2) if price > sl else 0,
            confidence=72.0, strategy="Resistance Breakout",
            session="", best_session=False, timeframe="Daily",
            notes=f"Broke ₹{resistance:.5f} resistance, RSI={r:.1f}",
        )

    # SELL breakout: close below support
    if prev > support and price < support * 0.999 and 30 < r < 55:
        sl   = round(support + atr_v * 0.5, 5)
        tp1  = round(price - atr_v, 5)
        tp2  = round(price - 2 * atr_v, 5)
        tp3  = round(price - 3 * atr_v, 5)
        return ForexSignal(
            pair=pair, direction="SELL", entry=price,
            stop_loss=sl, target_1=tp1, target_2=tp2, target_3=tp3,
            pips_risk=_pips(sl - price, pair),
            pips_reward=_pips(price - tp2, pair),
            risk_reward=round((price - tp2) / (sl - price), 2) if sl > price else 0,
            confidence=70.0, strategy="Support Breakdown",
            session="", best_session=False, timeframe="Daily",
            notes=f"Broke {support:.5f} support, RSI={r:.1f}",
        )

    return None


# ── Main scanner ──────────────────────────────────────────────────────────

def scan_forex_signals(
    pairs: Optional[list[str]] = None,
    min_confidence: float = 65.0,
    timeframe: str = "1d",
    period: str = "90d",
) -> list[ForexSignal]:
    """
    Scan all forex pairs and return signals above min_confidence.

    Args:
        pairs: List of pairs to scan. Defaults to all major pairs.
        min_confidence: Minimum confidence score (0–100).
        timeframe: "1d", "1h", "15m"
        period: yfinance period string.

    Returns:
        List of ForexSignal objects sorted by confidence descending.
    """
    if pairs is None:
        pairs = list(PAIR_TO_TICKER.keys())

    session_name, is_best = get_active_session()
    signals: list[ForexSignal] = []

    for pair in pairs:
        try:
            df = fetch_forex_data(pair, period=period, interval=timeframe)
            if df is None or len(df) < 30:
                continue

            # Run all strategies
            candidates = [
                _signal_trend(df, pair),
                _signal_mean_reversion(df, pair),
                _signal_breakout(df, pair),
            ]

            for sig in candidates:
                if sig is None:
                    continue
                if sig.confidence < min_confidence:
                    continue

                # Attach session info
                sig.session     = session_name
                sig.best_session = is_best

                # Boost confidence during best sessions
                if is_best:
                    sig.confidence = min(sig.confidence + 5, 99)
                    sig.notes += f" | 🔥 {session_name} (Best time!)"

                signals.append(sig)
                logger.info(
                    "Forex signal: %s %s @ %.5f | SL %.5f | TP2 %.5f | conf %.1f%%",
                    sig.direction, pair, sig.entry, sig.stop_loss,
                    sig.target_2, sig.confidence,
                )

        except Exception as e:
            logger.error("Error scanning %s: %s", pair, e)

    # Sort by confidence
    signals.sort(key=lambda s: s.confidence, reverse=True)
    return signals


# ── Telegram formatter ────────────────────────────────────────────────────

def format_signal_for_telegram(sig: ForexSignal) -> str:
    """Format a ForexSignal as a rich Telegram HTML message."""
    dir_emoji  = "🟢" if sig.direction == "BUY" else "🔴"
    sess_badge = f"🔥 <b>{sig.session}</b> (BEST TIME!)" if sig.best_session else f"📍 {sig.session}"
    conf_bar   = "🔥" * int(sig.confidence // 20)

    # Determine pip symbol
    is_jpy = "JPY" in sig.pair or "INR" in sig.pair

    return (
        f"{dir_emoji} <b>{sig.direction} — {sig.pair}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📊 <b>Strategy:</b> {sig.strategy}\n"
        f"⏱ <b>Timeframe:</b> {sig.timeframe}\n"
        f"🕐 <b>Time:</b> {sig.timestamp}\n"
        f"📍 <b>Session:</b> {sess_badge}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"▶️ <b>Entry:</b>   {sig.entry:.5f}\n"
        f"🛑 <b>Stop Loss:</b> {sig.stop_loss:.5f}  "
        f"<i>({sig.pips_risk:.0f} pips risk)</i>\n"
        f"🎯 <b>TP1:</b>    {sig.target_1:.5f}  <i>(conservative)</i>\n"
        f"🎯 <b>TP2:</b>    {sig.target_2:.5f}  <i>(moderate)</i>\n"
        f"🎯 <b>TP3:</b>    {sig.target_3:.5f}  <i>(aggressive)</i>\n"
        f"📐 <b>Risk:Reward:</b> 1:{sig.risk_reward:.1f}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🤖 <b>AI Confidence:</b> {sig.confidence:.1f}%  {conf_bar}\n"
        f"💡 <b>Notes:</b> <i>{sig.notes}</i>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"⚠️ <i>Manual execution — Open your broker app</i>"
    )


# ── Quick test (run directly) ─────────────────────────────────────────────
if __name__ == "__main__":
    import asyncio
    logging.basicConfig(level=logging.INFO)

    print("\n🔍 Scanning all forex pairs...\n")
    results = scan_forex_signals(min_confidence=60.0)

    if not results:
        print("❌ No signals right now. Try again during London/NY session.")
    else:
        for s in results:
            print(format_signal_for_telegram(s))
            print()
