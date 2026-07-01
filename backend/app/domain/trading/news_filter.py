"""
Economic News Filter — Forex Factory calendar feed.
Checks high-impact events within ±2 hours of current time.
NEVER raises — always returns safe defaults on error.
"""
from __future__ import annotations

import json
import logging
import os
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_NEWS_URL    = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
_CACHE_FILE  = Path(__file__).parents[4] / "data" / "news_cache.json"
_CACHE_TTL   = 3600  # 1 hour

_WARN_WINDOW  = 2 * 3600   # 2 hours either side
_REDUCE_WINDOW = 30 * 60   # 30 minutes — reduce confidence


def _load_cache() -> Optional[dict]:
    try:
        if _CACHE_FILE.exists():
            data = json.loads(_CACHE_FILE.read_text())
            if time.time() - data.get("fetched_at", 0) < _CACHE_TTL:
                return data
    except Exception:
        pass
    return None


def _save_cache(events: list) -> None:
    try:
        _CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        _CACHE_FILE.write_text(json.dumps({"fetched_at": time.time(), "events": events}))
    except Exception:
        pass


def _fetch_events() -> list:
    cached = _load_cache()
    if cached:
        return cached.get("events", [])
    try:
        import urllib.request
        req = urllib.request.Request(
            _NEWS_URL,
            headers={"User-Agent": "Mozilla/5.0 TradingBot/1.0"},
        )
        with urllib.request.urlopen(req, timeout=10) as r:
            raw = json.loads(r.read())
        # Keep only HIGH impact events
        events = [
            e for e in raw
            if str(e.get("impact", "")).upper() in ("HIGH", "3")
        ]
        _save_cache(events)
        logger.info("News filter: fetched %d high-impact events", len(events))
        return events
    except Exception as e:
        logger.debug("News filter fetch failed (non-fatal): %s", e)
        return []


def _parse_event_time(event: dict) -> Optional[datetime]:
    """Parse FF calendar datetime fields → UTC datetime."""
    try:
        raw = event.get("date") or event.get("datetime") or ""
        if not raw:
            return None
        # FF format: "2026-06-29T14:30:00-04:00" or "06-29-2026"
        from dateutil import parser as dparser
        dt = dparser.parse(raw)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def check_news(pair: str, confidence: int) -> dict:
    """
    Returns:
        {
            news_warning: bool,
            news_events: list[str],    # human-readable event names
            confidence_penalty: int,   # subtract from confidence (0 or 30)
        }
    """
    result = {"news_warning": False, "news_events": [], "confidence_penalty": 0}
    try:
        events = _fetch_events()
        if not events:
            return result

        # Extract both currencies from pair (EUR/USD → ["EUR", "USD"])
        parts = pair.replace("-", "/").split("/")
        currencies = {p.upper() for p in parts if p}
        # Handle metals / crypto
        ccy_map = {"XAU": "USD", "XAG": "USD", "BTC": "USD", "ETH": "USD"}
        extra = set()
        for c in currencies:
            if c in ccy_map:
                extra.add(ccy_map[c])
        currencies |= extra

        now_utc = datetime.now(timezone.utc)
        warn_events: list[str] = []
        within_30min = False

        for evt in events:
            ccy = str(evt.get("currency", "")).upper()
            if ccy not in currencies:
                continue
            evt_time = _parse_event_time(evt)
            if evt_time is None:
                continue
            diff = abs((evt_time - now_utc).total_seconds())
            if diff <= _WARN_WINDOW:
                title = evt.get("title") or evt.get("name") or "High-Impact Event"
                mins  = int((evt_time - now_utc).total_seconds() / 60)
                sign  = "in" if mins >= 0 else "ago"
                warn_events.append(f"{ccy}: {title} ({abs(mins)}min {sign})")
                if diff <= _REDUCE_WINDOW:
                    within_30min = True

        if warn_events:
            result["news_warning"] = True
            result["news_events"]  = warn_events[:5]
            if within_30min:
                result["confidence_penalty"] = 30
                logger.info("News filter: HIGH-IMPACT within 30min for %s — penalty 30", pair)
            else:
                logger.info("News filter: high-impact within 2H for %s", pair)
    except Exception as e:
        logger.debug("News filter check failed (non-fatal): %s", e)
    return result
