"""
NSE India data scraper.

Provides FII/DII activity, delivery data, open-interest analysis,
Put-Call Ratio, India VIX, and bulk/block deal information.

Currently returns *realistic mock data*; designed to be swapped for
real NSE API calls (``nsepython`` / direct endpoints) when ready.
Rate limiting and browser-like headers are already in place.
"""

import logging
import random
import time
from datetime import date, datetime
from typing import Any, Optional
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)

IST = ZoneInfo("Asia/Kolkata")

# Rate limiting
_MIN_DELAY: float = 1.0  # NSE is very strict — keep ≥ 1 s between calls
_last_request_ts: float = 0.0

# Browser-like headers to avoid blocking
_HEADERS: dict[str, str] = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.nseindia.com/",
}


def _rate_limit() -> None:
    """Enforce minimum delay between NSE requests."""
    global _last_request_ts
    elapsed = time.monotonic() - _last_request_ts
    if elapsed < _MIN_DELAY:
        time.sleep(_MIN_DELAY - elapsed)
    _last_request_ts = time.monotonic()


class NSEDataScraper:
    """
    Scraper for supplementary NSE market data.

    All methods currently return realistic mock data so the rest of
    the system can develop against a stable interface.  When the
    real NSE endpoints are integrated, only the private ``_fetch``
    method needs to change.
    """

    def __init__(self) -> None:
        """Initialise NSE scraper with default session config."""
        self._session_cookies: dict[str, str] = {}
        logger.info("NSEDataScraper initialised (mock-data mode)")

    # ── FII / DII Activity ───────────────────────────────────────────

    def get_fii_dii_activity(
        self,
        target_date: Optional[date] = None,
    ) -> dict[str, Any]:
        """
        Get Foreign Institutional Investor (FII) and Domestic
        Institutional Investor (DII) buy/sell activity.

        Args:
            target_date: Date to query. Defaults to today (IST).

        Returns:
            Dict with ``fii_buy``, ``fii_sell``, ``fii_net``,
            ``dii_buy``, ``dii_sell``, ``dii_net``, ``date``.
        """
        _rate_limit()
        d = target_date or datetime.now(IST).date()

        fii_buy = round(random.uniform(5_000, 15_000), 2)
        fii_sell = round(random.uniform(4_000, 14_000), 2)
        dii_buy = round(random.uniform(3_000, 10_000), 2)
        dii_sell = round(random.uniform(2_500, 9_500), 2)

        data = {
            "date": d.isoformat(),
            "fii_buy": fii_buy,
            "fii_sell": fii_sell,
            "fii_net": round(fii_buy - fii_sell, 2),
            "dii_buy": dii_buy,
            "dii_sell": dii_sell,
            "dii_net": round(dii_buy - dii_sell, 2),
            "unit": "₹ crore",
        }
        logger.info(
            "FII/DII activity for %s — FII net: ₹%.2f Cr, DII net: ₹%.2f Cr",
            d, data["fii_net"], data["dii_net"],
        )
        return data

    # ── Delivery data ────────────────────────────────────────────────

    def get_delivery_data(self, symbol: str) -> dict[str, Any]:
        """
        Get delivery percentage and volume data for *symbol*.

        Args:
            symbol: NSE symbol (e.g. ``"RELIANCE"``).

        Returns:
            Dict with ``traded_qty``, ``deliverable_qty``,
            ``delivery_pct``, ``avg_delivery_pct_5d``.
        """
        _rate_limit()
        traded = random.randint(5_000_000, 30_000_000)
        delivery_pct = round(random.uniform(25.0, 75.0), 2)
        deliverable = int(traded * delivery_pct / 100)

        data = {
            "symbol": symbol.upper(),
            "traded_qty": traded,
            "deliverable_qty": deliverable,
            "delivery_pct": delivery_pct,
            "avg_delivery_pct_5d": round(delivery_pct + random.uniform(-5, 5), 2),
            "date": datetime.now(IST).date().isoformat(),
        }
        logger.debug("Delivery data %s: %.1f%% delivery", symbol, delivery_pct)
        return data

    # ── Open Interest ────────────────────────────────────────────────

    def get_oi_data(self, symbol: str) -> dict[str, Any]:
        """
        Get open-interest snapshot for *symbol* in F&O.

        Returns:
            Dict with ``total_oi``, ``oi_change``, ``oi_change_pct``,
            ``max_oi_ce_strike``, ``max_oi_pe_strike``.
        """
        _rate_limit()
        total_oi = random.randint(5_000_000, 50_000_000)
        oi_change = random.randint(-2_000_000, 3_000_000)

        data = {
            "symbol": symbol.upper(),
            "total_oi": total_oi,
            "oi_change": oi_change,
            "oi_change_pct": round((oi_change / total_oi) * 100, 2) if total_oi else 0.0,
            "max_oi_ce_strike": random.choice([23000, 23500, 24000, 24500, 25000]),
            "max_oi_pe_strike": random.choice([22500, 23000, 23500, 24000]),
            "pcr_oi": round(random.uniform(0.7, 1.5), 3),
            "date": datetime.now(IST).date().isoformat(),
        }
        logger.debug("OI data %s: total=%d, change=%d", symbol, total_oi, oi_change)
        return data

    # ── Put-Call Ratio ───────────────────────────────────────────────

    def get_pcr_data(self, index: str = "NIFTY") -> float:
        """
        Get the overall Put-Call Ratio for *index*.

        Args:
            index: Index name (e.g. ``"NIFTY"``, ``"BANKNIFTY"``).

        Returns:
            PCR value (typically 0.5 – 2.0).
        """
        _rate_limit()
        pcr = round(random.uniform(0.65, 1.45), 3)
        logger.info("PCR for %s: %.3f", index, pcr)
        return pcr

    # ── India VIX ────────────────────────────────────────────────────

    def get_india_vix(self) -> float:
        """
        Get the current India VIX value.

        Returns:
            VIX value (typically 10 – 30).
        """
        _rate_limit()
        vix = round(random.uniform(10.0, 25.0), 2)
        logger.info("India VIX: %.2f", vix)
        return vix

    # ── Bulk deals ───────────────────────────────────────────────────

    def get_bulk_deals(self) -> list[dict[str, Any]]:
        """
        Get today's bulk deals from NSE.

        Returns:
            List of deal dicts with ``symbol``, ``client``,
            ``deal_type``, ``quantity``, ``price``.
        """
        _rate_limit()
        sample_clients = [
            "Goldman Sachs (Singapore)",
            "Morgan Stanley Asia",
            "HDFC Mutual Fund",
            "SBI Life Insurance",
            "Motilal Oswal Financial Services",
        ]
        sample_symbols = ["TATAPOWER", "IRFC", "ZOMATO", "PAYTM", "ADANIGREEN"]

        deals: list[dict[str, Any]] = []
        for _ in range(random.randint(2, 6)):
            deals.append({
                "symbol": random.choice(sample_symbols),
                "client": random.choice(sample_clients),
                "deal_type": random.choice(["BUY", "SELL"]),
                "quantity": random.randint(100_000, 5_000_000),
                "price": round(random.uniform(100, 3000), 2),
                "date": datetime.now(IST).date().isoformat(),
            })

        logger.info("Bulk deals: %d deals fetched", len(deals))
        return deals

    # ── Block deals ──────────────────────────────────────────────────

    def get_block_deals(self) -> list[dict[str, Any]]:
        """
        Get today's block deals from NSE.

        Returns:
            List of deal dicts similar to bulk deals.
        """
        _rate_limit()
        sample_symbols = ["RELIANCE", "TCS", "HDFCBANK", "INFY", "ICICIBANK"]
        sample_clients = [
            "Citigroup Global Markets",
            "JP Morgan Chase",
            "BNP Paribas",
            "Deutsche Bank AG",
        ]

        deals: list[dict[str, Any]] = []
        for _ in range(random.randint(1, 4)):
            deals.append({
                "symbol": random.choice(sample_symbols),
                "client": random.choice(sample_clients),
                "deal_type": random.choice(["BUY", "SELL"]),
                "quantity": random.randint(500_000, 10_000_000),
                "price": round(random.uniform(500, 5000), 2),
                "date": datetime.now(IST).date().isoformat(),
            })

        logger.info("Block deals: %d deals fetched", len(deals))
        return deals
