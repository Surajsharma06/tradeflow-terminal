"""
Trade Journal — local JSON-file storage for manual trade logging.
"""
from __future__ import annotations

import json
import uuid
import logging
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_JOURNAL_FILE = Path(__file__).parents[4] / "data" / "journal" / "trades.json"
_JOURNAL_FILE.parent.mkdir(parents=True, exist_ok=True)
IST = timezone(timedelta(hours=5, minutes=30))


def _load() -> list[dict]:
    if not _JOURNAL_FILE.exists():
        return []
    try:
        return json.loads(_JOURNAL_FILE.read_text())
    except Exception:
        return []


def _save(entries: list[dict]) -> None:
    _JOURNAL_FILE.write_text(json.dumps(entries, default=str, indent=2))


def add_entry(data: dict) -> dict:
    entries = _load()
    entry = {
        "id":               str(uuid.uuid4()),
        "timestamp":        data.get("timestamp") or datetime.now(IST).isoformat(),
        "pair":             data.get("pair", ""),
        "direction":        data.get("direction", "BUY"),
        "entry":            float(data.get("entry", 0)),
        "sl":               float(data.get("sl", 0)),
        "tp1":              float(data.get("tp1", 0)),
        "tp2":              float(data.get("tp2", 0)),
        "tp3":              float(data.get("tp3", 0)),
        "result":           data.get("result", "OPEN"),
        "exit_price":       float(data.get("exit_price", 0)) if data.get("exit_price") else None,
        "pnl_pips":         float(data.get("pnl_pips", 0)) if data.get("pnl_pips") else None,
        "rr_achieved":      float(data.get("rr_achieved", 0)) if data.get("rr_achieved") else None,
        "session":          data.get("session", ""),
        "confluence_score": int(data.get("confluence_score", 0)),
        "notes":            data.get("notes", ""),
        "screenshot_url":   data.get("screenshot_url", ""),
    }
    entries.append(entry)
    _save(entries)
    return entry


def get_entries(
    pair: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    result: Optional[str] = None,
    limit: int = 200,
) -> list[dict]:
    entries = _load()
    if pair:
        entries = [e for e in entries if e.get("pair", "").upper() == pair.upper()]
    if result:
        entries = [e for e in entries if e.get("result", "").upper() == result.upper()]
    if date_from:
        entries = [e for e in entries if (e.get("timestamp") or "") >= date_from]
    if date_to:
        entries = [e for e in entries if (e.get("timestamp") or "") <= date_to]
    return entries[-limit:][::-1]


def delete_entry(entry_id: str) -> bool:
    entries = _load()
    new = [e for e in entries if e.get("id") != entry_id]
    if len(new) == len(entries):
        return False
    _save(new)
    return True


def get_stats() -> dict:
    entries = _load()
    closed = [e for e in entries if e.get("result") in ("WIN", "LOSS", "BREAKEVEN")]
    total  = len(closed)
    wins   = [e for e in closed if e.get("result") == "WIN"]
    losses = [e for e in closed if e.get("result") == "LOSS"]

    total_pips = sum(e.get("pnl_pips") or 0 for e in closed)
    avg_rr_vals = [e["rr_achieved"] for e in wins if e.get("rr_achieved")]
    avg_rr = round(sum(avg_rr_vals) / len(avg_rr_vals), 2) if avg_rr_vals else 0

    # Best / worst pair
    pair_pips: dict[str, float] = defaultdict(float)
    for e in closed:
        pair_pips[e.get("pair", "?")] += e.get("pnl_pips") or 0
    best_pair  = max(pair_pips, key=pair_pips.get) if pair_pips else None
    worst_pair = min(pair_pips, key=pair_pips.get) if pair_pips else None

    # Best session
    session_wins: dict[str, int] = defaultdict(int)
    session_total: dict[str, int] = defaultdict(int)
    for e in closed:
        s = e.get("session", "Unknown") or "Unknown"
        session_total[s] += 1
        if e.get("result") == "WIN":
            session_wins[s] += 1
    best_session = None
    best_wr = 0.0
    for s, tot in session_total.items():
        wr = session_wins[s] / tot if tot else 0
        if wr > best_wr:
            best_wr, best_session = wr, s

    # Monthly breakdown
    monthly: dict[str, dict] = defaultdict(lambda: {"trades": 0, "wins": 0, "pips": 0.0})
    for e in closed:
        try:
            month = (e.get("timestamp") or "")[:7]  # "2026-06"
            monthly[month]["trades"] += 1
            if e.get("result") == "WIN":
                monthly[month]["wins"] += 1
            monthly[month]["pips"] += e.get("pnl_pips") or 0
        except Exception:
            pass
    monthly_list = [
        {"month": m, "trades": v["trades"], "wins": v["wins"], "pips": round(v["pips"], 1)}
        for m, v in sorted(monthly.items())
    ]

    return {
        "total_trades":       len(entries),
        "closed_trades":      total,
        "open_trades":        len([e for e in entries if e.get("result") == "OPEN"]),
        "wins":               len(wins),
        "losses":             len(losses),
        "win_rate":           round(len(wins) / max(total, 1) * 100, 1),
        "avg_rr":             avg_rr,
        "total_pips":         round(total_pips, 1),
        "best_pair":          best_pair,
        "worst_pair":         worst_pair,
        "best_session":       best_session,
        "monthly_breakdown":  monthly_list,
    }
