"""
Ensemble decision maker for the Trading System.

Combines predictions from LSTM, XGBoost, PPO, and Sentiment models
using configurable weights.  Gracefully degrades when individual
models are unavailable — redistributes weight among active models.

Default weights:
* LSTM: 30 %
* XGBoost: 30 %
* PPO: 25 %
* Sentiment: 15 %
"""

import logging
from datetime import datetime
from typing import Any, Optional

import numpy as np
import pandas as pd

from app.ml.lstm_predictor import LSTMPredictor
from app.ml.xgboost_classifier import XGBoostClassifier
from app.ml.ppo_agent import PPOTradingAgent
from app.ml.sentiment_engine import SentimentEngine

logger = logging.getLogger(__name__)

# Default ensemble weights
_DEFAULT_WEIGHTS: dict[str, float] = {
    "lstm": 0.30,
    "xgboost": 0.30,
    "ppo": 0.25,
    "sentiment": 0.15,
}

# Direction-to-score mapping
_DIRECTION_SCORE: dict[str, float] = {
    "BUY": 1.0,
    "SELL": -1.0,
    "HOLD": 0.0,
}


class EnsembleDecisionMaker:
    """
    Weighted ensemble of multiple ML models for trade decisions.

    Accepts predictions from LSTM, XGBoost, PPO, and Sentiment
    models, converts each to a directional score (−1 to +1), and
    computes a weighted average.  The final score is mapped to a
    BUY / SELL / HOLD signal with confidence.

    If a model is unavailable, its weight is redistributed
    proportionally among the remaining models.
    """

    def __init__(
        self,
        weights: Optional[dict[str, float]] = None,
        buy_threshold: float = 0.35,
        sell_threshold: float = -0.35,
    ) -> None:
        """
        Args:
            weights: Per-model weights. Keys: ``lstm``, ``xgboost``,
                ``ppo``, ``sentiment``.
            buy_threshold: Ensemble score above which to signal BUY.
            sell_threshold: Ensemble score below which to signal SELL.
        """
        self.weights = weights or _DEFAULT_WEIGHTS.copy()
        self.buy_threshold = buy_threshold
        self.sell_threshold = sell_threshold

        # Lazy-initialise sub-models
        self._lstm: Optional[LSTMPredictor] = None
        self._xgb: Optional[XGBoostClassifier] = None
        self._ppo: Optional[PPOTradingAgent] = None
        self._sentiment: Optional[SentimentEngine] = None

        logger.info(
            "EnsembleDecisionMaker initialised — weights: %s, "
            "thresholds: BUY>%.2f, SELL<%.2f",
            self.weights, buy_threshold, sell_threshold,
        )

    # ── Lazy model accessors ─────────────────────────────────────────

    @property
    def lstm(self) -> LSTMPredictor:
        """Lazy-load LSTM predictor."""
        if self._lstm is None:
            self._lstm = LSTMPredictor()
        return self._lstm

    @property
    def xgb(self) -> XGBoostClassifier:
        """Lazy-load XGBoost classifier."""
        if self._xgb is None:
            self._xgb = XGBoostClassifier()
        return self._xgb

    @property
    def ppo(self) -> PPOTradingAgent:
        """Lazy-load PPO agent."""
        if self._ppo is None:
            self._ppo = PPOTradingAgent()
        return self._ppo

    @property
    def sentiment(self) -> SentimentEngine:
        """Lazy-load sentiment engine."""
        if self._sentiment is None:
            self._sentiment = SentimentEngine()
        return self._sentiment

    # ── Main decision method ─────────────────────────────────────────

    def combine_signals(
        self,
        df: pd.DataFrame,
        headlines: Optional[list[str]] = None,
        portfolio_state: Optional[dict[str, float]] = None,
        feature_cols: Optional[list[str]] = None,
    ) -> dict[str, Any]:
        """
        Combine all model predictions into a single trading decision.

        Args:
            df: Feature DataFrame for price-based models.
            headlines: News headlines for sentiment analysis.
            portfolio_state: Current portfolio state for PPO.
            feature_cols: Feature columns for LSTM and XGBoost.

        Returns:
            Dict with ``signal``, ``score``, ``confidence``,
            ``model_scores``, ``active_models``, ``weights_used``.
        """
        model_results: dict[str, dict[str, Any]] = {}
        model_scores: dict[str, float] = {}
        active_weights: dict[str, float] = {}

        # ── LSTM prediction ──────────────────────────────────────────
        try:
            lstm_pred = self.lstm.predict(df, feature_cols)
            direction = lstm_pred.get("direction", "HOLD")
            confidence = lstm_pred.get("confidence", 50.0)
            score = _DIRECTION_SCORE.get(direction, 0.0) * (confidence / 100)
            model_scores["lstm"] = score
            model_results["lstm"] = lstm_pred
            active_weights["lstm"] = self.weights.get("lstm", 0)
        except Exception as exc:
            logger.warning("LSTM prediction unavailable: %s", exc)

        # ── XGBoost prediction ───────────────────────────────────────
        try:
            xgb_pred = self.xgb.predict(df, feature_cols)
            signal = xgb_pred.get("signal", "HOLD")
            confidence = xgb_pred.get("confidence", 50.0)
            score = _DIRECTION_SCORE.get(signal, 0.0) * (confidence / 100)
            model_scores["xgboost"] = score
            model_results["xgboost"] = xgb_pred
            active_weights["xgboost"] = self.weights.get("xgboost", 0)
        except Exception as exc:
            logger.warning("XGBoost prediction unavailable: %s", exc)

        # ── PPO prediction ───────────────────────────────────────────
        try:
            ppo_pred = self.ppo.predict_action(df, portfolio_state, feature_cols)
            action = ppo_pred.get("action", "HOLD")
            confidence = ppo_pred.get("confidence", 50.0)
            score = _DIRECTION_SCORE.get(action, 0.0) * (confidence / 100)
            model_scores["ppo"] = score
            model_results["ppo"] = ppo_pred
            active_weights["ppo"] = self.weights.get("ppo", 0)
        except Exception as exc:
            logger.warning("PPO prediction unavailable: %s", exc)

        # ── Sentiment prediction ─────────────────────────────────────
        try:
            if headlines:
                sent = self.sentiment.get_aggregate_sentiment(headlines)
            else:
                sent = {"overall_score": 50.0, "overall_sentiment": "neutral"}

            # Convert 0–100 score to −1 to +1
            sent_score = (sent["overall_score"] - 50) / 50
            model_scores["sentiment"] = sent_score
            model_results["sentiment"] = sent
            active_weights["sentiment"] = self.weights.get("sentiment", 0)
        except Exception as exc:
            logger.warning("Sentiment prediction unavailable: %s", exc)

        # ── Combine scores ───────────────────────────────────────────
        if not model_scores:
            logger.error("No models produced predictions — returning HOLD")
            return self._fallback_result()

        # Redistribute weights among active models
        total_active_weight = sum(active_weights.values())
        normalised_weights: dict[str, float] = {}
        for model, w in active_weights.items():
            normalised_weights[model] = w / total_active_weight if total_active_weight > 0 else 0

        # Weighted ensemble score (−1 to +1)
        ensemble_score = sum(
            model_scores[m] * normalised_weights.get(m, 0)
            for m in model_scores
        )

        # Map to signal
        if ensemble_score > self.buy_threshold:
            signal = "BUY"
        elif ensemble_score < self.sell_threshold:
            signal = "SELL"
        else:
            signal = "HOLD"

        # Confidence: how far we are from the threshold
        if signal == "BUY":
            confidence = min((ensemble_score - self.buy_threshold) / (1 - self.buy_threshold) * 100, 100)
        elif signal == "SELL":
            confidence = min((self.sell_threshold - ensemble_score) / (1 + self.sell_threshold) * 100, 100)
        else:
            confidence = (1 - abs(ensemble_score) / max(abs(self.buy_threshold), abs(self.sell_threshold))) * 50

        # Convert ensemble score from (-1, +1) to (0, 100) for the API
        score_0_100 = round((ensemble_score + 1) * 50, 2)

        result = {
            "signal": signal,
            "score": score_0_100,
            "ensemble_score": round(ensemble_score, 4),
            "confidence": round(max(0, confidence), 2),
            "model_scores": {k: round(v, 4) for k, v in model_scores.items()},
            "model_results": model_results,
            "active_models": list(model_scores.keys()),
            "weights_used": {k: round(v, 4) for k, v in normalised_weights.items()},
            "timestamp": datetime.utcnow().isoformat(),
        }

        logger.info(
            "Ensemble decision: %s (score=%.2f, confidence=%.1f%%, models=%s)",
            signal, score_0_100, confidence, list(model_scores.keys()),
        )
        return result

    # ── Fallback ─────────────────────────────────────────────────────

    @staticmethod
    def _fallback_result() -> dict[str, Any]:
        """Return a safe HOLD result when no models are available."""
        return {
            "signal": "HOLD",
            "score": 50.0,
            "ensemble_score": 0.0,
            "confidence": 0.0,
            "model_scores": {},
            "model_results": {},
            "active_models": [],
            "weights_used": {},
            "fallback": True,
            "timestamp": datetime.utcnow().isoformat(),
        }
