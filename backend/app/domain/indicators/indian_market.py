"""
Indian market–specific indicators.

Covers institutional flow tracking (FII / DII), delivery-based analysis,
option-chain metrics (PCR, OI build-up), circuit-limit proximity, and
India VIX–driven position sizing.  External data sources are mocked for
now and can be swapped for real feeds later.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)

IST = ZoneInfo("Asia/Kolkata")


# ═══════════════════════════════════════════════════════════════════════
# FII / DII Tracker
# ═══════════════════════════════════════════════════════════════════════

class FIIDIITracker:
    """Track Foreign Institutional Investor and Domestic Institutional
    Investor activity in the Indian cash-market segment.

    Currently returns **mock data**.  Replace
    :meth:`get_fii_dii_activity` with a real feed (e.g. NSE bulk-deal
    API) when available.
    """

    def __init__(self) -> None:
        self._last_refresh: Optional[datetime] = None

    # ── public API ───────────────────────────────────────────────────

    def get_fii_dii_activity(self) -> dict[str, float]:
        """Return the latest FII / DII buy / sell figures (₹ crore).

        Returns
        -------
        dict
            Keys: ``fii_buy``, ``fii_sell``, ``fii_net``,
            ``dii_buy``, ``dii_sell``, ``dii_net``.
        """
        # ── Mock data (realistic scale in ₹ crore → stored as ₹) ──
        fii_buy = 8_500_000_000.0   # ₹850 Cr
        fii_sell = 7_200_000_000.0  # ₹720 Cr
        dii_buy = 6_800_000_000.0   # ₹680 Cr
        dii_sell = 5_900_000_000.0  # ₹590 Cr

        self._last_refresh = datetime.now(tz=IST)
        data = {
            "fii_buy": fii_buy,
            "fii_sell": fii_sell,
            "fii_net": fii_buy - fii_sell,
            "dii_buy": dii_buy,
            "dii_sell": dii_sell,
            "dii_net": dii_buy - dii_sell,
            "timestamp": self._last_refresh.isoformat(),
        }
        logger.debug("FII/DII activity: %s", data)
        return data

    def is_fii_buying_heavy(self, threshold: float = 500_000_000.0) -> bool:
        """Return ``True`` if FII net buy exceeds *threshold* (₹).

        A net buy > ₹500 Cr is typically treated as a bullish
        institutional signal.

        Parameters
        ----------
        threshold : float, default 500_000_000 (₹50 Cr → stored in ₹)
            Net-buy amount above which FII buying is considered heavy.
        """
        activity = self.get_fii_dii_activity()
        result = activity["fii_net"] > threshold
        logger.info(
            "FII heavy buy check: net=₹%.2f Cr, threshold=₹%.2f Cr → %s",
            activity["fii_net"] / 1e7,
            threshold / 1e7,
            result,
        )
        return result


# ═══════════════════════════════════════════════════════════════════════
# Delivery Analysis
# ═══════════════════════════════════════════════════════════════════════

def delivery_percentage(traded_qty: float, delivery_qty: float) -> float:
    """Compute delivery percentage.

    Parameters
    ----------
    traded_qty : float
        Total traded quantity for the session.
    delivery_qty : float
        Quantity actually taken / given delivery.

    Returns
    -------
    float
        Delivery % (0 – 100).  Returns 0.0 when *traded_qty* is zero.
    """
    if traded_qty <= 0:
        logger.warning("delivery_percentage: traded_qty is zero or negative")
        return 0.0
    pct = (delivery_qty / traded_qty) * 100.0
    logger.debug("Delivery %%: %.2f (delivery=%s, traded=%s)", pct, delivery_qty, traded_qty)
    return pct


def is_strong_delivery(delivery_pct: float, threshold: float = 50.0) -> bool:
    """Return ``True`` if delivery percentage exceeds *threshold*.

    High delivery % (> 50 %) signals genuine institutional interest
    rather than speculative intraday churn.

    Parameters
    ----------
    delivery_pct : float
        Delivery percentage (0 – 100).
    threshold : float, default 50.0
        Minimum % to be considered "strong".
    """
    return delivery_pct >= threshold


# ═══════════════════════════════════════════════════════════════════════
# Options Market Indicators
# ═══════════════════════════════════════════════════════════════════════

def calculate_pcr(put_oi: float, call_oi: float) -> float:
    """Put-Call Ratio based on open interest.

    Parameters
    ----------
    put_oi : float
        Total put open interest.
    call_oi : float
        Total call open interest.

    Returns
    -------
    float
        PCR value.  Returns 0.0 if *call_oi* is zero.
    """
    if call_oi <= 0:
        logger.warning("calculate_pcr: call_oi is zero or negative")
        return 0.0
    pcr = put_oi / call_oi
    logger.debug("PCR: %.3f (put_oi=%s, call_oi=%s)", pcr, put_oi, call_oi)
    return pcr


def interpret_pcr(pcr: float) -> str:
    """Interpret a Put-Call Ratio value.

    Interpretation
    --------------
    - PCR > 1.3  → ``BULLISH``  (over-hedged → contrarian bullish)
    - PCR < 0.7  → ``BEARISH``  (complacency → contrarian bearish)
    - Otherwise  → ``NEUTRAL``

    Parameters
    ----------
    pcr : float
        Put-Call Ratio.
    """
    if pcr > 1.3:
        return "BULLISH"
    if pcr < 0.7:
        return "BEARISH"
    return "NEUTRAL"


def detect_oi_buildup(
    current_oi: float,
    prev_oi: float,
    price_change: float,
) -> str:
    """Classify OI build-up based on change in open interest and price.

    Returns
    -------
    str
        One of ``LONG_BUILDUP``, ``SHORT_BUILDUP``,
        ``LONG_UNWINDING``, ``SHORT_COVERING``, or ``NO_CHANGE``.
    """
    oi_up = current_oi > prev_oi
    oi_down = current_oi < prev_oi
    price_up = price_change > 0
    price_down = price_change < 0

    if oi_up and price_up:
        buildup = "LONG_BUILDUP"
    elif oi_up and price_down:
        buildup = "SHORT_BUILDUP"
    elif oi_down and price_down:
        buildup = "LONG_UNWINDING"
    elif oi_down and price_up:
        buildup = "SHORT_COVERING"
    else:
        buildup = "NO_CHANGE"

    logger.debug(
        "OI buildup: %s (oi: %s→%s, price_change: %.2f)",
        buildup,
        prev_oi,
        current_oi,
        price_change,
    )
    return buildup


# ═══════════════════════════════════════════════════════════════════════
# Circuit Limit Check
# ═══════════════════════════════════════════════════════════════════════

def is_near_circuit(
    price: float,
    prev_close: float,
    circuit_pct: float = 5.0,
) -> bool:
    """Return ``True`` if *price* is within 0.5 % of the circuit limit.

    Stocks near their upper / lower circuit are illiquid and should be
    avoided for fresh entries.

    Parameters
    ----------
    price : float
        Current (or LTP) price.
    prev_close : float
        Previous session's closing price.
    circuit_pct : float, default 5.0
        Circuit-limit band in percent (e.g. 5 %).
    """
    if prev_close <= 0:
        logger.warning("is_near_circuit: prev_close is zero or negative")
        return False

    upper_circuit = prev_close * (1 + circuit_pct / 100.0)
    lower_circuit = prev_close * (1 - circuit_pct / 100.0)

    buffer_pct = 0.005  # 0.5 % buffer
    near_upper = price >= upper_circuit * (1 - buffer_pct)
    near_lower = price <= lower_circuit * (1 + buffer_pct)

    result = near_upper or near_lower
    if result:
        logger.info(
            "Stock near circuit: price=%.2f, prev_close=%.2f, "
            "upper=%.2f, lower=%.2f",
            price,
            prev_close,
            upper_circuit,
            lower_circuit,
        )
    return result


# ═══════════════════════════════════════════════════════════════════════
# India VIX Analyzer
# ═══════════════════════════════════════════════════════════════════════

class IndiaVIXAnalyzer:
    """Adjust trading position sizes based on India VIX levels.

    VIX Range      Multiplier  Rationale
    ──────────     ──────────  ─────────────────────────
    < 15            1.00       Normal volatility
    15 – 20         0.75       Slightly elevated → reduce 25 %
    20 – 25         0.50       High vol → reduce 50 %
    > 25            0.00       Extreme vol → cash / hedged only
    """

    _BANDS: list[tuple[float, float]] = [
        (15.0, 1.00),
        (20.0, 0.75),
        (25.0, 0.50),
    ]

    def get_position_size_multiplier(self, vix: float) -> float:
        """Return a position-size multiplier in [0.0, 1.0].

        Parameters
        ----------
        vix : float
            Current India VIX reading.
        """
        if vix < 0:
            logger.warning("IndiaVIXAnalyzer: negative VIX value (%.2f)", vix)
            return 0.0

        for threshold, multiplier in self._BANDS:
            if vix < threshold:
                logger.debug("VIX %.2f → multiplier %.2f", vix, multiplier)
                return multiplier

        logger.warning(
            "VIX %.2f exceeds 25 → position multiplier 0.0 (cash only)",
            vix,
        )
        return 0.0
