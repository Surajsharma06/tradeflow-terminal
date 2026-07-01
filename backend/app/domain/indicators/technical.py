"""
Technical indicators module.

Pure-function implementations of common technical indicators using only
``pandas`` and ``numpy``.  Every function is designed to be called with a
``pd.DataFrame`` that has the standard OHLCV columns
(``open``, ``high``, ``low``, ``close``, ``volume``).

All functions gracefully handle empty DataFrames, insufficient history,
and NaN values by returning NaN-filled Series / DataFrames of the
correct length.
"""

from __future__ import annotations

import logging
from typing import Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# ── Column name aliases (lowercase) ─────────────────────────────────
_OPEN = "open"
_HIGH = "high"
_LOW = "low"
_CLOSE = "close"
_VOLUME = "volume"


# ═══════════════════════════════════════════════════════════════════════
# Moving Averages
# ═══════════════════════════════════════════════════════════════════════

def ema(series: pd.Series, period: int) -> pd.Series:
    """Exponential Moving Average.

    Parameters
    ----------
    series : pd.Series
        Price series (typically close prices).
    period : int
        Look-back window for the EMA.

    Returns
    -------
    pd.Series
        EMA values.  NaN for the first ``period - 1`` rows.
    """
    if series.empty or period <= 0:
        logger.warning("ema: empty series or invalid period=%s", period)
        return pd.Series(dtype=float, index=series.index)
    return series.ewm(span=period, adjust=False, min_periods=period).mean()


def sma(series: pd.Series, period: int) -> pd.Series:
    """Simple Moving Average.

    Parameters
    ----------
    series : pd.Series
        Price series.
    period : int
        Look-back window.

    Returns
    -------
    pd.Series
        SMA values.  NaN for the first ``period - 1`` rows.
    """
    if series.empty or period <= 0:
        logger.warning("sma: empty series or invalid period=%s", period)
        return pd.Series(dtype=float, index=series.index)
    return series.rolling(window=period, min_periods=period).mean()


# ═══════════════════════════════════════════════════════════════════════
# Momentum / Oscillators
# ═══════════════════════════════════════════════════════════════════════

def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    """Relative Strength Index (Wilder smoothing).

    Parameters
    ----------
    series : pd.Series
        Price series (close prices).
    period : int, default 14
        RSI look-back period.

    Returns
    -------
    pd.Series
        RSI in the range [0, 100].
    """
    if series.empty or len(series) < period + 1:
        logger.debug("rsi: insufficient data (need %d, got %d)", period + 1, len(series))
        return pd.Series(np.nan, index=series.index)

    delta = series.diff()
    gain = delta.clip(lower=0.0)
    loss = (-delta).clip(lower=0.0)

    avg_gain = gain.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()

    rs = avg_gain / avg_loss.replace(0, np.nan)
    result = 100.0 - (100.0 / (1.0 + rs))
    return result


def macd(
    series: pd.Series,
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
) -> tuple[pd.Series, pd.Series, pd.Series]:
    """Moving Average Convergence Divergence.

    Parameters
    ----------
    series : pd.Series
        Price series.
    fast : int, default 12
        Fast EMA period.
    slow : int, default 26
        Slow EMA period.
    signal : int, default 9
        Signal line EMA period.

    Returns
    -------
    tuple[pd.Series, pd.Series, pd.Series]
        ``(macd_line, signal_line, histogram)``
    """
    if series.empty or len(series) < slow:
        nan_s = pd.Series(np.nan, index=series.index)
        return nan_s.copy(), nan_s.copy(), nan_s.copy()

    fast_ema = ema(series, fast)
    slow_ema = ema(series, slow)
    macd_line = fast_ema - slow_ema
    signal_line = ema(macd_line, signal)
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram


def stochastic(
    df: pd.DataFrame,
    k_period: int = 14,
    d_period: int = 3,
) -> tuple[pd.Series, pd.Series]:
    """Stochastic Oscillator (%K and %D).

    Parameters
    ----------
    df : pd.DataFrame
        Must contain ``high``, ``low``, ``close`` columns.
    k_period : int, default 14
        Look-back for %K.
    d_period : int, default 3
        Smoothing period for %D (SMA of %K).

    Returns
    -------
    tuple[pd.Series, pd.Series]
        ``(percent_k, percent_d)``
    """
    if df.empty or len(df) < k_period:
        nan_s = pd.Series(np.nan, index=df.index)
        return nan_s.copy(), nan_s.copy()

    lowest_low = df[_LOW].rolling(window=k_period, min_periods=k_period).min()
    highest_high = df[_HIGH].rolling(window=k_period, min_periods=k_period).max()

    denom = highest_high - lowest_low
    denom = denom.replace(0, np.nan)

    percent_k = 100.0 * (df[_CLOSE] - lowest_low) / denom
    percent_d = percent_k.rolling(window=d_period, min_periods=d_period).mean()
    return percent_k, percent_d


# ═══════════════════════════════════════════════════════════════════════
# Volatility
# ═══════════════════════════════════════════════════════════════════════

def atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Average True Range.

    Parameters
    ----------
    df : pd.DataFrame
        Must contain ``high``, ``low``, ``close`` columns.
    period : int, default 14
        Smoothing period.

    Returns
    -------
    pd.Series
        ATR values.
    """
    if df.empty or len(df) < 2:
        return pd.Series(np.nan, index=df.index)

    high = df[_HIGH]
    low = df[_LOW]
    prev_close = df[_CLOSE].shift(1)

    tr = pd.concat(
        [high - low, (high - prev_close).abs(), (low - prev_close).abs()],
        axis=1,
    ).max(axis=1)

    return tr.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()


def bollinger_bands(
    series: pd.Series,
    period: int = 20,
    std_dev: float = 2.0,
) -> tuple[pd.Series, pd.Series, pd.Series, pd.Series, pd.Series]:
    """Bollinger Bands with bandwidth and %B.

    Parameters
    ----------
    series : pd.Series
        Price series (close).
    period : int, default 20
        SMA look-back.
    std_dev : float, default 2.0
        Standard-deviation multiplier.

    Returns
    -------
    tuple[pd.Series, pd.Series, pd.Series, pd.Series, pd.Series]
        ``(upper, middle, lower, bandwidth, percent_b)``
    """
    if series.empty or len(series) < period:
        nan_s = pd.Series(np.nan, index=series.index)
        return nan_s.copy(), nan_s.copy(), nan_s.copy(), nan_s.copy(), nan_s.copy()

    middle = sma(series, period)
    rolling_std = series.rolling(window=period, min_periods=period).std()

    upper = middle + std_dev * rolling_std
    lower = middle - std_dev * rolling_std

    band_width = middle.replace(0, np.nan)
    bandwidth = (upper - lower) / band_width

    denom = (upper - lower).replace(0, np.nan)
    percent_b = (series - lower) / denom

    return upper, middle, lower, bandwidth, percent_b


def supertrend(
    df: pd.DataFrame,
    period: int = 10,
    multiplier: float = 3.0,
) -> tuple[pd.Series, pd.Series]:
    """Supertrend indicator.

    Parameters
    ----------
    df : pd.DataFrame
        Must contain ``high``, ``low``, ``close``.
    period : int, default 10
        ATR period.
    multiplier : float, default 3.0
        ATR multiplier for the bands.

    Returns
    -------
    tuple[pd.Series, pd.Series]
        ``(supertrend_line, direction)``
        Direction: ``1`` = bullish (uptrend), ``-1`` = bearish (downtrend).
    """
    if df.empty or len(df) < period + 1:
        nan_s = pd.Series(np.nan, index=df.index)
        return nan_s.copy(), nan_s.copy()

    atr_vals = atr(df, period)
    hl2 = (df[_HIGH] + df[_LOW]) / 2.0

    upper_band = hl2 + multiplier * atr_vals
    lower_band = hl2 - multiplier * atr_vals

    st = pd.Series(np.nan, index=df.index, dtype=float)
    direction = pd.Series(1, index=df.index, dtype=int)

    # Initialise at the first valid ATR row
    first_valid = atr_vals.first_valid_index()
    if first_valid is None:
        return st, direction.astype(float)

    start = df.index.get_loc(first_valid)
    st.iloc[start] = upper_band.iloc[start]
    direction.iloc[start] = -1  # assume bearish until proven

    close = df[_CLOSE]

    for i in range(start + 1, len(df)):
        prev_ub = upper_band.iloc[i] if upper_band.iloc[i] < upper_band.iloc[i - 1] or close.iloc[i - 1] > upper_band.iloc[i - 1] else upper_band.iloc[i - 1]
        prev_lb = lower_band.iloc[i] if lower_band.iloc[i] > lower_band.iloc[i - 1] or close.iloc[i - 1] < lower_band.iloc[i - 1] else lower_band.iloc[i - 1]

        upper_band.iloc[i] = prev_ub
        lower_band.iloc[i] = prev_lb

        if direction.iloc[i - 1] == -1 and close.iloc[i] > upper_band.iloc[i]:
            direction.iloc[i] = 1
        elif direction.iloc[i - 1] == 1 and close.iloc[i] < lower_band.iloc[i]:
            direction.iloc[i] = -1
        else:
            direction.iloc[i] = direction.iloc[i - 1]

        st.iloc[i] = lower_band.iloc[i] if direction.iloc[i] == 1 else upper_band.iloc[i]

    return st, direction.astype(float)


# ═══════════════════════════════════════════════════════════════════════
# Trend
# ═══════════════════════════════════════════════════════════════════════

def adx(df: pd.DataFrame, period: int = 14) -> tuple[pd.Series, pd.Series, pd.Series]:
    """Average Directional Index with +DI and -DI.

    Parameters
    ----------
    df : pd.DataFrame
        Must contain ``high``, ``low``, ``close``.
    period : int, default 14
        Smoothing period.

    Returns
    -------
    tuple[pd.Series, pd.Series, pd.Series]
        ``(adx_values, plus_di, minus_di)``
    """
    if df.empty or len(df) < period + 1:
        nan_s = pd.Series(np.nan, index=df.index)
        return nan_s.copy(), nan_s.copy(), nan_s.copy()

    high = df[_HIGH]
    low = df[_LOW]

    plus_dm = high.diff()
    minus_dm = -low.diff()

    plus_dm = plus_dm.where((plus_dm > minus_dm) & (plus_dm > 0), 0.0)
    minus_dm = minus_dm.where((minus_dm > plus_dm) & (minus_dm > 0), 0.0)

    atr_vals = atr(df, period)

    smooth_plus = plus_dm.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()
    smooth_minus = minus_dm.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()

    plus_di = 100.0 * smooth_plus / atr_vals.replace(0, np.nan)
    minus_di = 100.0 * smooth_minus / atr_vals.replace(0, np.nan)

    dx = 100.0 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
    adx_values = dx.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()

    return adx_values, plus_di, minus_di


# ═══════════════════════════════════════════════════════════════════════
# Volume
# ═══════════════════════════════════════════════════════════════════════

def vwap(df: pd.DataFrame) -> pd.Series:
    """Volume Weighted Average Price (intra-day, cumulative).

    Parameters
    ----------
    df : pd.DataFrame
        Must contain ``high``, ``low``, ``close``, ``volume``.

    Returns
    -------
    pd.Series
        Cumulative VWAP.
    """
    if df.empty:
        return pd.Series(dtype=float, index=df.index)

    typical_price = (df[_HIGH] + df[_LOW] + df[_CLOSE]) / 3.0
    cum_tp_vol = (typical_price * df[_VOLUME]).cumsum()
    cum_vol = df[_VOLUME].cumsum().replace(0, np.nan)
    return cum_tp_vol / cum_vol


def volume_sma_ratio(df: pd.DataFrame, period: int = 20) -> pd.Series:
    """Current volume divided by its SMA.

    A value > 1 indicates above-average volume.

    Parameters
    ----------
    df : pd.DataFrame
        Must contain ``volume``.
    period : int, default 20
        SMA look-back.

    Returns
    -------
    pd.Series
        Volume / SMA(volume).
    """
    if df.empty or _VOLUME not in df.columns:
        return pd.Series(np.nan, index=df.index)

    vol_sma = sma(df[_VOLUME].astype(float), period)
    return df[_VOLUME] / vol_sma.replace(0, np.nan)


# ═══════════════════════════════════════════════════════════════════════
# Price-level checks
# ═══════════════════════════════════════════════════════════════════════

def is_near_52_week_high(df: pd.DataFrame, threshold: float = 0.02) -> pd.Series:
    """Check whether close is within *threshold* of its 252-day high.

    Parameters
    ----------
    df : pd.DataFrame
        Must contain ``close``.
    threshold : float, default 0.02
        Fractional distance from the 52-week high (2 %).

    Returns
    -------
    pd.Series[bool]
    """
    if df.empty or len(df) < 2:
        return pd.Series(False, index=df.index)

    period = min(252, len(df))
    high_252 = df[_CLOSE].rolling(window=period, min_periods=1).max()
    pct_from_high = (high_252 - df[_CLOSE]) / high_252.replace(0, np.nan)
    return pct_from_high <= threshold


def is_near_52_week_low(df: pd.DataFrame, threshold: float = 0.02) -> pd.Series:
    """Check whether close is within *threshold* of its 252-day low.

    Parameters
    ----------
    df : pd.DataFrame
        Must contain ``close``.
    threshold : float, default 0.02
        Fractional distance from the 52-week low (2 %).

    Returns
    -------
    pd.Series[bool]
    """
    if df.empty or len(df) < 2:
        return pd.Series(False, index=df.index)

    period = min(252, len(df))
    low_252 = df[_CLOSE].rolling(window=period, min_periods=1).min()
    pct_from_low = (df[_CLOSE] - low_252) / low_252.replace(0, np.nan)
    return pct_from_low <= threshold


# ═══════════════════════════════════════════════════════════════════════
# Composite
# ═══════════════════════════════════════════════════════════════════════

def calculate_all_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Compute all supported indicators and return an enriched DataFrame.

    The original columns are preserved; indicator columns are appended.
    If the input DataFrame is empty or has fewer than 2 rows an empty
    DataFrame with the expected schema is returned.

    Parameters
    ----------
    df : pd.DataFrame
        Standard OHLCV DataFrame.

    Returns
    -------
    pd.DataFrame
        Enriched DataFrame with indicator columns.
    """
    if df.empty or len(df) < 2:
        logger.warning("calculate_all_indicators: insufficient data (rows=%d)", len(df))
        return df.copy()

    result = df.copy()
    close = result[_CLOSE]

    # Moving averages
    for p in (9, 21, 50, 200):
        result[f"ema_{p}"] = ema(close, p)
        result[f"sma_{p}"] = sma(close, p)

    # RSI
    result["rsi_14"] = rsi(close, 14)

    # MACD
    result["macd_line"], result["macd_signal"], result["macd_histogram"] = macd(close)

    # Bollinger Bands
    (
        result["bb_upper"],
        result["bb_middle"],
        result["bb_lower"],
        result["bb_bandwidth"],
        result["bb_percent_b"],
    ) = bollinger_bands(close)

    # ATR
    result["atr_14"] = atr(result, 14)

    # Supertrend
    result["supertrend"], result["supertrend_direction"] = supertrend(result)

    # ADX
    result["adx_14"], result["plus_di"], result["minus_di"] = adx(result, 14)

    # VWAP
    if _VOLUME in result.columns:
        result["vwap"] = vwap(result)
        result["volume_sma_ratio"] = volume_sma_ratio(result)

    # Stochastic
    result["stoch_k"], result["stoch_d"] = stochastic(result)

    # 52-week proximity
    result["near_52w_high"] = is_near_52_week_high(result)
    result["near_52w_low"] = is_near_52_week_low(result)

    logger.info(
        "calculate_all_indicators: enriched %d rows with %d new columns",
        len(result),
        len(result.columns) - len(df.columns),
    )
    return result
