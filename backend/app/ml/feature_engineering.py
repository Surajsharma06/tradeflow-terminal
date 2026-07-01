"""
Feature engineering for ML trading models.

Creates 50+ features from raw OHLCV data including technical indicators,
return series, volatility metrics, volume analysis, price position
indicators, candlestick patterns, time-based features, lagged features,
and multiple target variables for supervised learning.
"""

import logging
from typing import Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class FeatureEngineer:
    """
    Transforms raw OHLCV data into a rich feature matrix for ML models.

    Features are grouped into categories:
    * **Technical indicators** — RSI, MACD, Bollinger, ATR, ADX, etc.
    * **Returns** — log returns at various horizons.
    * **Volatility** — rolling std, Parkinson, Garman-Klass.
    * **Volume** — OBV, VWAP, relative volume.
    * **Price position** — distance from MA, high/low, support/resistance.
    * **Candlestick patterns** — doji, hammer, engulfing, etc.
    * **Time** — day of week, month, quarter.
    * **Lagged** — lag-1 through lag-5 of key features.
    * **Targets** — forward returns for 1, 3, 5, 10 day horizons.
    """

    def __init__(self, include_targets: bool = True) -> None:
        """
        Args:
            include_targets: If ``True``, append forward-return target
                columns to the feature DataFrame.
        """
        self.include_targets = include_targets
        logger.info(
            "FeatureEngineer initialised (include_targets=%s)",
            include_targets,
        )

    # ═══════════════════════════════════════════════════════════════════
    # Public API
    # ═══════════════════════════════════════════════════════════════════

    def create_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Build the complete feature matrix from OHLCV data.

        Args:
            df: DataFrame with columns ``Open, High, Low, Close, Volume``
                (case-insensitive) indexed by datetime.

        Returns:
            DataFrame with all engineered features. Rows with ``NaN``
            values (from rolling windows) are **dropped**.
        """
        if df.empty:
            logger.warning("Empty DataFrame — returning empty features")
            return pd.DataFrame()

        # Normalise column names
        df = df.copy()
        df.columns = [c.lower() for c in df.columns]
        required = {"open", "high", "low", "close", "volume"}
        if not required.issubset(set(df.columns)):
            missing = required - set(df.columns)
            logger.error("Missing columns: %s", missing)
            return pd.DataFrame()

        logger.info("Building features for %d bars …", len(df))

        # Build feature groups
        df = self._add_return_features(df)
        df = self._add_volatility_features(df)
        df = self._add_technical_indicators(df)
        df = self._add_volume_features(df)
        df = self._add_price_position_features(df)
        df = self._add_candlestick_patterns(df)
        df = self._add_time_features(df)
        df = self._add_lagged_features(df)

        if self.include_targets:
            df = self._add_targets(df)

        # Drop rows with NaN from rolling calculations
        initial_len = len(df)
        df.dropna(inplace=True)
        logger.info(
            "Feature matrix: %d rows × %d cols (dropped %d NaN rows)",
            len(df), len(df.columns), initial_len - len(df),
        )
        return df

    def get_feature_names(self, df: pd.DataFrame) -> list[str]:
        """Return the list of feature column names (excluding targets)."""
        target_cols = {"target_1d", "target_3d", "target_5d", "target_10d",
                       "target_direction_1d", "target_direction_3d"}
        base_cols = {"open", "high", "low", "close", "volume"}
        return [c for c in df.columns if c not in target_cols and c not in base_cols]

    # ═══════════════════════════════════════════════════════════════════
    # Return features
    # ═══════════════════════════════════════════════════════════════════

    @staticmethod
    def _add_return_features(df: pd.DataFrame) -> pd.DataFrame:
        """Log and simple returns at multiple horizons."""
        df["log_return_1d"] = np.log(df["close"] / df["close"].shift(1))
        df["log_return_3d"] = np.log(df["close"] / df["close"].shift(3))
        df["log_return_5d"] = np.log(df["close"] / df["close"].shift(5))
        df["log_return_10d"] = np.log(df["close"] / df["close"].shift(10))
        df["simple_return_1d"] = df["close"].pct_change(1)
        df["simple_return_5d"] = df["close"].pct_change(5)
        df["cum_return_20d"] = df["close"].pct_change(20)
        return df

    # ═══════════════════════════════════════════════════════════════════
    # Volatility features
    # ═══════════════════════════════════════════════════════════════════

    @staticmethod
    def _add_volatility_features(df: pd.DataFrame) -> pd.DataFrame:
        """Rolling volatility, Parkinson, and Garman-Klass estimators."""
        # Rolling standard deviation of returns
        df["volatility_5d"] = df["close"].pct_change().rolling(5).std()
        df["volatility_10d"] = df["close"].pct_change().rolling(10).std()
        df["volatility_20d"] = df["close"].pct_change().rolling(20).std()
        df["volatility_60d"] = df["close"].pct_change().rolling(60).std()

        # Parkinson volatility (uses high/low)
        hl_ratio = np.log(df["high"] / df["low"])
        df["parkinson_vol_20d"] = np.sqrt(
            (1 / (4 * np.log(2))) * (hl_ratio ** 2).rolling(20).mean()
        )

        # Garman-Klass volatility
        log_hl = np.log(df["high"] / df["low"]) ** 2
        log_co = np.log(df["close"] / df["open"]) ** 2
        df["garman_klass_vol_20d"] = np.sqrt(
            (0.5 * log_hl - (2 * np.log(2) - 1) * log_co).rolling(20).mean()
        )

        # Volatility ratio (short / long)
        df["vol_ratio_5_20"] = df["volatility_5d"] / (df["volatility_20d"] + 1e-10)

        return df

    # ═══════════════════════════════════════════════════════════════════
    # Technical indicators
    # ═══════════════════════════════════════════════════════════════════

    @staticmethod
    def _add_technical_indicators(df: pd.DataFrame) -> pd.DataFrame:
        """RSI, MACD, Bollinger Bands, ATR, ADX, Stochastic, CCI, Williams %R."""
        close = df["close"]
        high = df["high"]
        low = df["low"]

        # ── RSI (14-period) ──────────────────────────────────────────
        delta = close.diff()
        gain = delta.where(delta > 0, 0.0).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0.0)).rolling(14).mean()
        rs = gain / (loss + 1e-10)
        df["rsi_14"] = 100 - (100 / (1 + rs))

        # RSI 7 and 21
        for period in (7, 21):
            g = delta.where(delta > 0, 0.0).rolling(period).mean()
            l_ = (-delta.where(delta < 0, 0.0)).rolling(period).mean()
            df[f"rsi_{period}"] = 100 - (100 / (1 + g / (l_ + 1e-10)))

        # ── MACD ─────────────────────────────────────────────────────
        ema_12 = close.ewm(span=12, adjust=False).mean()
        ema_26 = close.ewm(span=26, adjust=False).mean()
        df["macd"] = ema_12 - ema_26
        df["macd_signal"] = df["macd"].ewm(span=9, adjust=False).mean()
        df["macd_histogram"] = df["macd"] - df["macd_signal"]

        # ── Bollinger Bands ──────────────────────────────────────────
        sma_20 = close.rolling(20).mean()
        std_20 = close.rolling(20).std()
        df["bb_upper"] = sma_20 + 2 * std_20
        df["bb_lower"] = sma_20 - 2 * std_20
        df["bb_width"] = (df["bb_upper"] - df["bb_lower"]) / (sma_20 + 1e-10)
        df["bb_pct_b"] = (close - df["bb_lower"]) / (df["bb_upper"] - df["bb_lower"] + 1e-10)

        # ── Moving averages ──────────────────────────────────────────
        for period in (5, 10, 20, 50, 200):
            df[f"sma_{period}"] = close.rolling(period).mean()
            df[f"ema_{period}"] = close.ewm(span=period, adjust=False).mean()

        # ── ATR (14-period) ──────────────────────────────────────────
        tr1 = high - low
        tr2 = (high - close.shift(1)).abs()
        tr3 = (low - close.shift(1)).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        df["atr_14"] = tr.rolling(14).mean()
        df["atr_pct"] = df["atr_14"] / (close + 1e-10) * 100

        # ── ADX (14-period) ──────────────────────────────────────────
        plus_dm = (high - high.shift(1)).clip(lower=0)
        minus_dm = (low.shift(1) - low).clip(lower=0)
        plus_dm = plus_dm.where(plus_dm > minus_dm, 0)
        minus_dm = minus_dm.where(minus_dm > plus_dm, 0)
        atr_smooth = tr.rolling(14).mean()
        plus_di = 100 * (plus_dm.rolling(14).mean() / (atr_smooth + 1e-10))
        minus_di = 100 * (minus_dm.rolling(14).mean() / (atr_smooth + 1e-10))
        dx = 100 * ((plus_di - minus_di).abs() / (plus_di + minus_di + 1e-10))
        df["adx_14"] = dx.rolling(14).mean()
        df["plus_di"] = plus_di
        df["minus_di"] = minus_di

        # ── Stochastic Oscillator ────────────────────────────────────
        low_14 = low.rolling(14).min()
        high_14 = high.rolling(14).max()
        df["stoch_k"] = 100 * (close - low_14) / (high_14 - low_14 + 1e-10)
        df["stoch_d"] = df["stoch_k"].rolling(3).mean()

        # ── CCI ──────────────────────────────────────────────────────
        tp = (high + low + close) / 3
        sma_tp = tp.rolling(20).mean()
        mad = tp.rolling(20).apply(lambda x: np.abs(x - x.mean()).mean(), raw=True)
        df["cci_20"] = (tp - sma_tp) / (0.015 * mad + 1e-10)

        # ── Williams %R ──────────────────────────────────────────────
        df["williams_r"] = -100 * (high_14 - close) / (high_14 - low_14 + 1e-10)

        return df

    # ═══════════════════════════════════════════════════════════════════
    # Volume features
    # ═══════════════════════════════════════════════════════════════════

    @staticmethod
    def _add_volume_features(df: pd.DataFrame) -> pd.DataFrame:
        """OBV, VWAP proxy, relative volume, volume trend."""
        vol = df["volume"]
        close = df["close"]

        # On-Balance Volume
        obv_sign = np.sign(close.diff())
        df["obv"] = (vol * obv_sign).cumsum()

        # Volume moving averages
        df["volume_sma_10"] = vol.rolling(10).mean()
        df["volume_sma_20"] = vol.rolling(20).mean()

        # Relative volume (vs 20-day average)
        df["relative_volume"] = vol / (df["volume_sma_20"] + 1)

        # Volume rate of change
        df["volume_roc_5"] = vol.pct_change(5)

        # VWAP proxy (cumulative)
        cum_vol = vol.cumsum()
        cum_vp = (close * vol).cumsum()
        df["vwap"] = cum_vp / (cum_vol + 1)

        # Volume-price trend
        df["vpt"] = (vol * close.pct_change()).cumsum()

        # Money Flow Index (14-period)
        tp = (df["high"] + df["low"] + close) / 3
        mf = tp * vol
        pos_mf = mf.where(tp > tp.shift(1), 0.0).rolling(14).sum()
        neg_mf = mf.where(tp < tp.shift(1), 0.0).rolling(14).sum()
        df["mfi_14"] = 100 - (100 / (1 + pos_mf / (neg_mf + 1e-10)))

        return df

    # ═══════════════════════════════════════════════════════════════════
    # Price position features
    # ═══════════════════════════════════════════════════════════════════

    @staticmethod
    def _add_price_position_features(df: pd.DataFrame) -> pd.DataFrame:
        """Distance from MAs, 52-week high/low, support/resistance zones."""
        close = df["close"]

        # Distance from moving averages (%)
        for period in (20, 50, 200):
            sma = close.rolling(period).mean()
            df[f"dist_sma_{period}_pct"] = (close - sma) / (sma + 1e-10) * 100

        # Distance from 52-week (252 trading days) high/low
        high_252 = df["high"].rolling(252, min_periods=50).max()
        low_252 = df["low"].rolling(252, min_periods=50).min()
        df["dist_52w_high_pct"] = (close - high_252) / (high_252 + 1e-10) * 100
        df["dist_52w_low_pct"] = (close - low_252) / (low_252 + 1e-10) * 100

        # Price range position (where is price within recent range)
        high_20 = df["high"].rolling(20).max()
        low_20 = df["low"].rolling(20).min()
        df["price_position_20d"] = (close - low_20) / (high_20 - low_20 + 1e-10)

        # MA crossover signals
        df["ema_cross_5_20"] = (
            df.get("ema_5", close.ewm(span=5).mean())
            - df.get("ema_20", close.ewm(span=20).mean())
        )

        return df

    # ═══════════════════════════════════════════════════════════════════
    # Candlestick patterns
    # ═══════════════════════════════════════════════════════════════════

    @staticmethod
    def _add_candlestick_patterns(df: pd.DataFrame) -> pd.DataFrame:
        """Detect common candlestick patterns (binary flags)."""
        o, h, l, c = df["open"], df["high"], df["low"], df["close"]
        body = (c - o).abs()
        full_range = h - l + 1e-10

        # Doji: tiny body relative to range
        df["pattern_doji"] = (body / full_range < 0.1).astype(int)

        # Hammer: small body in upper third, long lower shadow
        lower_shadow = pd.concat([o, c], axis=1).min(axis=1) - l
        upper_shadow = h - pd.concat([o, c], axis=1).max(axis=1)
        df["pattern_hammer"] = (
            (lower_shadow > 2 * body) & (upper_shadow < body * 0.5)
        ).astype(int)

        # Shooting star (inverted hammer at top)
        df["pattern_shooting_star"] = (
            (upper_shadow > 2 * body) & (lower_shadow < body * 0.5)
        ).astype(int)

        # Bullish engulfing
        prev_bearish = c.shift(1) < o.shift(1)
        curr_bullish = c > o
        engulfing = curr_bullish & prev_bearish & (c > o.shift(1)) & (o < c.shift(1))
        df["pattern_bull_engulfing"] = engulfing.astype(int)

        # Bearish engulfing
        prev_bullish = c.shift(1) > o.shift(1)
        curr_bearish = c < o
        bear_engulf = curr_bearish & prev_bullish & (o > c.shift(1)) & (c < o.shift(1))
        df["pattern_bear_engulfing"] = bear_engulf.astype(int)

        # Marubozu (strong candle, minimal shadows)
        df["pattern_marubozu"] = (body / full_range > 0.9).astype(int)

        return df

    # ═══════════════════════════════════════════════════════════════════
    # Time features
    # ═══════════════════════════════════════════════════════════════════

    @staticmethod
    def _add_time_features(df: pd.DataFrame) -> pd.DataFrame:
        """Calendar-based features including forex market sessions (UTC)."""
        if not isinstance(df.index, pd.DatetimeIndex):
            try:
                df.index = pd.to_datetime(df.index)
            except Exception:
                logger.warning("Cannot parse index as datetime — skipping time features")
                return df

        idx = df.index
        if idx.tz is None:
            idx = idx.tz_localize("UTC")
        else:
            idx = idx.tz_convert("UTC")
        hour = idx.hour
        dow  = idx.dayofweek

        df["day_of_week"] = dow
        df["month"] = idx.month
        df["quarter"] = idx.quarter
        df["is_month_start"] = idx.is_month_start.astype(int)
        df["is_month_end"] = idx.is_month_end.astype(int)
        df["is_quarter_end"] = idx.is_quarter_end.astype(int)

        # Sine/cosine encoding for cyclical features
        df["day_sin"] = np.sin(2 * np.pi * dow / 5)
        df["day_cos"] = np.cos(2 * np.pi * dow / 5)
        df["month_sin"] = np.sin(2 * np.pi * idx.month / 12)
        df["month_cos"] = np.cos(2 * np.pi * idx.month / 12)

        # Forex session flags (UTC) — most predictable during overlaps
        df["sess_tokyo"]   = ((hour >= 0)  & (hour < 9)).astype(int)
        df["sess_london"]  = ((hour >= 7)  & (hour < 16)).astype(int)
        df["sess_ny"]      = ((hour >= 13) & (hour < 22)).astype(int)
        df["sess_overlap"] = ((hour >= 13) & (hour < 16)).astype(int)  # London+NY overlap
        df["sess_dead"]    = ((hour >= 22) | (hour < 0)).astype(int)   # low-activity window

        # Day-of-week quality flags (Mon open and Fri close are noisiest)
        df["dow_monday"]  = (dow == 0).astype(int)
        df["dow_friday"]  = (dow == 4).astype(int)
        df["dow_midweek"] = ((dow >= 1) & (dow <= 3)).astype(int)

        return df

    # ═══════════════════════════════════════════════════════════════════
    # Lagged features
    # ═══════════════════════════════════════════════════════════════════

    @staticmethod
    def _add_lagged_features(df: pd.DataFrame) -> pd.DataFrame:
        """Lag-1 through lag-5 of key features for autoregressive signal."""
        lag_cols = ["log_return_1d", "rsi_14", "macd_histogram", "relative_volume"]
        for col in lag_cols:
            if col not in df.columns:
                continue
            for lag in range(1, 6):
                df[f"{col}_lag{lag}"] = df[col].shift(lag)
        return df

    # ═══════════════════════════════════════════════════════════════════
    # Target variables
    # ═══════════════════════════════════════════════════════════════════

    @staticmethod
    def _add_targets(df: pd.DataFrame) -> pd.DataFrame:
        """Forward returns, directional labels, and spread-aware targets."""
        close = df["close"]

        # Forward returns (regression targets)
        for horizon in (1, 3, 5, 10):
            df[f"target_{horizon}d"] = close.shift(-horizon) / close - 1

        # Simple directional labels (1=up, 0=down)
        df["target_direction_1d"] = (close.shift(-1) > close).astype(int)
        df["target_direction_3d"] = (close.shift(-3) > close).astype(int)

        # Spread-aware target: only profitable moves count as signals.
        # Typical forex spread ~0.02% of price; target must exceed 2x spread.
        typical_spread_pct = 0.0002
        fwd_3 = close.shift(-3) - close
        min_move = close * typical_spread_pct * 2
        df["target_profitable_buy"]  = (fwd_3 >  min_move).astype(int)
        df["target_profitable_sell"] = (fwd_3 < -min_move).astype(int)

        # ADX-based trend quality flag (1 = trending, safe to trade)
        if "adx_14" in df.columns:
            df["is_trending"] = (df["adx_14"] >= 25).astype(int)

        return df
