"""
PPO-based reinforcement learning trading agent.

Uses ``stable-baselines3`` for policy optimisation.  Provides
``predict_action``, ``save``, and ``load`` methods with automatic
mock fallback when the library is unavailable or no trained model exists.
"""

import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import numpy as np
import pandas as pd

try:
    from stable_baselines3 import PPO

    HAS_SB3 = True
except ImportError:
    HAS_SB3 = False

from app.core.config import get_settings

logger = logging.getLogger(__name__)

# Action mapping
_ACTIONS: dict[int, str] = {0: "HOLD", 1: "BUY", 2: "SELL"}


class PPOTradingAgent:
    """
    Proximal Policy Optimisation agent for trading.

    Wraps a pre-trained ``PPO`` model from stable-baselines3.
    Observation space is expected to be a 1-D feature vector
    (OHLCV + indicators + portfolio state).

    Falls back to mock action predictions when:
    * ``stable-baselines3`` is not installed.
    * No trained model file is found.
    """

    def __init__(
        self,
        model_path: Optional[str] = None,
        observation_size: int = 30,
    ) -> None:
        """
        Args:
            model_path: Path to a saved PPO model zip.
            observation_size: Expected observation vector length.
        """
        settings = get_settings()
        self._model_dir = Path(settings.ml_model_dir)
        self._model_path = model_path or str(self._model_dir / "ppo_trading_agent")
        self._obs_size = observation_size
        self._model: Any = None
        self._is_mock: bool = True

        if not HAS_SB3:
            logger.info(
                "stable-baselines3 not installed — "
                "PPOTradingAgent will return mock actions"
            )
            return

        self._load_if_exists()

    # ── Model I/O ────────────────────────────────────────────────────

    def _load_if_exists(self) -> None:
        """Load a pre-trained PPO model if the file exists."""
        zip_path = self._model_path
        if not zip_path.endswith(".zip"):
            zip_path += ".zip"

        if os.path.isfile(zip_path):
            try:
                self._model = PPO.load(self._model_path)
                self._is_mock = False
                logger.info("PPO model loaded from %s", self._model_path)
            except Exception as exc:
                logger.warning("Failed to load PPO model: %s — using mock", exc)
                self._is_mock = True
        else:
            logger.info(
                "No PPO model at %s — mock actions will be used",
                zip_path,
            )

    def save(self, path: Optional[str] = None) -> None:
        """Save the trained model to disk."""
        if not HAS_SB3 or self._model is None:
            logger.warning("Cannot save — stable-baselines3 not available or no model")
            return

        save_path = path or self._model_path
        os.makedirs(os.path.dirname(save_path) or ".", exist_ok=True)
        self._model.save(save_path)
        logger.info("PPO model saved to %s", save_path)

    def load(self, path: Optional[str] = None) -> None:
        """Load model from *path*."""
        if not HAS_SB3:
            logger.warning("Cannot load — stable-baselines3 not available")
            return

        load_path = path or self._model_path
        try:
            self._model = PPO.load(load_path)
            self._is_mock = False
            logger.info("PPO model loaded from %s", load_path)
        except Exception as exc:
            logger.error("Failed to load PPO model from %s: %s", load_path, exc)

    # ── Observation preparation ──────────────────────────────────────

    def prepare_observation(
        self,
        df: pd.DataFrame,
        portfolio_state: Optional[dict[str, float]] = None,
        feature_cols: Optional[list[str]] = None,
    ) -> np.ndarray:
        """
        Build a flat observation vector from features + portfolio state.

        Args:
            df: Feature DataFrame (uses the last row).
            portfolio_state: Dict with ``cash``, ``position_value``,
                ``unrealised_pnl``.  Defaults to a neutral state.
            feature_cols: Columns to select from *df*.

        Returns:
            1-D ``np.ndarray`` of length ``observation_size``.
        """
        if feature_cols:
            row = df[feature_cols].iloc[-1].values
        else:
            row = df.select_dtypes(include=[np.number]).iloc[-1].values

        # Append portfolio state
        ps = portfolio_state or {"cash": 1.0, "position_value": 0.0, "unrealised_pnl": 0.0}
        portfolio_vec = np.array([
            ps.get("cash", 1.0),
            ps.get("position_value", 0.0),
            ps.get("unrealised_pnl", 0.0),
        ])

        obs = np.concatenate([row, portfolio_vec]).astype(np.float32)

        # Pad or truncate to expected size
        if len(obs) < self._obs_size:
            obs = np.pad(obs, (0, self._obs_size - len(obs)))
        elif len(obs) > self._obs_size:
            obs = obs[: self._obs_size]

        # Replace NaN/Inf
        obs = np.nan_to_num(obs, nan=0.0, posinf=0.0, neginf=0.0)
        return obs

    # ── Action prediction ────────────────────────────────────────────

    def predict_action(
        self,
        df: pd.DataFrame,
        portfolio_state: Optional[dict[str, float]] = None,
        feature_cols: Optional[list[str]] = None,
    ) -> dict[str, Any]:
        """
        Predict the next trading action.

        Args:
            df: Feature DataFrame.
            portfolio_state: Current portfolio state dict.
            feature_cols: Feature columns to use.

        Returns:
            Dict with ``action`` (HOLD/BUY/SELL), ``confidence``,
            ``model_type``, ``timestamp``.
        """
        if self._is_mock or not HAS_SB3:
            return self._mock_predict()

        try:
            obs = self.prepare_observation(df, portfolio_state, feature_cols)
            action, _states = self._model.predict(obs, deterministic=True)
            action_int = int(action)
            action_name = _ACTIONS.get(action_int, "HOLD")

            # Estimate confidence from action probability (if available)
            confidence = 60.0  # Default
            try:
                dist = self._model.policy.get_distribution(
                    self._model.policy.obs_to_tensor(obs.reshape(1, -1))[0]
                )
                probs = dist.distribution.probs.detach().numpy()[0]
                confidence = float(probs[action_int]) * 100
            except Exception:
                pass

            result = {
                "action": action_name,
                "action_id": action_int,
                "confidence": round(confidence, 2),
                "model_type": "PPO",
                "timestamp": datetime.utcnow().isoformat(),
            }
            logger.debug("PPO action: %s (%.1f%%)", action_name, confidence)
            return result

        except Exception as exc:
            logger.error("PPO prediction failed: %s", exc)
            return self._mock_predict()

    # ── Mock fallback ────────────────────────────────────────────────

    @staticmethod
    def _mock_predict() -> dict[str, Any]:
        """Return a plausible mock action prediction."""
        # Weight towards HOLD for realistic distribution
        weights = [0.5, 0.3, 0.2]  # HOLD, BUY, SELL
        action_id = int(np.random.choice([0, 1, 2], p=weights))
        return {
            "action": _ACTIONS[action_id],
            "action_id": action_id,
            "confidence": round(float(np.random.uniform(35, 70)), 2),
            "model_type": "PPO",
            "mock": True,
            "timestamp": datetime.utcnow().isoformat(),
        }
