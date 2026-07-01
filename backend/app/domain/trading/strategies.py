"""
Trading strategies.

Defines a ``BaseStrategy`` abstract class and concrete strategy
implementations covering trend-following, mean-reversion, momentum
breakout, scalping, swing trading, and options strategies.

Each strategy's :meth:`generate_signal` returns a signal dict with
``direction``, ``entry``, ``stop_loss``, ``target``,
``strategy_name``, and ``confidence``, or ``None`` if no actionable
signal exists.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from app.domain.indicators.technical import (
    atr,
    bollinger_bands,
    ema,
    macd,
    rsi,
    supertrend,
    volume_sma_ratio,
    vwap,
    adx as calc_adx,
    is_near_52_week_high,
    stochastic,
)

logger = logging.getLogger(__name__)

IST = ZoneInfo("Asia/Kolkata")


# ═══════════════════════════════════════════════════════════════════════
# Signal & backtest data classes
# ═══════════════════════════════════════════════════════════════════════

@dataclass
class Signal:
    """Represents a trading signal produced by a strategy."""

    direction: str  # "BUY" or "SELL"
    entry: float
    stop_loss: float
    target: float
    strategy_name: str
    confidence: float  # 0 – 100
    symbol: str = ""
    timeframe: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now(tz=IST).isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class BacktestResult:
    """Summary of a strategy back-test run."""

    strategy_name: str
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    win_rate: float = 0.0
    total_pnl: float = 0.0
    max_drawdown: float = 0.0
    sharpe_ratio: float = 0.0
    profit_factor: float = 0.0
    final_capital: float = 0.0
    trades: list[dict[str, Any]] = field(default_factory=list)


# ═══════════════════════════════════════════════════════════════════════
# Base class
# ═══════════════════════════════════════════════════════════════════════

class BaseStrategy(ABC):
    """Abstract base for all trading strategies.

    Subclasses must implement :meth:`generate_signal`.
    """

    name: str = "base"
    timeframe: str = "1d"

    @abstractmethod
    def generate_signal(
        self,
        df: pd.DataFrame,
        indicators: Optional[dict[str, Any]] = None,
    ) -> Optional[Signal]:
        """Produce a signal from the given OHLCV data.

        Parameters
        ----------
        df : pd.DataFrame
            OHLCV data for a single symbol.
        indicators : dict, optional
            Pre-computed indicator values.

        Returns
        -------
        Signal or None
        """
        ...

    # ── Simple vectorised back-test ──────────────────────────────────

    def backtest(
        self,
        df: pd.DataFrame,
        initial_capital: float = 1_000_000.0,
    ) -> BacktestResult:
        """Run a naive walk-forward back-test over *df*.

        This is a simplified event-based loop: for each bar, attempt to
        generate a signal and simulate the trade outcome using fixed
        risk-reward from the signal.

        Parameters
        ----------
        df : pd.DataFrame
            Full OHLCV history.
        initial_capital : float
            Starting capital.

        Returns
        -------
        BacktestResult
        """
        capital = initial_capital
        peak_capital = capital
        max_dd = 0.0
        trades: list[dict[str, Any]] = []
        wins = 0
        losses = 0
        gross_profit = 0.0
        gross_loss = 0.0

        min_bars = 50  # need enough history for indicators
        step = 5  # evaluate every 5 bars to avoid look-ahead

        for i in range(min_bars, len(df), step):
            window = df.iloc[: i + 1].copy()
            signal = self.generate_signal(window)

            if signal is None:
                continue

            # Simulate trade with the next bar's open (or close)
            if i + 1 >= len(df):
                break
            fill_price = signal.entry
            sl = signal.stop_loss
            tp = signal.target

            # Determine outcome by scanning forward bars
            hit_tp = False
            hit_sl = False
            exit_price = fill_price

            for j in range(i + 1, min(i + 20, len(df))):  # max 20 bars
                bar = df.iloc[j]
                if signal.direction == "BUY":
                    if bar["low"] <= sl:
                        hit_sl = True
                        exit_price = sl
                        break
                    if bar["high"] >= tp:
                        hit_tp = True
                        exit_price = tp
                        break
                else:  # SELL
                    if bar["high"] >= sl:
                        hit_sl = True
                        exit_price = sl
                        break
                    if bar["low"] <= tp:
                        hit_tp = True
                        exit_price = tp
                        break
                exit_price = bar["close"]

            # PnL
            if signal.direction == "BUY":
                pnl = exit_price - fill_price
            else:
                pnl = fill_price - exit_price

            risk_amount = capital * 0.01  # 1 % risk
            trade_risk = abs(fill_price - sl) if abs(fill_price - sl) > 0 else 1.0
            qty = max(1, int(risk_amount / trade_risk))
            trade_pnl = pnl * qty

            capital += trade_pnl
            peak_capital = max(peak_capital, capital)
            drawdown = (peak_capital - capital) / peak_capital if peak_capital > 0 else 0
            max_dd = max(max_dd, drawdown)

            if trade_pnl > 0:
                wins += 1
                gross_profit += trade_pnl
            else:
                losses += 1
                gross_loss += abs(trade_pnl)

            trades.append({
                "bar_index": i,
                "direction": signal.direction,
                "entry": fill_price,
                "exit": exit_price,
                "pnl": round(trade_pnl, 2),
                "hit_tp": hit_tp,
                "hit_sl": hit_sl,
            })

        total = wins + losses
        win_rate = (wins / total * 100) if total > 0 else 0.0
        pf = (gross_profit / gross_loss) if gross_loss > 0 else float("inf")

        # Sharpe approximation from trade returns
        trade_returns = [t["pnl"] / initial_capital for t in trades]
        sharpe = 0.0
        if trade_returns:
            arr = np.array(trade_returns)
            if arr.std() > 0:
                sharpe = float(arr.mean() / arr.std() * np.sqrt(252))

        result = BacktestResult(
            strategy_name=self.name,
            total_trades=total,
            winning_trades=wins,
            losing_trades=losses,
            win_rate=round(win_rate, 2),
            total_pnl=round(capital - initial_capital, 2),
            max_drawdown=round(max_dd * 100, 2),
            sharpe_ratio=round(sharpe, 2),
            profit_factor=round(pf, 2),
            final_capital=round(capital, 2),
            trades=trades,
        )
        logger.info(
            "Backtest %s: %d trades, win_rate=%.1f%%, PnL=%.2f, maxDD=%.1f%%",
            self.name,
            total,
            win_rate,
            result.total_pnl,
            result.max_drawdown,
        )
        return result


# ═══════════════════════════════════════════════════════════════════════
# Concrete strategies
# ═══════════════════════════════════════════════════════════════════════


class TrendFollowingStrategy(BaseStrategy):
    """EMA(9) × EMA(21) crossover confirmed by Supertrend and ADX > 25.

    Entry : when EMA-9 crosses above EMA-21 AND Supertrend is bullish
            AND ADX > 25.
    SL    : at the Supertrend level.
    Target: 2× the risk (entry − SL).
    """

    name = "trend_following"
    timeframe = "1d"

    def generate_signal(
        self,
        df: pd.DataFrame,
        indicators: Optional[dict[str, Any]] = None,
    ) -> Optional[Signal]:
        """Generate a trend-following signal."""
        if df.empty or len(df) < 30:
            return None

        close = df["close"]
        ema9 = ema(close, 9)
        ema21 = ema(close, 21)

        # Check EMA crossover (current bar)
        if len(ema9) < 2 or len(ema21) < 2:
            return None

        cross_up = ema9.iloc[-1] > ema21.iloc[-1] and ema9.iloc[-2] <= ema21.iloc[-2]
        cross_down = ema9.iloc[-1] < ema21.iloc[-1] and ema9.iloc[-2] >= ema21.iloc[-2]

        if not (cross_up or cross_down):
            return None

        # Supertrend confirmation
        st_line, st_dir = supertrend(df)
        if st_line.empty:
            return None
        latest_st = st_line.iloc[-1]
        latest_dir = st_dir.iloc[-1]

        # ADX check
        adx_vals, _, _ = calc_adx(df, 14)
        latest_adx = adx_vals.iloc[-1] if not adx_vals.empty else 0

        if np.isnan(latest_adx) or latest_adx < 25:
            return None

        entry = close.iloc[-1]

        if cross_up and latest_dir == 1:  # bullish
            sl = latest_st if not np.isnan(latest_st) else entry * 0.97
            risk = entry - sl
            tp = entry + 2 * risk if risk > 0 else entry * 1.04
            direction = "BUY"
            confidence = min(50 + latest_adx, 95)
        elif cross_down and latest_dir == -1:  # bearish
            sl = latest_st if not np.isnan(latest_st) else entry * 1.03
            risk = sl - entry
            tp = entry - 2 * risk if risk > 0 else entry * 0.96
            direction = "SELL"
            confidence = min(50 + latest_adx, 95)
        else:
            return None

        logger.info(
            "TrendFollowing signal: %s @ %.2f, SL=%.2f, TP=%.2f, ADX=%.1f",
            direction,
            entry,
            sl,
            tp,
            latest_adx,
        )
        return Signal(
            direction=direction,
            entry=round(entry, 2),
            stop_loss=round(sl, 2),
            target=round(tp, 2),
            strategy_name=self.name,
            confidence=round(confidence, 1),
            metadata={"adx": round(latest_adx, 2), "supertrend": round(latest_st, 2)},
        )


class MeanReversionStrategy(BaseStrategy):
    """Bollinger-Band squeeze/expansion combined with RSI divergence.

    Entry : price touches or pierces lower BB while RSI shows higher
            low (bullish divergence).
    SL    : below the lower BB by one ATR.
    Target: middle BB (mean-reversion target).
    """

    name = "mean_reversion"
    timeframe = "1d"

    def generate_signal(
        self,
        df: pd.DataFrame,
        indicators: Optional[dict[str, Any]] = None,
    ) -> Optional[Signal]:
        """Generate a mean-reversion signal."""
        if df.empty or len(df) < 30:
            return None

        close = df["close"]
        upper, middle, lower, bandwidth, pct_b = bollinger_bands(close)
        rsi_vals = rsi(close)

        if any(s.isna().all() for s in [upper, lower, rsi_vals]):
            return None

        latest_close = close.iloc[-1]
        latest_lower = lower.iloc[-1]
        latest_upper = upper.iloc[-1]
        latest_middle = middle.iloc[-1]
        latest_rsi = rsi_vals.iloc[-1]
        latest_bandwidth = bandwidth.iloc[-1]

        # Squeeze detection: bandwidth below 20th percentile
        bw_valid = bandwidth.dropna()
        if len(bw_valid) < 10:
            return None
        squeeze = latest_bandwidth < bw_valid.quantile(0.20)

        # BUY: price near/below lower BB + RSI < 35 (oversold)
        if latest_close <= latest_lower * 1.005 and latest_rsi < 35:
            from app.domain.indicators.technical import atr as calc_atr

            atr_val = calc_atr(df).iloc[-1]
            atr_val = atr_val if not np.isnan(atr_val) else latest_close * 0.015

            entry = latest_close
            sl = latest_lower - atr_val
            tp = latest_middle
            confidence = 60.0
            if squeeze:
                confidence += 10
            if latest_rsi < 25:
                confidence += 10

            logger.info(
                "MeanReversion BUY: entry=%.2f, SL=%.2f, TP=%.2f, RSI=%.1f, BW=%.4f",
                entry, sl, tp, latest_rsi, latest_bandwidth,
            )
            return Signal(
                direction="BUY",
                entry=round(entry, 2),
                stop_loss=round(sl, 2),
                target=round(tp, 2),
                strategy_name=self.name,
                confidence=round(confidence, 1),
                metadata={
                    "rsi": round(latest_rsi, 2),
                    "bandwidth": round(latest_bandwidth, 4),
                    "squeeze": squeeze,
                },
            )

        # SELL: price near/above upper BB + RSI > 65 (overbought)
        if latest_close >= latest_upper * 0.995 and latest_rsi > 65:
            from app.domain.indicators.technical import atr as calc_atr

            atr_val = calc_atr(df).iloc[-1]
            atr_val = atr_val if not np.isnan(atr_val) else latest_close * 0.015

            entry = latest_close
            sl = latest_upper + atr_val
            tp = latest_middle
            confidence = 60.0
            if squeeze:
                confidence += 10
            if latest_rsi > 75:
                confidence += 10

            logger.info(
                "MeanReversion SELL: entry=%.2f, SL=%.2f, TP=%.2f, RSI=%.1f",
                entry, sl, tp, latest_rsi,
            )
            return Signal(
                direction="SELL",
                entry=round(entry, 2),
                stop_loss=round(sl, 2),
                target=round(tp, 2),
                strategy_name=self.name,
                confidence=round(confidence, 1),
                metadata={
                    "rsi": round(latest_rsi, 2),
                    "bandwidth": round(latest_bandwidth, 4),
                    "squeeze": squeeze,
                },
            )

        return None


class MomentumBreakoutStrategy(BaseStrategy):
    """52-week-high breakout on elevated volume.

    Entry : price breaks above 52-week high AND volume > 2× SMA(20).
    SL    : previous resistance level (previous day's close).
    Target: entry + 1.5× risk.
    """

    name = "momentum_breakout"
    timeframe = "1d"

    def generate_signal(
        self,
        df: pd.DataFrame,
        indicators: Optional[dict[str, Any]] = None,
    ) -> Optional[Signal]:
        """Generate a momentum breakout signal."""
        if df.empty or len(df) < 60:
            return None

        close = df["close"]
        vol_ratio = volume_sma_ratio(df, 20)

        near_high = is_near_52_week_high(df, threshold=0.005)

        if near_high.empty or vol_ratio.empty:
            return None

        latest_near_high = near_high.iloc[-1]
        latest_vol_ratio = vol_ratio.iloc[-1]

        if not latest_near_high or np.isnan(latest_vol_ratio) or latest_vol_ratio < 2.0:
            return None

        # Previous 52-week high
        period = min(252, len(close) - 1)
        prev_high = close.iloc[:-1].rolling(window=period, min_periods=1).max().iloc[-1]
        entry = close.iloc[-1]

        # Only trigger if actually breaking *above*
        if entry <= prev_high:
            return None

        sl = df["close"].iloc[-2]  # previous close as support
        risk = entry - sl
        if risk <= 0:
            return None
        tp = entry + 1.5 * risk

        confidence = 65.0
        if latest_vol_ratio > 3.0:
            confidence += 10
        if latest_vol_ratio > 5.0:
            confidence += 10

        logger.info(
            "MomentumBreakout BUY: entry=%.2f, SL=%.2f, TP=%.2f, vol_ratio=%.1f",
            entry, sl, tp, latest_vol_ratio,
        )
        return Signal(
            direction="BUY",
            entry=round(entry, 2),
            stop_loss=round(sl, 2),
            target=round(tp, 2),
            strategy_name=self.name,
            confidence=round(confidence, 1),
            metadata={
                "volume_ratio": round(latest_vol_ratio, 2),
                "prev_52w_high": round(prev_high, 2),
            },
        )


class ScalpingStrategy(BaseStrategy):
    """Intra-day VWAP bounce with RSI confirmation.

    Timeframe: 1-minute / 5-minute charts.
    Entry    : price bounces off VWAP + RSI oversold (< 30).
    Target   : 0.5 – 1 % quick profit.
    SL       : 0.3 % below entry.
    """

    name = "scalping"
    timeframe = "1m"

    def generate_signal(
        self,
        df: pd.DataFrame,
        indicators: Optional[dict[str, Any]] = None,
    ) -> Optional[Signal]:
        """Generate a scalping signal."""
        if df.empty or len(df) < 20:
            return None

        close = df["close"]
        vwap_vals = vwap(df)
        rsi_vals = rsi(close, period=7)  # shorter RSI for scalping

        if vwap_vals.empty or rsi_vals.empty:
            return None

        latest_close = close.iloc[-1]
        latest_vwap = vwap_vals.iloc[-1]
        latest_rsi = rsi_vals.iloc[-1]

        if np.isnan(latest_vwap) or np.isnan(latest_rsi):
            return None

        vwap_distance_pct = ((latest_close - latest_vwap) / latest_vwap) * 100 if latest_vwap else 0

        # BUY: price within 0.15 % of VWAP from below + RSI < 30
        if -0.15 <= vwap_distance_pct <= 0.05 and latest_rsi < 30:
            entry = latest_close
            sl = entry * 0.997  # 0.3 % SL
            tp = entry * 1.007  # 0.7 % target
            confidence = 55.0 + (30 - latest_rsi)  # lower RSI → more confident

            logger.info(
                "Scalping BUY: entry=%.2f, VWAP=%.2f, RSI=%.1f",
                entry, latest_vwap, latest_rsi,
            )
            return Signal(
                direction="BUY",
                entry=round(entry, 2),
                stop_loss=round(sl, 2),
                target=round(tp, 2),
                strategy_name=self.name,
                confidence=round(min(confidence, 90), 1),
                metadata={
                    "vwap": round(latest_vwap, 2),
                    "rsi": round(latest_rsi, 2),
                    "vwap_distance_pct": round(vwap_distance_pct, 3),
                },
            )

        # SELL: price bounces down from VWAP from above + RSI > 70
        if -0.05 <= vwap_distance_pct <= 0.15 and latest_rsi > 70:
            entry = latest_close
            sl = entry * 1.003
            tp = entry * 0.993
            confidence = 55.0 + (latest_rsi - 70)

            logger.info(
                "Scalping SELL: entry=%.2f, VWAP=%.2f, RSI=%.1f",
                entry, latest_vwap, latest_rsi,
            )
            return Signal(
                direction="SELL",
                entry=round(entry, 2),
                stop_loss=round(sl, 2),
                target=round(tp, 2),
                strategy_name=self.name,
                confidence=round(min(confidence, 90), 1),
                metadata={
                    "vwap": round(latest_vwap, 2),
                    "rsi": round(latest_rsi, 2),
                    "vwap_distance_pct": round(vwap_distance_pct, 3),
                },
            )

        return None


class SwingTradingStrategy(BaseStrategy):
    """Multi-timeframe swing trade: daily trend + higher-high /
    higher-low pattern on the entry timeframe.

    Hold period : 3 – 10 days.
    Entry       : higher-low confirmation on 4H while daily EMA(50) is
                  trending up.
    SL          : below the recent swing low.
    Target      : 2× risk.
    """

    name = "swing"
    timeframe = "4h"

    def generate_signal(
        self,
        df: pd.DataFrame,
        indicators: Optional[dict[str, Any]] = None,
    ) -> Optional[Signal]:
        """Generate a swing-trading signal (single timeframe
        approximation — real MTF requires two DataFrames).
        """
        if df.empty or len(df) < 60:
            return None

        close = df["close"]
        low = df["low"]
        high = df["high"]

        ema50 = ema(close, 50)
        ema200 = ema(close, 200)
        rsi_vals = rsi(close, 14)

        if any(s.isna().all() for s in [ema50, ema200]):
            return None

        latest_close = close.iloc[-1]
        latest_ema50 = ema50.iloc[-1]
        latest_ema200 = ema200.iloc[-1]
        latest_rsi = rsi_vals.iloc[-1] if not rsi_vals.isna().all() else 50

        # Daily trend: EMA50 > EMA200 (bullish) and rising EMA50
        if np.isnan(latest_ema50) or np.isnan(latest_ema200):
            return None

        bullish_trend = latest_ema50 > latest_ema200
        bearish_trend = latest_ema50 < latest_ema200

        # Higher-high / higher-low detection (last 10 bars)
        lookback = min(10, len(df) - 1)
        recent_lows = low.iloc[-lookback:].values
        recent_highs = high.iloc[-lookback:].values

        # BUY: bullish trend + price making higher lows + RSI 40-60 (pullback zone)
        if bullish_trend and latest_close > latest_ema50:
            if len(recent_lows) >= 3:
                hl = recent_lows[-1] > recent_lows[0]  # higher low (simplified)
            else:
                hl = False

            if hl and 35 < latest_rsi < 65:
                swing_low = float(np.min(recent_lows))
                entry = latest_close
                sl = swing_low * 0.995
                risk = entry - sl
                if risk <= 0:
                    return None
                tp = entry + 2 * risk
                confidence = 65.0
                if latest_rsi < 50:
                    confidence += 10  # buying on pullback

                logger.info(
                    "Swing BUY: entry=%.2f, SL=%.2f, TP=%.2f",
                    entry, sl, tp,
                )
                return Signal(
                    direction="BUY",
                    entry=round(entry, 2),
                    stop_loss=round(sl, 2),
                    target=round(tp, 2),
                    strategy_name=self.name,
                    confidence=round(confidence, 1),
                    metadata={
                        "ema50": round(latest_ema50, 2),
                        "ema200": round(latest_ema200, 2),
                        "rsi": round(latest_rsi, 2),
                        "swing_low": round(swing_low, 2),
                    },
                )

        # SELL: bearish trend + lower-highs
        if bearish_trend and latest_close < latest_ema50:
            if len(recent_highs) >= 3:
                lh = recent_highs[-1] < recent_highs[0]  # lower high
            else:
                lh = False

            if lh and 35 < latest_rsi < 65:
                swing_high = float(np.max(recent_highs))
                entry = latest_close
                sl = swing_high * 1.005
                risk = sl - entry
                if risk <= 0:
                    return None
                tp = entry - 2 * risk
                confidence = 65.0
                if latest_rsi > 50:
                    confidence += 10

                logger.info(
                    "Swing SELL: entry=%.2f, SL=%.2f, TP=%.2f",
                    entry, sl, tp,
                )
                return Signal(
                    direction="SELL",
                    entry=round(entry, 2),
                    stop_loss=round(sl, 2),
                    target=round(tp, 2),
                    strategy_name=self.name,
                    confidence=round(confidence, 1),
                    metadata={
                        "ema50": round(latest_ema50, 2),
                        "ema200": round(latest_ema200, 2),
                        "rsi": round(latest_rsi, 2),
                        "swing_high": round(swing_high, 2),
                    },
                )

        return None


class OptionsStrategy(BaseStrategy):
    """NIFTY / BANKNIFTY option-strategy selector.

    Chooses the appropriate spread based on directional view and
    implied volatility (IV):

    - Bullish + reasonable IV  → Bull Call Spread
    - Bearish + reasonable IV  → Bear Put Spread
    - Sideways / high IV       → Iron Condor or sell OTM
    - Very high IV (> 20 %)    → Sell OTM (naked / covered)

    This strategy returns a *synthetic* signal with suggested legs
    encoded in metadata.  Actual option-chain data should be injected
    via ``indicators``.
    """

    name = "options"
    timeframe = "1d"

    def generate_signal(
        self,
        df: pd.DataFrame,
        indicators: Optional[dict[str, Any]] = None,
    ) -> Optional[Signal]:
        """Generate an options strategy recommendation."""
        if df.empty or len(df) < 30:
            return None

        close = df["close"]
        rsi_vals = rsi(close, 14)
        adx_vals, _, _ = calc_adx(df, 14)
        macd_line, signal_line, histogram = macd(close)

        latest_close = close.iloc[-1]
        latest_rsi = rsi_vals.iloc[-1] if not rsi_vals.isna().all() else 50
        latest_adx = adx_vals.iloc[-1] if not adx_vals.isna().all() else 15
        latest_histogram = histogram.iloc[-1] if not histogram.isna().all() else 0

        # Implied volatility from indicators dict (mock if absent)
        iv = 18.0  # default moderate IV
        if indicators and "iv" in indicators:
            iv = float(indicators["iv"])

        # Directional bias
        bullish = latest_rsi < 55 and latest_histogram > 0
        bearish = latest_rsi > 45 and latest_histogram < 0
        sideways = latest_adx < 20

        # Very high IV → sell premium
        if iv > 20:
            direction = "SELL"
            strategy_type = "SELL_OTM"
            entry = latest_close
            sl = entry * 1.03
            tp = entry  # premium decay is the target
            confidence = 70.0
            legs = {
                "strategy_type": strategy_type,
                "iv": iv,
                "suggestion": "Sell OTM Call + OTM Put (short strangle/straddle)",
            }
        elif sideways:
            direction = "SELL"
            strategy_type = "IRON_CONDOR"
            entry = latest_close
            sl = entry * 1.04
            tp = entry
            confidence = 65.0
            legs = {
                "strategy_type": strategy_type,
                "iv": iv,
                "suggestion": "Iron Condor — sell OTM call spread + OTM put spread",
            }
        elif bullish:
            direction = "BUY"
            strategy_type = "BULL_CALL_SPREAD"
            entry = latest_close
            sl = entry * 0.97
            tp = entry * 1.03
            confidence = 60.0
            legs = {
                "strategy_type": strategy_type,
                "iv": iv,
                "suggestion": "Buy ATM Call + Sell OTM Call",
            }
        elif bearish:
            direction = "SELL"
            strategy_type = "BEAR_PUT_SPREAD"
            entry = latest_close
            sl = entry * 1.03
            tp = entry * 0.97
            confidence = 60.0
            legs = {
                "strategy_type": strategy_type,
                "iv": iv,
                "suggestion": "Buy ATM Put + Sell OTM Put",
            }
        else:
            return None

        logger.info(
            "Options %s: %s @ %.2f, IV=%.1f%%, ADX=%.1f, RSI=%.1f",
            strategy_type, direction, entry, iv, latest_adx, latest_rsi,
        )
        return Signal(
            direction=direction,
            entry=round(entry, 2),
            stop_loss=round(sl, 2),
            target=round(tp, 2),
            strategy_name=self.name,
            confidence=round(confidence, 1),
            metadata=legs,
        )


# ═══════════════════════════════════════════════════════════════════════
# Factory
# ═══════════════════════════════════════════════════════════════════════

_ALL_STRATEGIES: dict[str, type[BaseStrategy]] = {
    "trend_following": TrendFollowingStrategy,
    "mean_reversion": MeanReversionStrategy,
    "momentum_breakout": MomentumBreakoutStrategy,
    "scalping": ScalpingStrategy,
    "swing": SwingTradingStrategy,
    "options": OptionsStrategy,
}


def get_strategy(name: str) -> BaseStrategy:
    """Instantiate a strategy by name.

    Parameters
    ----------
    name : str
        One of the registered strategy keys.

    Returns
    -------
    BaseStrategy

    Raises
    ------
    ValueError
        If the name is not recognised.
    """
    cls = _ALL_STRATEGIES.get(name)
    if cls is None:
        raise ValueError(
            f"Unknown strategy '{name}'. Available: {list(_ALL_STRATEGIES)}"
        )
    return cls()


def get_all_strategies() -> list[BaseStrategy]:
    """Return instances of every registered strategy."""
    return [cls() for cls in _ALL_STRATEGIES.values()]
