"""
Main API v1 router.

Aggregates all endpoint routers under /api/v1 with proper
prefixes and OpenAPI tags.
"""

from fastapi import APIRouter

from app.api.v1.endpoints import (
    analytics,
    backtest,
    backtest_forex,
    journal,
    legends,
    lipschutz,
    market_data,
    orderbook,
    portfolio,
    risk,
    signals,
    tools,
)

api_router = APIRouter()

api_router.include_router(
    lipschutz.router,
    prefix="/lipschutz",
    tags=["Lipschutz Mode"],
)

api_router.include_router(
    legends.router,
    prefix="/legends",
    tags=["Legends Mode"],
)

api_router.include_router(
    market_data.router,
    prefix="/market",
    tags=["Market Data"],
)

api_router.include_router(
    orderbook.router,
    prefix="/market",
    tags=["Order Book"],
)

api_router.include_router(
    signals.router,
    prefix="/signals",
    tags=["Signals"],
)

api_router.include_router(
    portfolio.router,
    prefix="/portfolio",
    tags=["Portfolio"],
)

api_router.include_router(
    risk.router,
    prefix="/risk",
    tags=["Risk Management"],
)

api_router.include_router(
    backtest.router,
    prefix="/backtest",
    tags=["Backtesting"],
)

api_router.include_router(
    analytics.router,
    prefix="/analytics",
    tags=["Analytics"],
)

api_router.include_router(
    tools.router,
    prefix="/tools",
    tags=["Tools"],
)

api_router.include_router(
    backtest_forex.router,
    prefix="/backtest-forex",
    tags=["Backtest Forex"],
)

api_router.include_router(
    journal.router,
    prefix="/journal",
    tags=["Trade Journal"],
)
