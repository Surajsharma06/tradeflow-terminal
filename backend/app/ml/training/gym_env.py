"""
Custom Gymnasium trading environment for RL agent training.

State space: OHLCV data + technical indicators + portfolio state.
Action space: Discrete(3) — HOLD, BUY, SELL.
Reward: Sharpe-ratio based with penalties for over-trading and
drawdown.

Falls back gracefully when ``gymnasium`` is not installed.
"""

import logging
from typing import Any, Optional

import numpy as np
import pandas as pd

try:
    import gymnasium as gym
    from gymnasium import spaces

    HAS_GYM = True
except ImportError:
    HAS_GYM = False

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════════
# Environment configuration defaults
# ═══════════════════════════════════════════════════════════════════════

_DEFAULT_CONFIG: dict[str, Any] = {
    "initial_balance": 1_000_000.0,
    "commission_rate": 0.001,           # 0.1 % per trade
    "max_position_pct": 0.20,           # max 20 % of portfolio per position
    "reward_lookback": 20,              # Sharpe window
    "overtrade_penalty": -0.005,        # penalty per excess trade
    "max_trades_per_day": 5,
    "drawdown_penalty_factor": 0.5,     # extra penalty for large drawdowns
    "window_size": 30,                  # observation window length
}


if HAS_GYM:

    class TradingEnv(gym.Env):
        """
        OpenAI Gymnasium environment for training RL trading agents.

        Observation:
            A vector of ``(window_size × n_features) + 3`` floats
            comprising flattened OHLCV + indicator history plus
            ``[cash_ratio, position_ratio, unrealised_pnl_ratio]``.

        Actions:
            ``0`` = HOLD, ``1`` = BUY, ``2`` = SELL.

        Reward:
            Differential Sharpe ratio + trade P&L bonus/penalty −
            over-trading penalty − drawdown penalty.
        """

        metadata = {"render_modes": ["human"]}

        def __init__(
            self,
            df: pd.DataFrame,
            feature_cols: Optional[list[str]] = None,
            config: Optional[dict[str, Any]] = None,
            render_mode: Optional[str] = None,
        ) -> None:
            """
            Args:
                df: DataFrame with OHLCV and feature columns.
                    Must contain at least ``close`` column.
                feature_cols: Columns to include in observation.
                    Defaults to all numeric columns.
                config: Override default environment config.
                render_mode: Gymnasium render mode.
            """
            super().__init__()
            self.render_mode = render_mode

            # Config
            self.cfg = {**_DEFAULT_CONFIG, **(config or {})}

            # Data
            self.df = df.copy()
            self.df.columns = [c.lower() for c in self.df.columns]
            if feature_cols:
                self._feature_cols = [c.lower() for c in feature_cols]
            else:
                self._feature_cols = list(
                    self.df.select_dtypes(include=[np.number]).columns
                )

            self._n_features = len(self._feature_cols)
            self._n_steps = len(self.df) - 1
            self._window = self.cfg["window_size"]

            # ── Spaces ───────────────────────────────────────────────
            obs_size = self._window * self._n_features + 3  # + portfolio state
            self.observation_space = spaces.Box(
                low=-np.inf, high=np.inf,
                shape=(obs_size,), dtype=np.float32,
            )
            self.action_space = spaces.Discrete(3)  # HOLD, BUY, SELL

            # ── Internal state (set by reset) ────────────────────────
            self._step_idx: int = 0
            self._balance: float = 0.0
            self._shares: int = 0
            self._entry_price: float = 0.0
            self._peak_value: float = 0.0
            self._trade_count: int = 0
            self._returns: list[float] = []

            logger.info(
                "TradingEnv created — %d steps, %d features, window=%d",
                self._n_steps, self._n_features, self._window,
            )

        # ── Gymnasium API ────────────────────────────────────────────

        def reset(
            self,
            *,
            seed: Optional[int] = None,
            options: Optional[dict] = None,
        ) -> tuple[np.ndarray, dict]:
            """Reset environment to initial state."""
            super().reset(seed=seed)

            self._step_idx = self._window
            self._balance = self.cfg["initial_balance"]
            self._shares = 0
            self._entry_price = 0.0
            self._peak_value = self._balance
            self._trade_count = 0
            self._returns = []

            obs = self._get_observation()
            info = self._get_info()
            return obs, info

        def step(
            self,
            action: int,
        ) -> tuple[np.ndarray, float, bool, bool, dict]:
            """
            Execute one step.

            Args:
                action: ``0``=HOLD, ``1``=BUY, ``2``=SELL.

            Returns:
                (observation, reward, terminated, truncated, info).
            """
            current_price = self._current_price()
            prev_value = self._portfolio_value(current_price)

            # Execute action
            reward = 0.0
            if action == 1:  # BUY
                reward += self._execute_buy(current_price)
            elif action == 2:  # SELL
                reward += self._execute_sell(current_price)

            # Advance
            self._step_idx += 1
            new_price = self._current_price()
            new_value = self._portfolio_value(new_price)

            # Compute reward components
            step_return = (new_value - prev_value) / (prev_value + 1e-10)
            self._returns.append(step_return)

            # Sharpe-based reward
            sharpe_reward = self._sharpe_reward()
            reward += sharpe_reward

            # Drawdown penalty
            self._peak_value = max(self._peak_value, new_value)
            drawdown = (self._peak_value - new_value) / (self._peak_value + 1e-10)
            if drawdown > 0.05:  # > 5% drawdown
                reward -= drawdown * self.cfg["drawdown_penalty_factor"]

            # Check termination
            terminated = self._step_idx >= self._n_steps
            truncated = new_value < self.cfg["initial_balance"] * 0.5  # -50% wipeout

            obs = self._get_observation()
            info = self._get_info()

            return obs, float(reward), terminated, truncated, info

        # ── Internals ────────────────────────────────────────────────

        def _current_price(self) -> float:
            """Get the close price at the current step."""
            idx = min(self._step_idx, len(self.df) - 1)
            return float(self.df["close"].iloc[idx])

        def _portfolio_value(self, price: float) -> float:
            """Total portfolio value = cash + shares × price."""
            return self._balance + self._shares * price

        def _get_observation(self) -> np.ndarray:
            """Build the observation vector."""
            start = max(0, self._step_idx - self._window)
            end = self._step_idx
            window_data = self.df[self._feature_cols].iloc[start:end].values

            # Pad if needed
            if len(window_data) < self._window:
                pad = np.zeros((self._window - len(window_data), self._n_features))
                window_data = np.vstack([pad, window_data])

            flat = window_data.flatten().astype(np.float32)

            # Portfolio state (normalised)
            price = self._current_price()
            total = self._portfolio_value(price)
            portfolio_state = np.array([
                self._balance / (total + 1e-10),              # cash ratio
                (self._shares * price) / (total + 1e-10),     # position ratio
                (price - self._entry_price) / (self._entry_price + 1e-10)
                if self._shares > 0 else 0.0,                 # unrealised P&L ratio
            ], dtype=np.float32)

            obs = np.concatenate([flat, portfolio_state])
            return np.nan_to_num(obs, nan=0.0, posinf=0.0, neginf=0.0)

        def _get_info(self) -> dict[str, Any]:
            """Return environment info dict."""
            price = self._current_price()
            return {
                "step": self._step_idx,
                "balance": round(self._balance, 2),
                "shares": self._shares,
                "portfolio_value": round(self._portfolio_value(price), 2),
                "trade_count": self._trade_count,
                "price": price,
            }

        def _execute_buy(self, price: float) -> float:
            """Buy shares up to max position size. Returns reward component."""
            if self._shares > 0:
                return 0.0  # Already in position

            max_invest = self._balance * self.cfg["max_position_pct"]
            shares_to_buy = int(max_invest / (price + 1e-10))
            if shares_to_buy <= 0:
                return 0.0

            cost = shares_to_buy * price
            commission = cost * self.cfg["commission_rate"]

            self._balance -= cost + commission
            self._shares = shares_to_buy
            self._entry_price = price
            self._trade_count += 1

            # Over-trading penalty
            if self._trade_count > self.cfg["max_trades_per_day"]:
                return self.cfg["overtrade_penalty"]
            return 0.0

        def _execute_sell(self, price: float) -> float:
            """Sell all shares. Returns reward component (P&L based)."""
            if self._shares <= 0:
                return 0.0

            proceeds = self._shares * price
            commission = proceeds * self.cfg["commission_rate"]
            pnl = (price - self._entry_price) * self._shares - commission

            self._balance += proceeds - commission
            self._shares = 0
            self._entry_price = 0.0
            self._trade_count += 1

            # P&L reward (normalised)
            pnl_reward = pnl / (self.cfg["initial_balance"] + 1e-10) * 10

            # Over-trading penalty
            if self._trade_count > self.cfg["max_trades_per_day"]:
                pnl_reward += self.cfg["overtrade_penalty"]

            return pnl_reward

        def _sharpe_reward(self) -> float:
            """Differential Sharpe ratio over the lookback window."""
            lookback = self.cfg["reward_lookback"]
            if len(self._returns) < lookback:
                return 0.0

            recent = np.array(self._returns[-lookback:])
            mean_r = np.mean(recent)
            std_r = np.std(recent) + 1e-10
            return float(mean_r / std_r) * 0.1

else:
    # Stub when gymnasium is not installed
    class TradingEnv:  # type: ignore[no-redef]
        """Stub TradingEnv when gymnasium is not installed."""

        def __init__(self, *args: Any, **kwargs: Any) -> None:
            logger.warning(
                "gymnasium not installed — TradingEnv is a no-op stub"
            )

        def reset(self, **kwargs: Any) -> tuple:
            return np.zeros(1), {}

        def step(self, action: int) -> tuple:
            return np.zeros(1), 0.0, True, False, {}
