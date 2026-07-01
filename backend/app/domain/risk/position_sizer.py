"""
Position sizing engine.

Calculates the optimal number of shares / lots to trade based on
risk-per-trade, VIX-adjusted volatility, conviction level, and
portfolio-level concentration limits.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)


class PositionSizer:
    """Risk-based position sizing with VIX, conviction, and
    concentration adjustments.

    The core formula is:

        size = (capital × risk_pct) / |entry − stop_loss|

    Subsequent multipliers reduce or increase this base size.
    """

    # ── Concentration limits ─────────────────────────────────────────
    MAX_SINGLE_STOCK_PCT: float = 5.0   # 5 % of capital
    MAX_SECTOR_PCT: float = 20.0        # 20 % of capital
    MAX_OPEN_POSITIONS: int = 10

    def __init__(self) -> None:
        logger.info("PositionSizer initialised")

    # ── Core position size ───────────────────────────────────────────

    def calculate_position_size(
        self,
        capital: float,
        risk_pct: float,
        entry: float,
        stop_loss: float,
    ) -> int:
        """Calculate position size from a fixed risk percentage.

        Parameters
        ----------
        capital : float
            Total available capital (₹).
        risk_pct : float
            Fraction of capital to risk per trade (e.g. ``0.01`` = 1 %).
        entry : float
            Planned entry price.
        stop_loss : float
            Planned stop-loss price.

        Returns
        -------
        int
            Number of shares (always ≥ 0).
        """
        if capital <= 0 or risk_pct <= 0 or entry <= 0:
            logger.warning(
                "calculate_position_size: invalid inputs "
                "(capital=%.2f, risk_pct=%.4f, entry=%.2f)",
                capital, risk_pct, entry,
            )
            return 0

        risk_per_share = abs(entry - stop_loss)
        if risk_per_share <= 0:
            logger.warning("calculate_position_size: risk_per_share is zero")
            return 0

        risk_amount = capital * risk_pct
        size = int(risk_amount / risk_per_share)
        size = max(0, size)

        logger.debug(
            "Position size: capital=%.0f, risk=%.2f%%, "
            "entry=%.2f, SL=%.2f → %d shares",
            capital, risk_pct * 100, entry, stop_loss, size,
        )
        return size

    # ── VIX adjustment ───────────────────────────────────────────────

    def apply_vix_adjustment(
        self,
        size: int,
        vix: float,
        market: str = "india",
    ) -> int:
        """Reduce position size based on VIX level.

        Multiplier table (India VIX):
        - < 15   → 1.0  (full size)
        - 15–20  → 0.75
        - 20–25  → 0.50
        - > 25   → 0.25 (minimal exposure)

        For non-India markets the thresholds are shifted by +5.

        Parameters
        ----------
        size : int
            Base position size.
        vix : float
            Current VIX reading.
        market : str, default "india"

        Returns
        -------
        int
            Adjusted size.
        """
        offset = 0 if market.lower() == "india" else 5

        if vix < 15 + offset:
            multiplier = 1.0
        elif vix < 20 + offset:
            multiplier = 0.75
        elif vix < 25 + offset:
            multiplier = 0.50
        else:
            multiplier = 0.25

        adjusted = max(0, int(size * multiplier))
        logger.debug(
            "VIX adjustment: vix=%.2f, market=%s, multiplier=%.2f → %d→%d",
            vix, market, multiplier, size, adjusted,
        )
        return adjusted

    # ── Conviction adjustment ────────────────────────────────────────

    def apply_conviction_adjustment(
        self,
        size: int,
        score: float,
        base_risk: float = 1.0,
        high_risk: float = 2.0,
    ) -> int:
        """Adjust size based on signal conviction score.

        - Score ≥ 85 → scale risk up to *high_risk* (e.g. 2× normal).
        - Score 72–84 → normal (1× base_risk).
        - Score < 72 → reduce to 0.5× (marginal conviction).

        Parameters
        ----------
        size : int
        score : float
            Signal composite score (0 – 100).
        base_risk : float
            Normal risk multiplier.
        high_risk : float
            Elevated risk multiplier for high-conviction signals.

        Returns
        -------
        int
        """
        if score >= 85:
            multiplier = high_risk
        elif score >= 72:
            multiplier = base_risk
        else:
            multiplier = 0.5

        adjusted = max(0, int(size * multiplier))
        logger.debug(
            "Conviction adjustment: score=%.1f, multiplier=%.2f → %d→%d",
            score, multiplier, size, adjusted,
        )
        return adjusted

    # ── Concentration checks ─────────────────────────────────────────

    def check_position_limits(
        self,
        symbol: str,
        sector: str,
        current_positions: list[dict[str, Any]],
        capital: float,
    ) -> bool:
        """Return ``True`` if adding a new position for *symbol* is
        within concentration limits.

        Limits enforced
        ---------------
        1. Max 5 % of capital in any single stock.
        2. Max 20 % of capital in any single sector.
        3. Max 10 open positions.

        Parameters
        ----------
        symbol : str
        sector : str
        current_positions : list[dict]
            Each dict must have ``symbol``, ``sector``,
            ``entry``, ``quantity``.
        capital : float

        Returns
        -------
        bool
        """
        if len(current_positions) >= self.MAX_OPEN_POSITIONS:
            logger.warning(
                "Position limit: max %d open positions reached",
                self.MAX_OPEN_POSITIONS,
            )
            return False

        # Single-stock exposure
        stock_exposure = sum(
            p["entry"] * p["quantity"]
            for p in current_positions
            if p.get("symbol") == symbol
        )
        if capital > 0 and (stock_exposure / capital) * 100 >= self.MAX_SINGLE_STOCK_PCT:
            logger.warning(
                "Position limit: %s already at %.1f%% of capital",
                symbol,
                (stock_exposure / capital) * 100,
            )
            return False

        # Sector exposure
        sector_exposure = sum(
            p["entry"] * p["quantity"]
            for p in current_positions
            if p.get("sector", "").upper() == sector.upper()
        )
        if capital > 0 and (sector_exposure / capital) * 100 >= self.MAX_SECTOR_PCT:
            logger.warning(
                "Position limit: sector %s at %.1f%% of capital",
                sector,
                (sector_exposure / capital) * 100,
            )
            return False

        return True

    # ── Full pipeline ────────────────────────────────────────────────

    def get_effective_size(
        self,
        capital: float,
        entry: float,
        stop_loss: float,
        score: float,
        vix: float,
        positions: list[dict[str, Any]],
        symbol: str,
        sector: str,
        risk_pct: float = 0.01,
        market: str = "india",
    ) -> int:
        """Full position-sizing pipeline.

        1. Base size from risk percentage.
        2. VIX adjustment.
        3. Conviction adjustment.
        4. Concentration-limit gate.

        Parameters
        ----------
        capital, entry, stop_loss, score, vix, positions, symbol,
        sector, risk_pct, market
            See individual methods for semantics.

        Returns
        -------
        int
            Final number of shares to trade.  Returns 0 if blocked
            by concentration limits.
        """
        # 1. Base
        size = self.calculate_position_size(capital, risk_pct, entry, stop_loss)
        if size <= 0:
            return 0

        # 2. VIX
        size = self.apply_vix_adjustment(size, vix, market)

        # 3. Conviction
        size = self.apply_conviction_adjustment(size, score)

        # 4. Concentration
        if not self.check_position_limits(symbol, sector, positions, capital):
            logger.info(
                "get_effective_size: %s blocked by concentration limits",
                symbol,
            )
            return 0

        # Cap position value at MAX_SINGLE_STOCK_PCT of capital
        max_value = capital * (self.MAX_SINGLE_STOCK_PCT / 100)
        if entry > 0:
            max_shares = int(max_value / entry)
            size = min(size, max_shares)

        logger.info(
            "Effective position size for %s: %d shares "
            "(entry=%.2f, SL=%.2f, score=%.1f, VIX=%.1f)",
            symbol, size, entry, stop_loss, score, vix,
        )
        return max(0, size)
