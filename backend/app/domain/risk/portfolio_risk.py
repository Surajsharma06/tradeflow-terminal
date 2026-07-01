"""
Portfolio-level risk analysis.

Provides correlation screening, beta computation, sector-exposure
tracking, and Value-at-Risk (VaR) estimation for the overall
portfolio.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class PortfolioRiskManager:
    """Portfolio-level risk manager enforcing diversification and
    aggregate risk constraints.
    """

    def __init__(self) -> None:
        logger.info("PortfolioRiskManager initialised")

    # ── Correlation check ────────────────────────────────────────────

    def check_correlation(
        self,
        symbol: str,
        existing_positions: list[dict[str, Any]],
        price_data: Optional[dict[str, pd.Series]] = None,
        threshold: float = 0.8,
    ) -> tuple[bool, str]:
        """Reject a new position if it is highly correlated with
        existing holdings.

        Parameters
        ----------
        symbol : str
            Candidate symbol.
        existing_positions : list[dict]
            Must include ``symbol`` key.
        price_data : dict, optional
            ``{symbol: pd.Series}`` of daily close prices.
            If not provided the check is auto-passed.
        threshold : float, default 0.8
            Maximum acceptable Pearson correlation.

        Returns
        -------
        tuple[bool, str]
            ``(ok, reason)``  —  ``ok=True`` means low correlation.
        """
        if price_data is None or symbol not in price_data:
            return True, "No price data — correlation check skipped"

        candidate_returns = price_data[symbol].pct_change().dropna()

        for pos in existing_positions:
            pos_symbol = pos.get("symbol", "")
            if pos_symbol not in price_data:
                continue

            pos_returns = price_data[pos_symbol].pct_change().dropna()

            # Align on common index
            aligned = pd.concat(
                [candidate_returns, pos_returns], axis=1, join="inner",
            )
            if len(aligned) < 20:
                continue

            corr = aligned.iloc[:, 0].corr(aligned.iloc[:, 1])
            if not np.isnan(corr) and abs(corr) > threshold:
                msg = (
                    f"{symbol} corr={corr:.2f} with {pos_symbol} "
                    f"exceeds threshold {threshold}"
                )
                logger.warning("Correlation check failed: %s", msg)
                return False, msg

        return True, "Correlation within limits"

    # ── Beta ─────────────────────────────────────────────────────────

    def calculate_portfolio_beta(
        self,
        positions: list[dict[str, Any]],
        market_data: Optional[dict[str, pd.Series]] = None,
        market_symbol: str = "NIFTY 50",
    ) -> float:
        """Calculate the portfolio's weighted beta relative to the
        market index.

        Parameters
        ----------
        positions : list[dict]
            Each with ``symbol``, ``entry``, ``quantity``.
        market_data : dict, optional
            ``{symbol: pd.Series}`` — must include the market index.
        market_symbol : str

        Returns
        -------
        float
            Portfolio beta.  Returns 1.0 when data is insufficient.
        """
        if not positions or market_data is None:
            return 1.0

        market_series = market_data.get(market_symbol)
        if market_series is None or len(market_series) < 30:
            return 1.0

        market_returns = market_series.pct_change().dropna()
        market_var = market_returns.var()
        if market_var == 0:
            return 1.0

        total_value = sum(p["entry"] * p["quantity"] for p in positions)
        if total_value == 0:
            return 1.0

        weighted_beta = 0.0

        for pos in positions:
            sym = pos.get("symbol", "")
            stock_series = market_data.get(sym)
            if stock_series is None or len(stock_series) < 30:
                # Assume beta = 1 for unknown stocks
                weight = (pos["entry"] * pos["quantity"]) / total_value
                weighted_beta += weight * 1.0
                continue

            stock_returns = stock_series.pct_change().dropna()
            aligned = pd.concat(
                [stock_returns, market_returns], axis=1, join="inner",
            )
            if len(aligned) < 20:
                weight = (pos["entry"] * pos["quantity"]) / total_value
                weighted_beta += weight * 1.0
                continue

            cov = aligned.iloc[:, 0].cov(aligned.iloc[:, 1])
            beta = cov / market_var
            weight = (pos["entry"] * pos["quantity"]) / total_value
            weighted_beta += weight * beta

        logger.info("Portfolio beta: %.3f", weighted_beta)
        return round(weighted_beta, 3)

    def check_beta_limit(
        self,
        beta: float,
        max_beta: float = 1.3,
    ) -> bool:
        """Return ``True`` if portfolio beta is within the limit.

        Parameters
        ----------
        beta : float
        max_beta : float, default 1.3
        """
        ok = abs(beta) <= max_beta
        if not ok:
            logger.warning(
                "Portfolio beta %.3f exceeds limit %.2f", beta, max_beta,
            )
        return ok

    # ── Sector exposure ──────────────────────────────────────────────

    def get_sector_exposure(
        self,
        positions: list[dict[str, Any]],
    ) -> dict[str, float]:
        """Return total invested value per sector.

        Parameters
        ----------
        positions : list[dict]
            Each with ``sector``, ``entry``, ``quantity``.

        Returns
        -------
        dict[str, float]
            ``{sector: total_value}``
        """
        exposure: dict[str, float] = {}
        for pos in positions:
            sector = pos.get("sector", "UNKNOWN").upper()
            value = pos.get("entry", 0) * pos.get("quantity", 0)
            exposure[sector] = exposure.get(sector, 0) + value

        logger.debug("Sector exposure: %s", exposure)
        return exposure

    def check_sector_limit(
        self,
        sector: str,
        exposure: dict[str, float],
        capital: float,
        max_pct: float = 20.0,
    ) -> bool:
        """Return ``True`` if sector exposure is below *max_pct* of
        capital.

        Parameters
        ----------
        sector : str
        exposure : dict
            Output of :meth:`get_sector_exposure`.
        capital : float
        max_pct : float, default 20.0
        """
        if capital <= 0:
            return False

        sector_val = exposure.get(sector.upper(), 0)
        pct = (sector_val / capital) * 100
        ok = pct < max_pct
        if not ok:
            logger.warning(
                "Sector %s at %.1f%% (limit %.1f%%)",
                sector, pct, max_pct,
            )
        return ok

    # ── Value at Risk (VaR) ──────────────────────────────────────────

    def calculate_portfolio_var(
        self,
        positions: list[dict[str, Any]],
        price_data: Optional[dict[str, pd.Series]] = None,
        confidence: float = 0.95,
        horizon_days: int = 1,
    ) -> float:
        """Parametric Value-at-Risk using variance-covariance method.

        Parameters
        ----------
        positions : list[dict]
            Each with ``symbol``, ``entry``, ``quantity``.
        price_data : dict, optional
            ``{symbol: pd.Series}`` of daily closes.
        confidence : float, default 0.95
        horizon_days : int, default 1

        Returns
        -------
        float
            VaR in ₹ (positive number representing potential loss).
        """
        if not positions or price_data is None:
            logger.debug("calculate_portfolio_var: no data — returning 0")
            return 0.0

        # Build weights and returns matrix
        symbols: list[str] = []
        weights: list[float] = []
        total_value = 0.0

        for pos in positions:
            sym = pos.get("symbol", "")
            val = pos.get("entry", 0) * pos.get("quantity", 0)
            if sym in price_data and val > 0:
                symbols.append(sym)
                weights.append(val)
                total_value += val

        if total_value == 0 or not symbols:
            return 0.0

        weight_arr = np.array(weights) / total_value

        # Daily returns for each asset
        returns_df = pd.DataFrame(
            {sym: price_data[sym].pct_change().dropna() for sym in symbols}
        ).dropna()

        if len(returns_df) < 10:
            logger.warning(
                "calculate_portfolio_var: insufficient return data (%d rows)",
                len(returns_df),
            )
            return 0.0

        # Covariance matrix
        cov_matrix = returns_df.cov().values

        # Portfolio variance
        port_var = float(weight_arr @ cov_matrix @ weight_arr)
        port_std = np.sqrt(port_var)

        # Z-score for confidence level
        from scipy.stats import norm  # type: ignore[import-untyped]

        z = norm.ppf(confidence)

        var = total_value * z * port_std * np.sqrt(horizon_days)
        var = round(var, 2)

        logger.info(
            "Portfolio VaR (%.0f%%, %dd): ₹%.2f (portfolio=₹%.0f, σ=%.4f)",
            confidence * 100,
            horizon_days,
            var,
            total_value,
            port_std,
        )
        return var
