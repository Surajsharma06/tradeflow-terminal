"""
FastAPI application entry point for the Trading System.

Configures CORS, lifespan (DB + Redis init/teardown), all v1 routers,
WebSocket endpoint for live prices, root health-check, and exception
handlers.
"""

import asyncio
import json
import logging
import random
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from collections.abc import AsyncGenerator

from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.constants import INDIAN_STOCKS
from app.core.logging_config import setup_logging
from app.infrastructure.cache.redis_client import close_redis, init_redis
from app.infrastructure.database.session import close_db, init_db

IST = timezone(timedelta(hours=5, minutes=30))
logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════
# Lifespan
# ═══════════════════════════════════════════════════════════════════════

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Application lifespan context manager.

    Startup: initialise logging, database, and Redis.
    Shutdown: close database engine and Redis pool.
    """
    settings = get_settings()
    setup_logging(log_level=settings.log_level)
    logger.info("=" * 60)
    logger.info("  Trading System API starting up")
    logger.info("  Environment : %s", settings.environment)
    logger.info("  Paper mode  : %s", settings.paper_trading)
    logger.info("  Debug       : %s", settings.debug)
    logger.info("=" * 60)

    # Initialise infrastructure
    try:
        await init_db()
        logger.info("Database initialised")
    except Exception as exc:
        logger.warning("Database init skipped — %s", exc)

    try:
        await init_redis()
        logger.info("Redis initialised")
    except Exception as exc:
        logger.warning("Redis init skipped — %s", exc)

    yield  # ── application runs ──

    # Shutdown
    logger.info("Shutting down Trading System API …")
    await close_db()
    await close_redis()
    logger.info("Shutdown complete")


# ═══════════════════════════════════════════════════════════════════════
# App Factory
# ═══════════════════════════════════════════════════════════════════════

def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()

    app = FastAPI(
        title="Trading System API",
        description=(
            "Professional automated trading system backend. "
            "Supports Indian equities, US stocks, crypto, and derivatives. "
            "Paper trading enabled by default."
        ),
        version=settings.app_version,
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    # ── CORS ─────────────────────────────────────────────────────────
    origins = ["*"] if settings.cors_allow_all else settings.cors_origins
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=not settings.cors_allow_all,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Routers ──────────────────────────────────────────────────────
    app.include_router(api_router, prefix="/api/v1")

    # ── Exception Handlers ───────────────────────────────────────────

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
        """Return structured JSON for HTTP exceptions."""
        logger.warning("HTTP %d — %s — %s", exc.status_code, request.url, exc.detail)
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": True,
                "status_code": exc.status_code,
                "detail": exc.detail,
                "timestamp": datetime.now(IST).isoformat(),
            },
        )

    @app.exception_handler(Exception)
    async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        """Catch-all for unhandled exceptions — log and return 500."""
        logger.exception("Unhandled error on %s: %s", request.url, exc)
        return JSONResponse(
            status_code=500,
            content={
                "error": True,
                "status_code": 500,
                "detail": "Internal server error",
                "timestamp": datetime.now(IST).isoformat(),
            },
        )

    # ── Root Endpoint ────────────────────────────────────────────────

    @app.get("/", tags=["System"])
    async def root() -> dict:
        """Return system status and health information."""
        now = datetime.now(IST)
        hour = now.hour
        minute = now.minute
        current_mins = hour * 60 + minute
        nse_open = 9 * 60 + 15
        nse_close = 15 * 60 + 30
        nse_status = (
            "open"
            if nse_open <= current_mins <= nse_close and now.weekday() < 5
            else "closed"
        )

        return {
            "name": "Trading System API",
            "version": settings.app_version,
            "status": "running",
            "environment": settings.environment,
            "paper_trading": settings.paper_trading,
            "nse_status": nse_status,
            "timestamp": now.isoformat(),
            "uptime": "healthy",
            "endpoints": {
                "docs": "/docs",
                "redoc": "/redoc",
                "api": "/api/v1",
                "websocket": "/ws/prices",
            },
        }

    @app.get("/health", tags=["System"])
    async def health_check() -> dict:
        """Lightweight health check for load balancers."""
        return {"status": "ok", "timestamp": datetime.now(IST).isoformat()}

    # ── WebSocket for Live Prices ────────────────────────────────────

    @app.websocket("/ws/prices")
    async def websocket_prices(websocket: WebSocket) -> None:
        """
        Stream mock live prices over WebSocket.

        Sends a JSON payload every second with randomised prices
        for popular Indian stocks.
        """
        await websocket.accept()
        logger.info("WebSocket client connected for live prices")

        try:
            while True:
                # Pick 5 random stocks and generate live ticks
                symbols = random.sample(list(INDIAN_STOCKS.keys()), k=5)
                ticks = []
                for sym in symbols:
                    base = INDIAN_STOCKS[sym]["base_price"]
                    price = round(base * (1 + random.uniform(-0.02, 0.02)), 2)
                    change = round(price - base, 2)
                    ticks.append({
                        "symbol": sym,
                        "price": price,
                        "change": change,
                        "change_pct": round(change / base * 100, 2),
                        "volume": random.randint(10_000, 2_000_000),
                        "timestamp": datetime.now(IST).isoformat(),
                    })

                await websocket.send_text(json.dumps({"prices": ticks}))
                await asyncio.sleep(1)

        except WebSocketDisconnect:
            logger.info("WebSocket client disconnected")
        except Exception as exc:
            logger.error("WebSocket error: %s", exc)

    # ── WebSocket for Live Order Book ────────────────────────────────

    @app.websocket("/ws/orderbook")
    async def websocket_orderbook(websocket: WebSocket) -> None:
        """Stream live order book updates for a forex pair every 800ms."""
        from app.api.v1.endpoints.orderbook import _get_price, _build_orderbook
        import math

        await websocket.accept()
        symbol = websocket.query_params.get("symbol", "EURUSD")
        pair   = symbol.upper().replace("-", "/")
        if "/" not in pair and len(pair) == 6:
            pair = pair[:3] + "/" + pair[3:]

        logger.info("OrderBook WS connected: %s", pair)

        try:
            base_price = _get_price(pair)
            price      = base_price
            tick_size  = 0.01 if "JPY" in pair else (1.0 if pair in ("BTC/USD","ETH/USD") else 0.0001)

            while True:
                # Slight random walk to simulate live movement
                price = round(price + random.gauss(0, tick_size * 0.8), 6)
                # Keep within ±0.2% of base
                price = max(base_price * 0.998, min(base_price * 1.002, price))

                ob = _build_orderbook(pair, price, levels=15)
                await websocket.send_text(json.dumps(ob))
                await asyncio.sleep(0.8)

        except WebSocketDisconnect:
            logger.info("OrderBook WS disconnected: %s", pair)
        except Exception as exc:
            logger.error("OrderBook WS error %s: %s", pair, exc)

    return app


# ── Module-level app instance for uvicorn ────────────────────────────
app = create_app()
