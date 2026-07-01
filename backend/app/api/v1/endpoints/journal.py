"""
Trade Journal endpoints — log, view, and analyse manual trades.
"""
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter()


class TradeEntry(BaseModel):
    pair:             str
    direction:        str = "BUY"
    entry:            float
    sl:               float
    tp1:              float
    tp2:              float = 0.0
    tp3:              float = 0.0
    result:           str   = "OPEN"
    exit_price:       Optional[float] = None
    pnl_pips:         Optional[float] = None
    rr_achieved:      Optional[float] = None
    session:          str   = ""
    confluence_score: int   = 0
    notes:            str   = ""
    screenshot_url:   str   = ""
    timestamp:        Optional[str] = None


@router.post("/entry", summary="Log a trade")
async def add_entry(entry: TradeEntry):
    from app.domain.journal.trade_journal import add_entry as _add
    return _add(entry.dict())


@router.get("/entries", summary="List trade entries")
async def list_entries(
    pair:      Optional[str] = Query(None),
    result:    Optional[str] = Query(None, description="WIN|LOSS|BREAKEVEN|OPEN"),
    date_from: Optional[str] = Query(None, description="ISO date e.g. 2026-01-01"),
    date_to:   Optional[str] = Query(None),
    limit:     int           = Query(100, ge=1, le=500),
):
    from app.domain.journal.trade_journal import get_entries
    return get_entries(pair=pair, date_from=date_from, date_to=date_to, result=result, limit=limit)


@router.get("/stats", summary="Aggregate journal stats")
async def get_stats():
    from app.domain.journal.trade_journal import get_stats
    return get_stats()


@router.delete("/entry/{entry_id}", summary="Delete a trade entry")
async def delete_entry(entry_id: str):
    from app.domain.journal.trade_journal import delete_entry as _del
    ok = _del(entry_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Entry not found")
    return {"deleted": entry_id}
