"""
Main trading engine.

Orchestrates the full trading cycle:
scan → score → risk check → execute.

Integrates strategy execution, signal scoring, risk management, and
order execution into a single cohesive workflow with anti-overtrading,
market-hours validation, and comprehensive logging.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional
from zoneinfo import ZoneInfo

import pandas as pd

from app.domain.trading.signal_scorer import ScoreBreakdown, SignalScorer
from app.domain.trading.strategies import BaseStrategy, Signal

logger = logging.getLogger(__name__)

IST = ZoneInfo("Asia/Kolkata")


# ═══════════════════════════════════════════════════════════════════════
# Data classes
# ═══════════════════════════════════════════════════════════════════════

@dataclass
class ScoredSignal:
    """A signal enriched with its score breakdown."""

    signal: Signal
    score: ScoreBreakdown
    should_trade: bool = False
    is_high_conviction: bool = False
    rejection_reasons: list[str] = field(default_factory=list)


@dataclass
class TradeResult:
    """Outcome of a trade execution attempt."""

    success: bool
    order_id: Optional[str] = None
    symbol: str = ""
    direction: str = ""
    quantity: int = 0
    fill_price: float = 0.0
    strategy: str = ""
    score: float = 0.0
    error: Optional[str] = None
    timestamp: str = field(
        default_factory=lambda: datetime.now(tz=IST).isoformat()
    )


@dataclass
class PortfolioStatus:
    """Snapshot of the current portfolio state."""

    total_capital: float = 0.0
    available_capital: float = 0.0
    invested_capital: float = 0.0
    open_positions: int = 0
    daily_pnl: float = 0.0
    total_pnl: float = 0.0
    positions: list[dict[str, Any]] = field(default_factory=list)
    timestamp: str = field(
        default_factory=lambda: datetime.now(tz=IST).isoformat()
    )


# ═══════════════════════════════════════════════════════════════════════
# Trading Engine
# ═══════════════════════════════════════════════════════════════════════

class TradingEngine:
    """Central orchestrator for the automated trading workflow.

    Responsibilities
    ----------------
    - Market scanning across symbols using registered strategies.
    - Signal evaluation via :class:`SignalScorer`.
    - Pre-trade risk checks delegated to the injected risk manager.
    - Order execution delegated to the injected order executor.
    - Open-position monitoring (stop-loss / take-profit updates,
      time-based exits).
    - Anti-overtrading enforcement.
    - Market-hours gating.

    Parameters
    ----------
    config : dict
        Trading configuration (capital, limits, etc.).
    risk_manager : object
        Instance with ``can_trade(signal, portfolio_state)`` and
        ``check_market_hours(market)`` methods.
    strategies : list[BaseStrategy]
        Strategies to scan with.
    scorer : SignalScorer
        Signal scoring engine.
    order_executor : object, optional
        Order executor with ``place_order(...)`` method.
    """

    def __init__(
        self,
        config: dict[str, Any],
        risk_manager: Any,
        strategies: list[BaseStrategy],
        scorer: SignalScorer,
        order_executor: Any = None,
    ) -> None:
        self._config = config
        self._risk_manager = risk_manager
        self._strategies = strategies
        self._scorer = scorer
        self._order_executor = order_executor

        # Runtime state
        self._trades_today: int = 0
        self._last_trade_time: Optional[datetime] = None
        self._traded_symbols_today: dict[str, datetime] = {}
        self._open_positions: list[dict[str, Any]] = []
        self._daily_pnl: float = 0.0

        logger.info(
            "TradingEngine initialised with %d strategies, capital=%.0f",
            len(strategies),
            config.get("capital", 0),
        )

    # ── Market scan ──────────────────────────────────────────────────

    def scan_market(
        self,
        symbols: dict[str, pd.DataFrame],
    ) -> list[Signal]:
        """Scan all *symbols* with every registered strategy.

        Parameters
        ----------
        symbols : dict[str, pd.DataFrame]
            Symbol name → OHLCV DataFrame.

        Returns
        -------
        list[Signal]
            Raw (un-scored) signals.
        """
        all_signals: list[Signal] = []

        for symbol, df in symbols.items():
            if df.empty:
                logger.debug("scan_market: skipping %s (empty data)", symbol)
                continue

            for strategy in self._strategies:
                try:
                    signal = strategy.generate_signal(df)
                    if signal is not None:
                        signal.symbol = symbol
                        signal.timeframe = strategy.timeframe
                        all_signals.append(signal)
                        logger.info(
                            "Signal generated: %s %s by %s (confidence=%.1f)",
                            signal.direction,
                            symbol,
                            strategy.name,
                            signal.confidence,
                        )
                except Exception:
                    logger.exception(
                        "Error generating signal for %s with %s",
                        symbol,
                        strategy.name,
                    )

        logger.info(
            "Market scan complete: %d symbols, %d signals generated",
            len(symbols),
            len(all_signals),
        )
        return all_signals

    # ── Signal evaluation ────────────────────────────────────────────

    def evaluate_signal(
        self,
        signal: Signal,
        indicators: Optional[dict[str, Any]] = None,
        sentiment: Optional[dict[str, Any]] = None,
        volume_data: Optional[dict[str, Any]] = None,
        regime: Optional[str] = None,
        macro: Optional[dict[str, Any]] = None,
    ) -> ScoredSignal:
        """Score a signal and decide whether to trade.

        Parameters
        ----------
        signal : Signal
        indicators, sentiment, volume_data, regime, macro : optional
            Additional context for the scorer.

        Returns
        -------
        ScoredSignal
        """
        signal_dict = {
            "direction": signal.direction,
            "strategy_name": signal.strategy_name,
            "entry": signal.entry,
            "stop_loss": signal.stop_loss,
            "target": signal.target,
        }
        score = self._scorer.score_signal(
            signal=signal_dict,
            indicators=indicators,
            sentiment=sentiment,
            volume_data=volume_data,
            regime=regime,
            macro=macro,
        )

        should = self._scorer.should_trade(score.total)
        high_conv = self._scorer.is_high_conviction(score.total)
        reasons: list[str] = []

        if not should:
            reasons.append(
                f"Score {score.total:.1f} below conviction threshold "
                f"{self._scorer._conviction_threshold}"
            )

        scored = ScoredSignal(
            signal=signal,
            score=score,
            should_trade=should,
            is_high_conviction=high_conv,
            rejection_reasons=reasons,
        )
        logger.info(
            "Signal evaluated: %s %s score=%.1f, trade=%s, high_conv=%s",
            signal.symbol,
            signal.direction,
            score.total,
            should,
            high_conv,
        )
        return scored

    # ── Trade execution ──────────────────────────────────────────────

    def execute_trade(self, scored_signal: ScoredSignal) -> TradeResult:
        """Execute a scored signal through the order executor.

        Pre-conditions checked:
        1. Signal score meets threshold.
        2. Risk manager approves.
        3. Anti-overtrading passes.

        Parameters
        ----------
        scored_signal : ScoredSignal

        Returns
        -------
        TradeResult
        """
        signal = scored_signal.signal

        if not scored_signal.should_trade:
            return TradeResult(
                success=False,
                symbol=signal.symbol,
                direction=signal.direction,
                strategy=signal.strategy_name,
                score=scored_signal.score.total,
                error="Signal did not meet conviction threshold",
            )

        # Risk manager check
        if self._risk_manager is not None:
            portfolio_state = self._get_portfolio_state()
            can_trade, reasons = self._risk_manager.can_trade(
                signal.__dict__, portfolio_state,
            )
            if not can_trade:
                reason_str = "; ".join(reasons)
                logger.warning(
                    "Trade rejected by risk manager: %s %s — %s",
                    signal.symbol,
                    signal.direction,
                    reason_str,
                )
                return TradeResult(
                    success=False,
                    symbol=signal.symbol,
                    direction=signal.direction,
                    strategy=signal.strategy_name,
                    score=scored_signal.score.total,
                    error=f"Risk check failed: {reason_str}",
                )

        # Anti-overtrading
        if self._trades_today >= self._config.get("max_trades_per_day", 5):
            msg = f"Daily trade limit reached ({self._trades_today})"
            logger.warning(msg)
            return TradeResult(
                success=False,
                symbol=signal.symbol,
                direction=signal.direction,
                strategy=signal.strategy_name,
                score=scored_signal.score.total,
                error=msg,
            )

        # Execute via order executor
        if self._order_executor is None:
            logger.warning("No order executor configured — simulating fill")
            order_id = f"SIM-{datetime.now(tz=IST).strftime('%Y%m%d%H%M%S')}"
            quantity = self._config.get("default_quantity", 1)
        else:
            try:
                result = self._order_executor.place_order(
                    symbol=signal.symbol,
                    direction=signal.direction,
                    quantity=self._config.get("default_quantity", 1),
                    price=signal.entry,
                    order_type="LIMIT",
                )
                order_id = result.get("order_id", "UNKNOWN")
                quantity = result.get("quantity", 1)
            except Exception as exc:
                logger.exception("Order execution failed for %s", signal.symbol)
                return TradeResult(
                    success=False,
                    symbol=signal.symbol,
                    direction=signal.direction,
                    strategy=signal.strategy_name,
                    score=scored_signal.score.total,
                    error=str(exc),
                )

        # Update state
        self._trades_today += 1
        self._last_trade_time = datetime.now(tz=IST)
        self._traded_symbols_today[signal.symbol] = self._last_trade_time

        self._open_positions.append({
            "symbol": signal.symbol,
            "direction": signal.direction,
            "entry": signal.entry,
            "stop_loss": signal.stop_loss,
            "target": signal.target,
            "quantity": quantity,
            "strategy": signal.strategy_name,
            "entry_time": self._last_trade_time.isoformat(),
            "order_id": order_id,
        })

        logger.info(
            "Trade executed: %s %s %d @ %.2f (order=%s, score=%.1f)",
            signal.direction,
            signal.symbol,
            quantity,
            signal.entry,
            order_id,
            scored_signal.score.total,
        )
        return TradeResult(
            success=True,
            order_id=order_id,
            symbol=signal.symbol,
            direction=signal.direction,
            quantity=quantity,
            fill_price=signal.entry,
            strategy=signal.strategy_name,
            score=scored_signal.score.total,
        )

    # ── Position monitoring ──────────────────────────────────────────

    def check_open_positions(
        self,
        current_prices: dict[str, float],
    ) -> list[dict[str, Any]]:
        """Check all open positions for SL / TP hits and time exits.

        Parameters
        ----------
        current_prices : dict[str, float]
            Symbol → current LTP.

        Returns
        -------
        list[dict]
            Actions taken (exits, SL updates, etc.).
        """
        actions: list[dict[str, Any]] = []

        for pos in list(self._open_positions):
            symbol = pos["symbol"]
            ltp = current_prices.get(symbol)
            if ltp is None:
                continue

            direction = pos["direction"]
            entry = pos["entry"]
            sl = pos["stop_loss"]
            tp = pos["target"]

            # Check stop-loss hit
            sl_hit = (direction == "BUY" and ltp <= sl) or \
                     (direction == "SELL" and ltp >= sl)

            # Check take-profit hit
            tp_hit = (direction == "BUY" and ltp >= tp) or \
                     (direction == "SELL" and ltp <= tp)

            # Time-based exit (3 days max)
            entry_time = datetime.fromisoformat(pos["entry_time"])
            now = datetime.now(tz=IST)
            days_held = (now - entry_time).total_seconds() / 86400

            if sl_hit:
                pnl = (sl - entry) * pos["quantity"] if direction == "BUY" else (entry - sl) * pos["quantity"]
                action = {
                    "type": "EXIT",
                    "reason": "STOP_LOSS",
                    "symbol": symbol,
                    "exit_price": sl,
                    "pnl": round(pnl, 2),
                }
                self._open_positions.remove(pos)
                self._daily_pnl += pnl
                actions.append(action)
                logger.info("SL hit: %s @ %.2f, PnL=%.2f", symbol, sl, pnl)

            elif tp_hit:
                pnl = (tp - entry) * pos["quantity"] if direction == "BUY" else (entry - tp) * pos["quantity"]
                action = {
                    "type": "EXIT",
                    "reason": "TAKE_PROFIT",
                    "symbol": symbol,
                    "exit_price": tp,
                    "pnl": round(pnl, 2),
                }
                self._open_positions.remove(pos)
                self._daily_pnl += pnl
                actions.append(action)
                logger.info("TP hit: %s @ %.2f, PnL=%.2f", symbol, tp, pnl)

            elif days_held > 3:
                pnl = (ltp - entry) * pos["quantity"] if direction == "BUY" else (entry - ltp) * pos["quantity"]
                action = {
                    "type": "EXIT",
                    "reason": "TIME_EXIT",
                    "symbol": symbol,
                    "exit_price": ltp,
                    "pnl": round(pnl, 2),
                    "days_held": round(days_held, 1),
                }
                self._open_positions.remove(pos)
                self._daily_pnl += pnl
                actions.append(action)
                logger.info(
                    "Time exit: %s after %.1f days, PnL=%.2f",
                    symbol, days_held, pnl,
                )

        return actions

    # ── Portfolio status ─────────────────────────────────────────────

    def get_portfolio_status(self) -> PortfolioStatus:
        """Return a snapshot of the current portfolio."""
        capital = self._config.get("capital", 1_000_000)
        invested = sum(
            p["entry"] * p["quantity"] for p in self._open_positions
        )
        return PortfolioStatus(
            total_capital=capital,
            available_capital=capital - invested,
            invested_capital=invested,
            open_positions=len(self._open_positions),
            daily_pnl=round(self._daily_pnl, 2),
            total_pnl=round(self._daily_pnl, 2),  # simplified
            positions=self._open_positions.copy(),
        )

    # ── Full trading cycle ───────────────────────────────────────────

    def run_cycle(
        self,
        symbols: dict[str, pd.DataFrame],
        current_prices: Optional[dict[str, float]] = None,
        market: str = "NSE",
    ) -> dict[str, Any]:
        """Execute a complete scan → score → risk → execute cycle.

        Parameters
        ----------
        symbols : dict[str, pd.DataFrame]
            Symbol → OHLCV data.
        current_prices : dict, optional
            Current LTPs for position monitoring.
        market : str, default "NSE"

        Returns
        -------
        dict
            Summary of actions taken in this cycle.
        """
        now = datetime.now(tz=IST)
        logger.info("═══ Trading cycle started at %s ═══", now.isoformat())

        # Market hours check
        if self._risk_manager is not None:
            if not self._risk_manager.check_market_hours(market):
                logger.info("Market closed — skipping cycle")
                return {
                    "status": "MARKET_CLOSED",
                    "timestamp": now.isoformat(),
                    "signals": [],
                    "trades": [],
                    "position_actions": [],
                }

        # 1. Check open positions
        position_actions: list[dict[str, Any]] = []
        if current_prices:
            position_actions = self.check_open_positions(current_prices)

        # 2. Scan market
        signals = self.scan_market(symbols)

        # 3. Evaluate and execute
        trades: list[TradeResult] = []
        for signal in signals:
            scored = self.evaluate_signal(signal)
            if scored.should_trade:
                result = self.execute_trade(scored)
                trades.append(result)

        summary = {
            "status": "COMPLETED",
            "timestamp": now.isoformat(),
            "signals_generated": len(signals),
            "trades_attempted": len(trades),
            "trades_successful": sum(1 for t in trades if t.success),
            "position_actions": position_actions,
            "open_positions": len(self._open_positions),
            "daily_pnl": round(self._daily_pnl, 2),
        }
        logger.info(
            "═══ Trading cycle complete: %d signals, %d trades, %d exits ═══",
            len(signals),
            len(trades),
            len(position_actions),
        )
        return summary

    # ── Internal helpers ─────────────────────────────────────────────

    def _get_portfolio_state(self) -> dict[str, Any]:
        """Build a portfolio state dict for risk-manager checks."""
        capital = self._config.get("capital", 1_000_000)
        return {
            "capital": capital,
            "daily_pnl": self._daily_pnl,
            "trades_today": self._trades_today,
            "open_positions": len(self._open_positions),
            "positions": self._open_positions.copy(),
            "last_trade_time": (
                self._last_trade_time.isoformat()
                if self._last_trade_time
                else None
            ),
            "traded_symbols_today": {
                k: v.isoformat()
                for k, v in self._traded_symbols_today.items()
            },
        }

    def reset_daily_state(self) -> None:
        """Reset counters at the start of a new trading day."""
        self._trades_today = 0
        self._last_trade_time = None
        self._traded_symbols_today.clear()
        self._daily_pnl = 0.0
        logger.info("Daily trading state reset")
