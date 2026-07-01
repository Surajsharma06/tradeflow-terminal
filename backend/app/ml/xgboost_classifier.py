"""
XGBoost classifier for BUY / SELL / HOLD signal prediction.

Wraps ``xgboost.XGBClassifier`` with feature-importance extraction,
model persistence, and automatic mock-prediction fallback when the
``xgboost`` library is not installed or no trained model is available.
"""

import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import numpy as np
import pandas as pd

try:
    import xgboost as xgb

    HAS_XGB = True
except ImportError:
    HAS_XGB = False

from app.core.config import get_settings

logger = logging.getLogger(__name__)

# Class label mapping
_LABELS: dict[int, str] = {0: "SELL", 1: "HOLD", 2: "BUY"}
_LABEL_INV: dict[str, int] = {v: k for k, v in _LABELS.items()}


class XGBoostClassifier:
    """
    Gradient-boosted tree classifier for trading signals.

    Predicts one of three classes:
    * ``BUY`` — open a long position.
    * ``SELL`` — exit / short.
    * ``HOLD`` — do nothing.

    Falls back to mock predictions when ``xgboost`` is not installed
    or no trained model is loaded.
    """

    def __init__(
        self,
        model_path: Optional[str] = None,
        n_estimators: int = 300,
        max_depth: int = 6,
        learning_rate: float = 0.05,
    ) -> None:
        """
        Args:
            model_path: Path to a saved ``.json`` XGBoost model.
            n_estimators: Number of boosting rounds.
            max_depth: Maximum tree depth.
            learning_rate: Boosting learning rate.
        """
        settings = get_settings()
        self._model_dir = Path(settings.ml_model_dir)
        self._model_path = model_path or str(self._model_dir / "forex_xgb_model.json")
        self._model: Any = None
        self._is_mock: bool = True
        self._feature_names: list[str] = []

        if not HAS_XGB:
            logger.info("xgboost not installed — XGBoostClassifier will return mock predictions")
            return

        self._model = xgb.XGBClassifier(
            n_estimators=n_estimators,
            max_depth=max_depth,
            learning_rate=learning_rate,
            objective="multi:softprob",
            num_class=3,
            eval_metric="mlogloss",
            use_label_encoder=False,
            random_state=42,
            n_jobs=-1,
        )
        self._load_if_exists()

    # ── Model I/O ────────────────────────────────────────────────────

    def _load_if_exists(self) -> None:
        """Load a pre-trained model if the file exists."""
        if not HAS_XGB or self._model is None:
            return

        if os.path.isfile(self._model_path):
            try:
                self._model.load_model(self._model_path)
                self._is_mock = False
                logger.info("XGBoost model loaded from %s", self._model_path)
            except Exception as exc:
                logger.warning("Failed to load XGBoost model: %s — using mock", exc)
                self._is_mock = True
        else:
            logger.info(
                "No XGBoost model at %s — mock predictions will be used",
                self._model_path,
            )

    def save(self, path: Optional[str] = None) -> None:
        """Persist the trained model to disk."""
        if not HAS_XGB or self._model is None:
            logger.warning("Cannot save — xgboost not available")
            return

        save_path = path or self._model_path
        os.makedirs(os.path.dirname(save_path) or ".", exist_ok=True)
        self._model.save_model(save_path)
        logger.info("XGBoost model saved to %s", save_path)

    def load(self, path: Optional[str] = None) -> None:
        """Load model weights from *path*."""
        if not HAS_XGB:
            logger.warning("Cannot load — xgboost not available")
            return

        load_path = path or self._model_path
        try:
            if self._model is None:
                self._model = xgb.XGBClassifier()
            self._model.load_model(load_path)
            self._is_mock = False
            logger.info("XGBoost model loaded from %s", load_path)
        except Exception as exc:
            logger.error("Failed to load XGBoost model from %s: %s", load_path, exc)

    # ── Training ─────────────────────────────────────────────────────

    def train(
        self,
        X: pd.DataFrame,
        y: pd.Series,
        eval_set: Optional[list[tuple[pd.DataFrame, pd.Series]]] = None,
    ) -> dict[str, Any]:
        """
        Train the classifier on labelled data.

        Args:
            X: Feature matrix.
            y: Target labels (0=SELL, 1=HOLD, 2=BUY).
            eval_set: Optional validation set for early stopping.

        Returns:
            Dict with training summary metrics.
        """
        if not HAS_XGB or self._model is None:
            logger.warning("Cannot train — xgboost not available")
            return {"error": "xgboost not available"}

        self._feature_names = list(X.columns)

        fit_params: dict[str, Any] = {}
        if eval_set:
            fit_params["eval_set"] = eval_set
            fit_params["verbose"] = False

        self._model.fit(X, y, **fit_params)
        self._is_mock = False

        # Training accuracy
        preds = self._model.predict(X)
        accuracy = float(np.mean(preds == y))

        logger.info(
            "XGBoost trained on %d samples — accuracy: %.2f%%",
            len(X), accuracy * 100,
        )
        return {
            "samples": len(X),
            "features": len(self._feature_names),
            "accuracy": round(accuracy * 100, 2),
        }

    # ── Prediction ───────────────────────────────────────────────────

    def predict(
        self,
        df: pd.DataFrame,
        feature_cols: Optional[list[str]] = None,
    ) -> dict[str, Any]:
        """
        Predict BUY / SELL / HOLD for the latest row.

        Args:
            df: Feature DataFrame (uses the last row).
            feature_cols: Columns to select. ``None`` = use training columns.

        Returns:
            Dict with ``signal``, ``probabilities``, ``confidence``,
            ``model_type``, ``timestamp``.
        """
        if self._is_mock or not HAS_XGB:
            return self._mock_predict()

        try:
            cols = feature_cols or self._feature_names
            if not cols:
                # Fallback: use all numeric columns
                cols = list(df.select_dtypes(include=[np.number]).columns)

            X = df[cols].iloc[[-1]]
            proba = self._model.predict_proba(X)[0]
            pred_class = int(np.argmax(proba))
            signal = _LABELS[pred_class]
            confidence = float(proba[pred_class]) * 100

            result = {
                "signal": signal,
                "probabilities": {
                    "SELL": round(float(proba[0]) * 100, 2),
                    "HOLD": round(float(proba[1]) * 100, 2),
                    "BUY": round(float(proba[2]) * 100, 2),
                },
                "confidence": round(confidence, 2),
                "model_type": "XGBoost",
                "timestamp": datetime.utcnow().isoformat(),
            }
            logger.debug("XGBoost prediction: %s (%.1f%%)", signal, confidence)
            return result

        except Exception as exc:
            logger.error("XGBoost prediction failed: %s", exc)
            return self._mock_predict()

    # ── Feature importance ───────────────────────────────────────────

    def get_feature_importance(
        self,
        importance_type: str = "gain",
        top_n: int = 20,
    ) -> list[dict[str, Any]]:
        """
        Return feature importance scores.

        Args:
            importance_type: ``\"gain\"``, ``\"weight\"``, or ``\"cover\"``.
            top_n: Number of top features to return.

        Returns:
            List of ``{feature, importance}`` dicts, sorted descending.
        """
        if self._is_mock or not HAS_XGB or self._model is None:
            return self._mock_feature_importance(top_n)

        try:
            booster = self._model.get_booster()
            scores = booster.get_score(importance_type=importance_type)

            items = [
                {"feature": k, "importance": round(v, 4)}
                for k, v in sorted(scores.items(), key=lambda x: x[1], reverse=True)
            ]
            return items[:top_n]

        except Exception as exc:
            logger.error("Feature importance extraction failed: %s", exc)
            return self._mock_feature_importance(top_n)

    # ── Mock fallbacks ───────────────────────────────────────────────

    @staticmethod
    def _mock_predict() -> dict[str, Any]:
        """Return a plausible mock prediction."""
        probs = np.random.dirichlet([2, 3, 2])  # Slightly favour HOLD
        pred_class = int(np.argmax(probs))
        return {
            "signal": _LABELS[pred_class],
            "probabilities": {
                "SELL": round(float(probs[0]) * 100, 2),
                "HOLD": round(float(probs[1]) * 100, 2),
                "BUY": round(float(probs[2]) * 100, 2),
            },
            "confidence": round(float(probs[pred_class]) * 100, 2),
            "model_type": "XGBoost",
            "mock": True,
            "timestamp": datetime.utcnow().isoformat(),
        }

    @staticmethod
    def _mock_feature_importance(top_n: int = 20) -> list[dict[str, Any]]:
        """Return mock feature importance data."""
        features = [
            "rsi_14", "macd_histogram", "bb_pct_b", "adx_14", "atr_pct",
            "relative_volume", "dist_sma_20_pct", "volatility_20d",
            "stoch_k", "cci_20", "log_return_1d", "mfi_14",
            "williams_r", "obv", "vol_ratio_5_20",
            "dist_52w_high_pct", "price_position_20d",
            "volume_roc_5", "garman_klass_vol_20d", "cum_return_20d",
        ]
        importances = sorted(np.random.uniform(0.01, 0.15, size=len(features)), reverse=True)
        return [
            {"feature": f, "importance": round(float(imp), 4)}
            for f, imp in zip(features[:top_n], importances[:top_n])
        ]
