"""
Real forex backtesting endpoints — walk-forward SMC strategy on historical 1H data.
"""
import asyncio
import logging

from fastapi import APIRouter, HTTPException, Query

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/run", summary="Run SMC backtest on historical data")
async def run_backtest(
    pair:     str = Query("EURUSD",  description="Pair e.g. EURUSD or EUR/USD"),
    days:     int = Query(90, ge=7, le=365, description="Lookback days (7–365)"),
):
    """
    Walk-forward backtest of SMC strategy.
    Fetches 1H historical OHLCV from yfinance, replays candle-by-candle.
    Saves result to data/backtest/.
    """
    from app.domain.backtesting.backtester import run_backtest as _run, save_result

    pair = pair.replace("-", "/").upper()
    if "/" not in pair and len(pair) == 6:
        pair = pair[:3] + "/" + pair[3:]

    logger.info("Backtest request: %s %dd", pair, days)

    loop = asyncio.get_event_loop()
    try:
        result = await loop.run_in_executor(None, lambda: _run(pair, days))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])

    filename = await loop.run_in_executor(None, lambda: save_result(result, pair, days))
    result["filename"] = filename
    return result


@router.get("/results", summary="List saved backtest results")
async def list_results():
    from app.domain.backtesting.backtester import list_results as _list
    return _list()


@router.get("/results/{filename}", summary="Get specific backtest result")
async def get_result(filename: str):
    from app.domain.backtesting.backtester import get_result as _get
    # Safety: only allow simple filenames, no path traversal
    if "/" in filename or ".." in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")
    data = _get(filename)
    if data is None:
        raise HTTPException(status_code=404, detail="Result not found")
    return data
