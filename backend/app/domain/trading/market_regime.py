"""
Market regime detection engine.

Classifies the current market state into one of five regimes using
ADX strength, EMA slope analysis, and VIX-level overrides.  Each
regime maps to a set of suitable strategies and a position-size
adjustment factor.
"""

from __future__ import annotations

import logging
from enum import Enum
from typing import Optional

import numpy as np
import pandas as pd

from app.domain.indicators.technical import adx, ema

logger = logging.getLogger(__name__)


class MarketRegime(str, Enum):
    """Detected market regime states."""

    BULL_TRENDING = "BULL_TRENDING"
    BEAR_TRENDING = "BEAR_TRENDING"
    SIDEWAYS = "SIDEWAYS"
    HIGH_VOLATILITY = "HIGH_VOLATILITY"
    LOW_VOLATILITY = "LOW_VOLATILITY"


# ── Strategy mapping per regime ─────────────────────────────────────

_REGIME_STRATEGIES: dict[MarketRegime, list[str]] = {
    MarketRegime.BULL_TRENDING: [
        "trend_following",
        "momentum",
        "breakout",
        "swing",
        "ema_crossover",
    ],
    MarketRegime.BEAR_TRENDING: [
        "mean_reversion",
        "pair_trading",
        "support_resistance",
    ],
    MarketRegime.SIDEWAYS: [
        "mean_reversion",
        "bollinger_squeeze",
        "scalping",
        "support_resistance",
        "pair_trading",
    ],
    MarketRegime.HIGH_VOLATILITY: [
        "scalping",
        "mean_reversion",
    ],
    MarketRegime.LOW_VOLATILITY: [
        "trend_following",
        "momentum",
        "breakout",
        "swing",
    ],
}

_REGIME_SIZE_ADJUSTMENT: dict[MarketRegime, float] = {
    MarketRegime.BULL_TRENDING: 1.0,
    MarketRegime.BEAR_TRENDING: 0.5,
    MarketRegime.SIDEWAYS: 0.7,
    MarketRegime.HIGH_VOLATILITY: 0.3,
    MarketRegime.LOW_VOLATILITY: 1.2,
}


class MarketRegimeDetector:
    """Detect the prevailing market regime from price data and optional
    VIX reading.

    Detection logic
    ---------------
    1. **VIX overrides** are checked first:
       - VIX > 25 → ``HIGH_VOLATILITY`` (extreme fear)
       - VIX < 12 → ``LOW_VOLATILITY`` (complacency)
    2. Otherwise, classify by ADX and EMA(200) position:
       - ADX > 25 *and* price > EMA 200 → ``BULL_TRENDING``
       - ADX > 25 *and* price < EMA 200 → ``BEAR_TRENDING``
       - ADX < 20 → ``SIDEWAYS``
       - Remaining → ``SIDEWAYS`` (default fallback)
    """

    def __init__(self) -> None:
        self._last_regime: Optional[MarketRegime] = None

    # ── Core detection ───────────────────────────────────────────────

    def detect_regime(
        self,
        df: pd.DataFrame,
        vix: Optional[float] = None,
    ) -> MarketRegime:
        """Determine the current market regime.

        Parameters
        ----------
        df : pd.DataFrame
            OHLCV data with at least ~200 rows for reliable EMA-200
            detection.  Must have ``high``, ``low``, ``close`` columns.
        vix : float, optional
            Current India VIX (or CBOE VIX) reading.  When provided it
            can override the price-based classification.

        Returns
        -------
        MarketRegime
        """
        # VIX overrides
        if vix is not None:
            if vix > 25:
                regime = MarketRegime.HIGH_VOLATILITY
                logger.info("Regime override: VIX %.2f > 25 → HIGH_VOLATILITY", vix)
                self._last_regime = regime
                return regime
            if vix < 12:
                regime = MarketRegime.LOW_VOLATILITY
                logger.info("Regime override: VIX %.2f < 12 → LOW_VOLATILITY", vix)
                self._last_regime = regime
                return regime

        # Need sufficient data for trend analysis
        if df.empty or len(df) < 30:
            logger.warning("detect_regime: insufficient data (%d rows), defaulting to SIDEWAYS", len(df))
            self._last_regime = MarketRegime.SIDEWAYS
            return MarketRegime.SIDEWAYS

        # Compute ADX
        adx_values, _, _ = adx(df, period=14)
        latest_adx = adx_values.iloc[-1] if not adx_values.empty else np.nan

        # Compute EMA-50 and EMA-200
        close = df["close"]
        ema_50 = ema(close, 50)
        ema_200 = ema(close, 200)

        latest_close = close.iloc[-1]
        latest_ema200 = ema_200.iloc[-1] if not ema_200.empty else np.nan
        latest_ema50 = ema_50.iloc[-1] if not ema_50.empty else np.nan

        # EMA slopes (5-period percentage change) for trend strength
        ema50_slope = np.nan
        if len(ema_50) >= 6:
            prev_val = ema_50.iloc[-6]
            if prev_val and prev_val != 0:
                ema50_slope = ((latest_ema50 - prev_val) / abs(prev_val)) * 100.0

        # Classification
        if not np.isnan(latest_adx) and latest_adx > 25:
            if not np.isnan(latest_ema200) and latest_close > latest_ema200:
                regime = MarketRegime.BULL_TRENDING
            elif not np.isnan(latest_ema200) and latest_close < latest_ema200:
                regime = MarketRegime.BEAR_TRENDING
            else:
                regime = MarketRegime.SIDEWAYS
        elif not np.isnan(latest_adx) and latest_adx < 20:
            regime = MarketRegime.SIDEWAYS
        else:
            # ADX between 20 and 25 — weak trend; use EMA slope
            if not np.isnan(ema50_slope) and ema50_slope > 0.5:
                regime = MarketRegime.BULL_TRENDING
            elif not np.isnan(ema50_slope) and ema50_slope < -0.5:
                regime = MarketRegime.BEAR_TRENDING
            else:
                regime = MarketRegime.SIDEWAYS

        self._last_regime = regime
        logger.info(
            "Regime detected: %s  (ADX=%.1f, close=%.2f, EMA200=%.2f, EMA50_slope=%.2f%%)",
            regime.value,
            latest_adx if not np.isnan(latest_adx) else 0,
            latest_close,
            latest_ema200 if not np.isnan(latest_ema200) else 0,
            ema50_slope if not np.isnan(ema50_slope) else 0,
        )
        return regime

    # ── Strategy mapping ─────────────────────────────────────────────

    @staticmethod
    def get_allowed_strategies(regime: MarketRegime) -> list[str]:
        """Return strategy names suitable for *regime*.

        Parameters
        ----------
        regime : MarketRegime

        Returns
        -------
        list[str]
        """
        strategies = _REGIME_STRATEGIES.get(regime, [])
        logger.debug("Allowed strategies for %s: %s", regime.value, strategies)
        return strategies

    @staticmethod
    def get_position_size_adjustment(regime: MarketRegime) -> float:
        """Return position-size multiplier for *regime*.

        Parameters
        ----------
        regime : MarketRegime

        Returns
        -------
        float
            Multiplier ∈ (0, 1.2].
        """
        adj = _REGIME_SIZE_ADJUSTMENT.get(regime, 1.0)
        logger.debug("Position size adjustment for %s: %.2f", regime.value, adj)
        return adj
