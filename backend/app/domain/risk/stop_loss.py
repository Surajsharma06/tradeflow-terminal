"""
Stop-loss and take-profit management.

Handles initial SL placement (ATR-based), trailing-stop progression,
time-based exits, multi-tier take-profit levels (2R / 3R / trail),
and comprehensive exit-decision logic.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)

IST = ZoneInfo("Asia/Kolkata")


class StopLossManager:
    """ATR-based stop-loss, trailing-stop, and take-profit engine.

    Default behaviour
    -----------------
    - Initial SL = ATR × *multiplier* from entry.
    - Breakeven trigger at 1.5 % unrealised profit.
    - Trail by ATR × 1.5 after 3 % profit.
    - Take-profit tiers:
      TP1 = 2R  (exit 40 %)
      TP2 = 3R  (exit 40 %)
      TP3 = trail remainder (20 %)
    """

    def __init__(self) -> None:
        logger.info("StopLossManager initialised")

    # ── Initial stop-loss ────────────────────────────────────────────

    def calculate_initial_sl(
        self,
        entry: float,
        atr_value: float,
        direction: str = "LONG",
        multiplier: float = 2.0,
    ) -> float:
        """Calculate the initial stop-loss from entry and ATR.

        Parameters
        ----------
        entry : float
            Entry price.
        atr_value : float
            Current ATR value.
        direction : str
            ``"LONG"`` or ``"SHORT"``.
        multiplier : float, default 2.0
            ATR multiplier for the stop distance.

        Returns
        -------
        float
            Stop-loss price.
        """
        if atr_value <= 0:
            logger.warning(
                "calculate_initial_sl: ATR is zero/negative, using 2%% of entry"
            )
            atr_value = entry * 0.02

        distance = atr_value * multiplier

        if direction.upper() == "LONG":
            sl = entry - distance
        else:
            sl = entry + distance

        sl = round(sl, 2)
        logger.debug(
            "Initial SL: direction=%s, entry=%.2f, ATR=%.2f, "
            "multiplier=%.1f → SL=%.2f",
            direction, entry, atr_value, multiplier, sl,
        )
        return sl

    # ── Trailing stop ────────────────────────────────────────────────

    def update_trailing_sl(
        self,
        current_price: float,
        entry: float,
        current_sl: float,
        atr_value: float,
        direction: str = "LONG",
    ) -> float:
        """Update the trailing stop-loss.

        Progression
        -----------
        1. At 1.5 % unrealised profit → move SL to breakeven (entry).
        2. At 3 % profit → trail by ATR × 1.5.

        The stop is only ever moved *in favour* (tightened); it never
        widens.

        Parameters
        ----------
        current_price : float
        entry : float
        current_sl : float
        atr_value : float
        direction : str

        Returns
        -------
        float
            Updated stop-loss price.
        """
        if entry <= 0:
            return current_sl

        if direction.upper() == "LONG":
            pnl_pct = ((current_price - entry) / entry) * 100
        else:
            pnl_pct = ((entry - current_price) / entry) * 100

        new_sl = current_sl

        if pnl_pct >= 3.0:
            # Trail by ATR × 1.5
            trail_distance = max(atr_value * 1.5, entry * 0.005)
            if direction.upper() == "LONG":
                proposed = current_price - trail_distance
                new_sl = max(current_sl, proposed)
            else:
                proposed = current_price + trail_distance
                new_sl = min(current_sl, proposed)

        elif pnl_pct >= 1.5:
            # Move to breakeven
            if direction.upper() == "LONG":
                new_sl = max(current_sl, entry)
            else:
                new_sl = min(current_sl, entry)

        new_sl = round(new_sl, 2)
        if new_sl != current_sl:
            logger.info(
                "Trailing SL updated: %s, pnl=%.1f%%, %.2f→%.2f",
                direction, pnl_pct, current_sl, new_sl,
            )
        return new_sl

    # ── Time-based exit ──────────────────────────────────────────────

    @staticmethod
    def check_time_based_exit(
        entry_time: datetime,
        max_days: int = 3,
    ) -> bool:
        """Return ``True`` if the position has exceeded *max_days*.

        Parameters
        ----------
        entry_time : datetime
        max_days : int, default 3

        Returns
        -------
        bool
        """
        now = datetime.now(tz=IST)

        # Ensure entry_time is timezone-aware
        if entry_time.tzinfo is None:
            entry_time = entry_time.replace(tzinfo=IST)

        days_held = (now - entry_time).total_seconds() / 86400
        should_exit = days_held >= max_days
        if should_exit:
            logger.info(
                "Time-based exit triggered: held %.1f days (max=%d)",
                days_held, max_days,
            )
        return should_exit

    # ── Multi-tier take-profit ───────────────────────────────────────

    def calculate_take_profit_levels(
        self,
        entry: float,
        stop_loss: float,
    ) -> dict[str, dict[str, float]]:
        """Calculate tiered take-profit levels based on risk (R).

        Tiers
        -----
        - **TP1** : 2R — exit 40 % of position.
        - **TP2** : 3R — exit another 40 %.
        - **TP3** : trail remaining 20 %.

        Parameters
        ----------
        entry : float
        stop_loss : float

        Returns
        -------
        dict
            ``{"tp1": {"price": …, "exit_pct": 40}, …}``
        """
        risk = abs(entry - stop_loss)
        if risk <= 0:
            logger.warning(
                "calculate_take_profit_levels: zero risk (entry=SL)"
            )
            risk = entry * 0.02

        direction_long = entry > stop_loss

        if direction_long:
            tp1 = entry + 2 * risk
            tp2 = entry + 3 * risk
            tp3 = entry + 4 * risk  # aspirational trail target
        else:
            tp1 = entry - 2 * risk
            tp2 = entry - 3 * risk
            tp3 = entry - 4 * risk

        levels = {
            "tp1": {"price": round(tp1, 2), "exit_pct": 40.0, "r_multiple": 2.0},
            "tp2": {"price": round(tp2, 2), "exit_pct": 40.0, "r_multiple": 3.0},
            "tp3": {"price": round(tp3, 2), "exit_pct": 20.0, "r_multiple": 4.0},
        }
        logger.debug(
            "TP levels: entry=%.2f, SL=%.2f, R=%.2f → %s",
            entry, stop_loss, risk, levels,
        )
        return levels

    # ── Comprehensive exit check ─────────────────────────────────────

    def should_exit(
        self,
        current_price: float,
        entry: float,
        stop_loss: float,
        take_profits: Optional[dict[str, dict[str, float]]] = None,
        entry_time: Optional[datetime] = None,
        pnl_pct: Optional[float] = None,
        max_days: int = 3,
    ) -> tuple[bool, str]:
        """Master exit decision.

        Checks (in order of priority):
        1. Stop-loss hit.
        2. Take-profit 1 / 2 / 3 hit.
        3. Time-based exit.
        4. Max loss guard (−5 %).

        Parameters
        ----------
        current_price : float
        entry : float
        stop_loss : float
        take_profits : dict, optional
        entry_time : datetime, optional
        pnl_pct : float, optional
            Pre-computed PnL percentage.
        max_days : int, default 3

        Returns
        -------
        tuple[bool, str]
            ``(should_exit, reason)``
        """
        direction_long = entry > stop_loss

        # 1. Stop-loss
        if direction_long and current_price <= stop_loss:
            return True, "STOP_LOSS_HIT"
        if not direction_long and current_price >= stop_loss:
            return True, "STOP_LOSS_HIT"

        # 2. Take-profit tiers
        if take_profits:
            for tier in ("tp1", "tp2", "tp3"):
                tp_info = take_profits.get(tier)
                if tp_info is None:
                    continue
                tp_price = tp_info["price"]
                if direction_long and current_price >= tp_price:
                    return True, f"TAKE_PROFIT_{tier.upper()}"
                if not direction_long and current_price <= tp_price:
                    return True, f"TAKE_PROFIT_{tier.upper()}"

        # 3. Time-based exit
        if entry_time is not None and self.check_time_based_exit(entry_time, max_days):
            return True, "TIME_EXIT"

        # 4. Max loss guard
        if pnl_pct is not None and pnl_pct <= -5.0:
            return True, "MAX_LOSS_GUARD"

        return False, "HOLD"
