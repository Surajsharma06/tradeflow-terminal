"""
LSTM-based price predictor for the Trading System.

Uses a 2-layer LSTM with 128 hidden units and 0.3 dropout.
Returns mock predictions when PyTorch is unavailable or when
no pre-trained model file is found on disk.
"""

import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import numpy as np
import pandas as pd

try:
    import torch
    import torch.nn as nn

    HAS_TORCH = True
except ImportError:
    HAS_TORCH = False

from app.core.config import get_settings

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════
# PyTorch LSTM Module
# ═══════════════════════════════════════════════════════════════════════

if HAS_TORCH:

    class _LSTMModel(nn.Module):
        """
        2-layer LSTM for sequential price/feature prediction.

        Architecture:
        * LSTM: ``input_size`` → 128 hidden, 2 layers, dropout 0.3
        * Fully-connected: 128 → 64 → ``output_size``
        """

        def __init__(
            self,
            input_size: int,
            hidden_size: int = 128,
            num_layers: int = 2,
            dropout: float = 0.3,
            output_size: int = 1,
        ) -> None:
            super().__init__()
            self.hidden_size = hidden_size
            self.num_layers = num_layers

            self.lstm = nn.LSTM(
                input_size=input_size,
                hidden_size=hidden_size,
                num_layers=num_layers,
                dropout=dropout,
                batch_first=True,
            )
            self.fc = nn.Sequential(
                nn.Linear(hidden_size, 64),
                nn.ReLU(),
                nn.Dropout(dropout),
                nn.Linear(64, output_size),
            )

        def forward(self, x: "torch.Tensor") -> "torch.Tensor":
            """Forward pass: ``(batch, seq_len, features) → (batch, output_size)``."""
            # h0, c0 default to zeros
            lstm_out, _ = self.lstm(x)
            # Take the last timestep
            last = lstm_out[:, -1, :]
            return self.fc(last)


class LSTMPredictor:
    """
    High-level wrapper around the LSTM model.

    Provides ``predict``, ``prepare_sequence``, ``save``, and ``load``
    methods.  Falls back to mock predictions when PyTorch is unavailable
    or no trained model weights are present.
    """

    DEFAULT_SEQ_LEN: int = 30
    DEFAULT_FEATURES: int = 10

    def __init__(
        self,
        model_path: Optional[str] = None,
        input_size: int = DEFAULT_FEATURES,
        seq_len: int = DEFAULT_SEQ_LEN,
    ) -> None:
        """
        Args:
            model_path: Path to a saved ``.pt`` model file.
            input_size: Number of input features per timestep.
            seq_len: Number of timesteps in each input sequence.
        """
        settings = get_settings()
        self._model_dir = Path(settings.ml_model_dir)
        self._model_path = model_path or str(self._model_dir / "lstm_predictor.pt")
        self._input_size = input_size
        self._seq_len = seq_len
        self._model: Any = None
        self._is_mock: bool = True

        if not HAS_TORCH:
            logger.info("PyTorch not installed — LSTMPredictor will return mock predictions")
            return

        self._model = _LSTMModel(input_size=input_size)
        self._load_if_exists()

    # ── Model I/O ────────────────────────────────────────────────────

    def _load_if_exists(self) -> None:
        """Load pre-trained weights if the model file exists."""
        if not HAS_TORCH or self._model is None:
            return

        if os.path.isfile(self._model_path):
            try:
                state = torch.load(self._model_path, map_location="cpu", weights_only=True)
                self._model.load_state_dict(state)
                self._model.eval()
                self._is_mock = False
                logger.info("LSTM model loaded from %s", self._model_path)
            except Exception as exc:
                logger.warning("Failed to load LSTM model: %s — using mock", exc)
                self._is_mock = True
        else:
            logger.info(
                "No LSTM model file at %s — mock predictions will be used",
                self._model_path,
            )
            self._is_mock = True

    def save(self, path: Optional[str] = None) -> None:
        """Save the current model weights to disk."""
        if not HAS_TORCH or self._model is None:
            logger.warning("Cannot save — PyTorch not available")
            return

        save_path = path or self._model_path
        os.makedirs(os.path.dirname(save_path) or ".", exist_ok=True)
        torch.save(self._model.state_dict(), save_path)
        logger.info("LSTM model saved to %s", save_path)

    def load(self, path: Optional[str] = None) -> None:
        """Load model weights from *path*."""
        if not HAS_TORCH or self._model is None:
            logger.warning("Cannot load — PyTorch not available")
            return

        load_path = path or self._model_path
        try:
            state = torch.load(load_path, map_location="cpu", weights_only=True)
            self._model.load_state_dict(state)
            self._model.eval()
            self._is_mock = False
            logger.info("LSTM model loaded from %s", load_path)
        except Exception as exc:
            logger.error("Failed to load LSTM model from %s: %s", load_path, exc)

    # ── Sequence preparation ─────────────────────────────────────────

    def prepare_sequence(
        self,
        df: pd.DataFrame,
        feature_cols: Optional[list[str]] = None,
    ) -> np.ndarray:
        """
        Extract the last ``seq_len`` rows from *df* as a model-ready array.

        Args:
            df: Feature DataFrame (rows = timesteps).
            feature_cols: Columns to select. If ``None``, uses the
                first ``input_size`` numeric columns.

        Returns:
            ``np.ndarray`` of shape ``(1, seq_len, n_features)``.
        """
        if feature_cols is None:
            numeric = df.select_dtypes(include=[np.number])
            feature_cols = list(numeric.columns[: self._input_size])

        data = df[feature_cols].values[-self._seq_len:]
        if len(data) < self._seq_len:
            # Pad with zeros at the front
            pad = np.zeros((self._seq_len - len(data), len(feature_cols)))
            data = np.vstack([pad, data])

        return data.reshape(1, self._seq_len, len(feature_cols)).astype(np.float32)

    # ── Prediction ───────────────────────────────────────────────────

    def predict(
        self,
        df: pd.DataFrame,
        feature_cols: Optional[list[str]] = None,
    ) -> dict[str, Any]:
        """
        Predict the next-bar return.

        Args:
            df: Feature DataFrame.
            feature_cols: Feature columns to use.

        Returns:
            Dict with ``predicted_return``, ``direction``,
            ``confidence``, ``model_type``, ``timestamp``.
        """
        if self._is_mock or not HAS_TORCH:
            return self._mock_predict()

        try:
            seq = self.prepare_sequence(df, feature_cols)
            tensor = torch.tensor(seq, dtype=torch.float32)

            with torch.no_grad():
                output = self._model(tensor)
                predicted = output.item()

            direction = "BUY" if predicted > 0 else "SELL"
            confidence = min(abs(predicted) * 100, 100.0)

            result = {
                "predicted_return": round(predicted, 6),
                "direction": direction,
                "confidence": round(confidence, 2),
                "model_type": "LSTM",
                "timestamp": datetime.utcnow().isoformat(),
            }
            logger.debug("LSTM prediction: %.6f (%s, %.1f%%)", predicted, direction, confidence)
            return result

        except Exception as exc:
            logger.error("LSTM prediction failed: %s", exc)
            return self._mock_predict()

    # ── Mock fallback ────────────────────────────────────────────────

    @staticmethod
    def _mock_predict() -> dict[str, Any]:
        """Return a plausible mock prediction."""
        predicted = np.random.normal(0.001, 0.01)
        direction = "BUY" if predicted > 0 else "SELL"
        return {
            "predicted_return": round(float(predicted), 6),
            "direction": direction,
            "confidence": round(float(np.random.uniform(40, 75)), 2),
            "model_type": "LSTM",
            "mock": True,
            "timestamp": datetime.utcnow().isoformat(),
        }
