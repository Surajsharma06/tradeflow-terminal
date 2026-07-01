"""
Global market indicators and cross-market correlation engine.

Provides directional predictions derived from S&P 500, USD Index (DXY),
crude oil, and Bitcoin moves, a mock fear-and-greed gauge, and a signal
confirmation layer that cross-checks trading signals against global cues.
"""

from __future__ import annotations

import logging
from typing import Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class GlobalCorrelationEngine:
    """Cross-market correlation and signal-confirmation engine.

    All prediction methods use simplified linear models.  Replace with
    real regression coefficients or ML models once historical data
    pipelines are in place.
    """

    # ── Historical correlation assumptions ───────────────────────────
    _SP500_NIFTY_BETA = 0.65  # NIFTY moves ~65 % of S&P 500 overnight move
    _DXY_FII_SENSITIVITY = -0.8  # rising DXY → negative FII flow
    _CRUDE_NIFTY_BETA = -0.30  # crude up → NIFTY mild negative (India is importer)
    _BTC_ALT_CASCADE_THRESHOLD = -5.0  # BTC drop > 5 % triggers alt risk

    def __init__(self) -> None:
        self._fear_greed_score: Optional[float] = None

    # ─────────────────────────────────────────────────────────────────
    # Correlation matrix
    # ─────────────────────────────────────────────────────────────────

    def calculate_correlation_matrix(
        self,
        price_data: dict[str, pd.Series],
    ) -> pd.DataFrame:
        """Build a pairwise Pearson correlation matrix from price series.

        Parameters
        ----------
        price_data : dict[str, pd.Series]
            Mapping of asset name → daily close-price series.

        Returns
        -------
        pd.DataFrame
            Correlation matrix (N × N).
        """
        if not price_data:
            logger.warning("calculate_correlation_matrix: empty price_data")
            return pd.DataFrame()

        combined = pd.DataFrame(price_data)
        returns = combined.pct_change().dropna()

        if returns.empty or len(returns) < 2:
            logger.warning("calculate_correlation_matrix: insufficient return data")
            return pd.DataFrame(
                np.nan,
                index=combined.columns,
                columns=combined.columns,
            )

        corr = returns.corr()
        logger.info(
            "Correlation matrix computed for %d assets over %d periods",
            len(price_data),
            len(returns),
        )
        return corr

    # ─────────────────────────────────────────────────────────────────
    # Cross-market predictions
    # ─────────────────────────────────────────────────────────────────

    def us_to_india_prediction(self, sp500_change: float) -> dict[str, object]:
        """Predict NIFTY direction based on S&P 500 overnight change.

        Parameters
        ----------
        sp500_change : float
            S&P 500 percentage change (e.g. ``-1.5`` for −1.5 %).

        Returns
        -------
        dict
            ``predicted_nifty_change``, ``direction``, ``confidence``.
        """
        predicted = sp500_change * self._SP500_NIFTY_BETA
        direction = "BULLISH" if predicted > 0 else "BEARISH" if predicted < 0 else "NEUTRAL"
        confidence = min(abs(sp500_change) * 20, 100.0)  # rough heuristic

        result = {
            "predicted_nifty_change": round(predicted, 3),
            "direction": direction,
            "confidence": round(confidence, 1),
        }
        logger.info("US→India prediction: S&P %.2f%% → NIFTY ~%.2f%%", sp500_change, predicted)
        return result

    def dxy_impact_prediction(self, dxy_change: float) -> dict[str, object]:
        """Predict FII flow direction from Dollar Index (DXY) move.

        A rising DXY typically leads to FII outflows from emerging
        markets including India.

        Parameters
        ----------
        dxy_change : float
            DXY percentage change.

        Returns
        -------
        dict
            ``fii_flow_direction``, ``impact_magnitude``, ``confidence``.
        """
        impact = dxy_change * self._DXY_FII_SENSITIVITY
        flow_dir = "INFLOW" if impact > 0 else "OUTFLOW" if impact < 0 else "NEUTRAL"
        confidence = min(abs(dxy_change) * 30, 100.0)

        result = {
            "fii_flow_direction": flow_dir,
            "impact_magnitude": round(abs(impact), 3),
            "confidence": round(confidence, 1),
        }
        logger.info("DXY impact: DXY %.2f%% → FII %s", dxy_change, flow_dir)
        return result

    def crude_nifty_correlation(self, crude_change: float) -> dict[str, object]:
        """Predict NIFTY impact from crude-oil price movement.

        India is a net crude importer; rising crude is mildly negative
        for the index.

        Parameters
        ----------
        crude_change : float
            Crude oil percentage change.
        """
        predicted = crude_change * self._CRUDE_NIFTY_BETA
        direction = "POSITIVE" if predicted > 0 else "NEGATIVE" if predicted < 0 else "NEUTRAL"

        result = {
            "predicted_nifty_impact": round(predicted, 3),
            "direction": direction,
            "confidence": round(min(abs(crude_change) * 15, 100.0), 1),
        }
        logger.info("Crude→NIFTY: crude %.2f%% → NIFTY ~%.2f%%", crude_change, predicted)
        return result

    def btc_altcoin_cascade_risk(self, btc_change: float) -> dict[str, object]:
        """Assess alt-coin cascade risk from a Bitcoin price move.

        Parameters
        ----------
        btc_change : float
            BTC percentage change.

        Returns
        -------
        dict
            ``risk_level`` (LOW / MEDIUM / HIGH / EXTREME),
            ``btc_change``, ``cascade_probable``.
        """
        if btc_change <= self._BTC_ALT_CASCADE_THRESHOLD:
            risk = "EXTREME"
        elif btc_change <= -3.0:
            risk = "HIGH"
        elif btc_change <= -1.0:
            risk = "MEDIUM"
        else:
            risk = "LOW"

        result = {
            "risk_level": risk,
            "btc_change": round(btc_change, 2),
            "cascade_probable": risk in ("HIGH", "EXTREME"),
        }
        logger.info("BTC cascade risk: BTC %.2f%% → %s", btc_change, risk)
        return result

    # ─────────────────────────────────────────────────────────────────
    # Fear & Greed
    # ─────────────────────────────────────────────────────────────────

    def get_fear_greed_score(self) -> dict[str, object]:
        """Return a mock Fear & Greed score (0 – 100).

        0  = Extreme Fear
        50 = Neutral
        100 = Extreme Greed

        Returns
        -------
        dict
            ``score``, ``label``.
        """
        # Mock: moderate greed
        score = 62.0
        self._fear_greed_score = score

        if score <= 20:
            label = "EXTREME_FEAR"
        elif score <= 40:
            label = "FEAR"
        elif score <= 60:
            label = "NEUTRAL"
        elif score <= 80:
            label = "GREED"
        else:
            label = "EXTREME_GREED"

        result = {"score": score, "label": label}
        logger.debug("Fear & Greed score: %s", result)
        return result

    # ─────────────────────────────────────────────────────────────────
    # Signal confirmation
    # ─────────────────────────────────────────────────────────────────

    def should_confirm_signal(
        self,
        signal_direction: str,
        correlations: Optional[dict[str, object]] = None,
    ) -> bool:
        """Decide whether global macro conditions support *signal_direction*.

        A simple majority-vote across available global cues.

        Parameters
        ----------
        signal_direction : str
            ``"BULLISH"`` or ``"BEARISH"``.
        correlations : dict, optional
            Pre-computed macro predictions (keys:
            ``us_prediction``, ``dxy_prediction``, ``crude_prediction``,
            ``fear_greed``).

        Returns
        -------
        bool
            ``True`` if global cues support the signal.
        """
        if correlations is None:
            logger.debug("should_confirm_signal: no correlations – auto-confirm")
            return True

        votes_for = 0
        votes_against = 0

        us_pred = correlations.get("us_prediction", {})
        if isinstance(us_pred, dict):
            us_dir = us_pred.get("direction", "NEUTRAL")
            if us_dir == signal_direction:
                votes_for += 1
            elif us_dir != "NEUTRAL":
                votes_against += 1

        dxy_pred = correlations.get("dxy_prediction", {})
        if isinstance(dxy_pred, dict):
            fii_flow = dxy_pred.get("fii_flow_direction", "NEUTRAL")
            if (signal_direction == "BULLISH" and fii_flow == "INFLOW") or \
               (signal_direction == "BEARISH" and fii_flow == "OUTFLOW"):
                votes_for += 1
            elif fii_flow != "NEUTRAL":
                votes_against += 1

        crude_pred = correlations.get("crude_prediction", {})
        if isinstance(crude_pred, dict):
            crude_dir = crude_pred.get("direction", "NEUTRAL")
            if (signal_direction == "BULLISH" and crude_dir == "POSITIVE") or \
               (signal_direction == "BEARISH" and crude_dir == "NEGATIVE"):
                votes_for += 1
            elif crude_dir != "NEUTRAL":
                votes_against += 1

        fg = correlations.get("fear_greed", {})
        if isinstance(fg, dict):
            fg_score = fg.get("score", 50)
            if signal_direction == "BULLISH" and fg_score > 40:
                votes_for += 1
            elif signal_direction == "BEARISH" and fg_score < 40:
                votes_for += 1
            else:
                votes_against += 1

        confirmed = votes_for >= votes_against
        logger.info(
            "Signal confirmation: direction=%s, votes_for=%d, votes_against=%d → %s",
            signal_direction,
            votes_for,
            votes_against,
            "CONFIRMED" if confirmed else "REJECTED",
        )
        return confirmed
