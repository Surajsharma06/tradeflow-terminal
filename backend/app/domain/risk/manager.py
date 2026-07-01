"""
Master risk manager.

Enforces daily / weekly / monthly loss limits, drawdown protocols,
consecutive-loss sizing rules, anti-overtrading checks, and
market-hours gating.  The :meth:`can_trade` method is the single
entry-point used by the trading engine before every trade attempt.
"""

from __future__ import annotations

import logging
from datetime import datetime, time
from typing import Any, Optional
from zoneinfo import ZoneInfo

from app.core.constants import MARKET_HOURS

logger = logging.getLogger(__name__)

IST = ZoneInfo("Asia/Kolkata")


class RiskManager:
    """Central risk-management gateway.

    All limits are loaded from *config* at construction time.  Sensible
    defaults are used when keys are absent.

    Config keys
    -----------
    - ``max_daily_loss_pct``   (default 3.0)
    - ``max_weekly_loss_pct``  (default 7.0)
    - ``max_monthly_loss_pct`` (default 15.0)
    - ``max_trades_per_day``   (default 5)
    - ``same_stock_cooldown_hours`` (default 4)
    - ``skip_first_minutes``   (default 15)
    - ``skip_last_minutes``    (default 10)
    - ``capital``              (default 1_000_000)
    - ``conviction_threshold`` (default 72)
    """

    def __init__(self, config: dict[str, Any]) -> None:
        self._config = config
        self._max_daily = config.get("max_daily_loss_pct", 3.0)
        self._max_weekly = config.get("max_weekly_loss_pct", 7.0)
        self._max_monthly = config.get("max_monthly_loss_pct", 15.0)
        self._max_trades = config.get("max_trades_per_day", 5)
        self._cooldown_hours = config.get("same_stock_cooldown_hours", 4)
        self._skip_first_min = config.get("skip_first_minutes", 15)
        self._skip_last_min = config.get("skip_last_minutes", 10)
        self._capital = config.get("capital", 1_000_000.0)
        self._conviction_threshold = config.get("conviction_threshold", 72)

        logger.info(
            "RiskManager initialised: daily=%.1f%%, weekly=%.1f%%, "
            "monthly=%.1f%%, max_trades=%d",
            self._max_daily, self._max_weekly,
            self._max_monthly, self._max_trades,
        )

    # ── Loss limits ──────────────────────────────────────────────────

    def check_daily_loss_limit(
        self,
        daily_pnl: float,
        capital: Optional[float] = None,
    ) -> tuple[bool, str]:
        """Return ``(ok, reason)``.  ``ok=True`` means within limit.

        Parameters
        ----------
        daily_pnl : float
            Cumulative realised + unrealised PnL today (₹).
        capital : float, optional
            Override capital from config.
        """
        cap = capital or self._capital
        if cap <= 0:
            return False, "Capital is zero"
        loss_pct = abs(min(0, daily_pnl)) / cap * 100
        if loss_pct >= self._max_daily:
            msg = (
                f"Daily loss limit breached: -{loss_pct:.1f}% "
                f"(limit {self._max_daily}%)"
            )
            logger.warning(msg)
            return False, msg
        return True, f"Daily loss at {loss_pct:.1f}% (limit {self._max_daily}%)"

    def check_weekly_loss_limit(
        self,
        weekly_pnl: float,
        capital: Optional[float] = None,
    ) -> tuple[bool, str]:
        """Return ``(ok, reason)``."""
        cap = capital or self._capital
        if cap <= 0:
            return False, "Capital is zero"
        loss_pct = abs(min(0, weekly_pnl)) / cap * 100
        if loss_pct >= self._max_weekly:
            msg = (
                f"Weekly loss limit breached: -{loss_pct:.1f}% "
                f"(limit {self._max_weekly}%)"
            )
            logger.warning(msg)
            return False, msg
        return True, f"Weekly loss at {loss_pct:.1f}% (limit {self._max_weekly}%)"

    def check_monthly_loss_limit(
        self,
        monthly_pnl: float,
        capital: Optional[float] = None,
    ) -> tuple[bool, str]:
        """Return ``(ok, reason)``."""
        cap = capital or self._capital
        if cap <= 0:
            return False, "Capital is zero"
        loss_pct = abs(min(0, monthly_pnl)) / cap * 100
        if loss_pct >= self._max_monthly:
            msg = (
                f"Monthly loss limit breached: -{loss_pct:.1f}% "
                f"(limit {self._max_monthly}%)"
            )
            logger.warning(msg)
            return False, msg
        return True, f"Monthly loss at {loss_pct:.1f}% (limit {self._max_monthly}%)"

    # ── Drawdown protocol ────────────────────────────────────────────

    def check_drawdown_protocol(
        self,
        drawdown_pct: float,
    ) -> tuple[str, str]:
        """Determine the action mandated by the current drawdown.

        Returns
        -------
        tuple[str, str]
            ``(action, explanation)``

            Actions:
            - ``"NORMAL"`` — no restriction.
            - ``"CONSERVATIVE"`` — raise conviction threshold to 80.
            - ``"PAPER_ONLY"`` — switch to paper trading.
            - ``"HALT"`` — full trading halt.
        """
        if drawdown_pct >= 15:
            action, msg = "HALT", f"Drawdown {drawdown_pct:.1f}% ≥ 15% → HALT"
        elif drawdown_pct >= 10:
            action, msg = "PAPER_ONLY", f"Drawdown {drawdown_pct:.1f}% ≥ 10% → paper only"
        elif drawdown_pct >= 5:
            action, msg = "CONSERVATIVE", f"Drawdown {drawdown_pct:.1f}% ≥ 5% → conservative"
        else:
            action, msg = "NORMAL", f"Drawdown {drawdown_pct:.1f}% — normal mode"

        if action != "NORMAL":
            logger.warning("Drawdown protocol: %s", msg)
        else:
            logger.debug("Drawdown protocol: %s", msg)
        return action, msg

    # ── Consecutive loss sizing ──────────────────────────────────────

    def check_consecutive_losses(self, losses_count: int) -> float:
        """Return a position-size multiplier based on recent consecutive
        losses.

        - ≤ 2 consecutive losses → 1.0  (full size)
        - 3 – 4 → 0.75
        - 5+     → 0.50

        Parameters
        ----------
        losses_count : int

        Returns
        -------
        float
            Multiplier ∈ [0.5, 1.0].
        """
        if losses_count >= 5:
            multiplier = 0.5
        elif losses_count >= 3:
            multiplier = 0.75
        else:
            multiplier = 1.0

        if multiplier < 1.0:
            logger.info(
                "Consecutive-loss adjustment: %d losses → size ×%.2f",
                losses_count, multiplier,
            )
        return multiplier

    # ── Anti-overtrading ─────────────────────────────────────────────

    def check_anti_overtrading(
        self,
        trades_today: int,
        last_trade_time: Optional[datetime],
        symbol: str,
        traded_symbols: Optional[dict[str, datetime]] = None,
    ) -> tuple[bool, str]:
        """Return ``(ok, reason)``.

        Checks
        ------
        1. Max trades per day.
        2. Same-stock cooldown (4 hours default).
        3. No trades in first 15 minutes or last 10 minutes of session.

        Parameters
        ----------
        trades_today : int
        last_trade_time : datetime, optional
        symbol : str
        traded_symbols : dict, optional
            ``{symbol: last_trade_datetime}``
        """
        now = datetime.now(tz=IST)

        # 1. Daily trade count
        if trades_today >= self._max_trades:
            msg = f"Max trades/day reached ({trades_today}/{self._max_trades})"
            logger.warning(msg)
            return False, msg

        # 2. Same-stock cooldown
        if traded_symbols and symbol in traded_symbols:
            last_time = traded_symbols[symbol]
            if last_time.tzinfo is None:
                last_time = last_time.replace(tzinfo=IST)
            hours_since = (now - last_time).total_seconds() / 3600
            if hours_since < self._cooldown_hours:
                msg = (
                    f"Same-stock cooldown: {symbol} traded "
                    f"{hours_since:.1f}h ago (need {self._cooldown_hours}h)"
                )
                logger.info(msg)
                return False, msg

        # 3. Session boundary checks
        market_open = time(9, 15)
        market_close = time(15, 30)
        current_time = now.time()

        # First N minutes
        no_trade_start = time(
            market_open.hour,
            market_open.minute + self._skip_first_min,
        )
        if current_time < no_trade_start:
            msg = f"First {self._skip_first_min} minutes — no trading"
            logger.info(msg)
            return False, msg

        # Last N minutes
        close_minutes = market_close.hour * 60 + market_close.minute
        no_trade_end_minutes = close_minutes - self._skip_last_min
        no_trade_end = time(
            no_trade_end_minutes // 60,
            no_trade_end_minutes % 60,
        )
        if current_time >= no_trade_end:
            msg = f"Last {self._skip_last_min} minutes — no trading"
            logger.info(msg)
            return False, msg

        return True, "OK"

    # ── Market hours ─────────────────────────────────────────────────

    def check_market_hours(self, market: str = "NSE") -> bool:
        """Return ``True`` if *market* is currently open.

        Uses :data:`app.core.constants.MARKET_HOURS` for schedule data.

        Parameters
        ----------
        market : str, default "NSE"
        """
        hours = MARKET_HOURS.get(market.upper())
        if hours is None:
            logger.warning("check_market_hours: unknown market '%s'", market)
            return False

        tz_name = hours.get("timezone", "Asia/Kolkata")
        tz = ZoneInfo(tz_name)
        now = datetime.now(tz=tz)

        # Day-of-week check
        days_str = hours.get("days", "Mon-Fri")
        if days_str == "Mon-Fri" and now.weekday() >= 5:
            return False
        # Mon-Sun → always open day-wise

        open_str = hours.get("market_open", "09:15")
        close_str = hours.get("market_close", "15:30")

        market_open = time(*map(int, open_str.split(":")))
        market_close = time(*map(int, close_str.split(":")))

        is_open = market_open <= now.time() <= market_close
        logger.debug(
            "Market hours: %s %s, now=%s, open=%s–%s → %s",
            market, now.strftime("%A"),
            now.time().isoformat(),
            open_str, close_str,
            "OPEN" if is_open else "CLOSED",
        )
        return is_open

    # ── Master gate ──────────────────────────────────────────────────

    def can_trade(
        self,
        signal: dict[str, Any],
        portfolio_state: dict[str, Any],
    ) -> tuple[bool, list[str]]:
        """Master pre-trade check combining all risk rules.

        Parameters
        ----------
        signal : dict
            Signal data (must have ``symbol``).
        portfolio_state : dict
            Must include: ``daily_pnl``, ``trades_today``,
            ``last_trade_time``, ``traded_symbols_today``,
            ``capital``, ``open_positions``.

        Returns
        -------
        tuple[bool, list[str]]
            ``(can_trade, list_of_rejection_reasons)``
        """
        reasons: list[str] = []
        capital = portfolio_state.get("capital", self._capital)

        # 1. Daily loss
        ok, msg = self.check_daily_loss_limit(
            portfolio_state.get("daily_pnl", 0), capital,
        )
        if not ok:
            reasons.append(msg)

        # 2. Anti-overtrading
        last_trade = portfolio_state.get("last_trade_time")
        if isinstance(last_trade, str):
            last_trade = datetime.fromisoformat(last_trade)

        traded_symbols_raw = portfolio_state.get("traded_symbols_today", {})
        traded_symbols: dict[str, datetime] = {}
        for sym, ts in traded_symbols_raw.items():
            if isinstance(ts, str):
                traded_symbols[sym] = datetime.fromisoformat(ts)
            else:
                traded_symbols[sym] = ts

        ok, msg = self.check_anti_overtrading(
            trades_today=portfolio_state.get("trades_today", 0),
            last_trade_time=last_trade,
            symbol=signal.get("symbol", ""),
            traded_symbols=traded_symbols,
        )
        if not ok:
            reasons.append(msg)

        # 3. Position count
        open_count = portfolio_state.get("open_positions", 0)
        max_positions = self._config.get("max_open_positions", 10)
        if open_count >= max_positions:
            reasons.append(
                f"Max open positions reached ({open_count}/{max_positions})"
            )

        can = len(reasons) == 0
        if not can:
            logger.warning(
                "can_trade → REJECTED for %s: %s",
                signal.get("symbol", "?"),
                "; ".join(reasons),
            )
        return can, reasons

    # ── Risk status snapshot ─────────────────────────────────────────

    def get_risk_status(
        self,
        portfolio_state: dict[str, Any],
    ) -> dict[str, Any]:
        """Return a comprehensive risk-status dict for dashboards / API.

        Parameters
        ----------
        portfolio_state : dict

        Returns
        -------
        dict
        """
        capital = portfolio_state.get("capital", self._capital)
        daily_pnl = portfolio_state.get("daily_pnl", 0)
        weekly_pnl = portfolio_state.get("weekly_pnl", 0)
        monthly_pnl = portfolio_state.get("monthly_pnl", 0)
        drawdown = portfolio_state.get("drawdown_pct", 0)

        daily_ok, daily_msg = self.check_daily_loss_limit(daily_pnl, capital)
        weekly_ok, weekly_msg = self.check_weekly_loss_limit(weekly_pnl, capital)
        monthly_ok, monthly_msg = self.check_monthly_loss_limit(monthly_pnl, capital)
        dd_action, dd_msg = self.check_drawdown_protocol(drawdown)

        return {
            "daily_loss": {
                "ok": daily_ok,
                "message": daily_msg,
                "pnl": round(daily_pnl, 2),
            },
            "weekly_loss": {
                "ok": weekly_ok,
                "message": weekly_msg,
                "pnl": round(weekly_pnl, 2),
            },
            "monthly_loss": {
                "ok": monthly_ok,
                "message": monthly_msg,
                "pnl": round(monthly_pnl, 2),
            },
            "drawdown": {
                "action": dd_action,
                "message": dd_msg,
                "pct": round(drawdown, 2),
            },
            "trades_today": portfolio_state.get("trades_today", 0),
            "open_positions": portfolio_state.get("open_positions", 0),
            "market_open": self.check_market_hours(),
            "timestamp": datetime.now(tz=IST).isoformat(),
        }
