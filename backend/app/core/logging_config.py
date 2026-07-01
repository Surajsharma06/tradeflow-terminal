"""
Logging configuration for the Trading System.

Provides coloured console output, rotating file handler, and IST timestamps.
All trading-related logs include strategy context when available.
"""

import logging
import logging.handlers
import os
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional


# IST offset: UTC+5:30
IST = timezone(timedelta(hours=5, minutes=30))


class ISTFormatter(logging.Formatter):
    """Custom formatter that outputs timestamps in IST (Asia/Kolkata)."""

    def formatTime(self, record: logging.LogRecord, datefmt: Optional[str] = None) -> str:
        """Convert log record time to IST."""
        dt = datetime.fromtimestamp(record.created, tz=IST)
        if datefmt:
            return dt.strftime(datefmt)
        return dt.strftime("%Y-%m-%d %H:%M:%S,%f")[:-3]


class ColouredFormatter(ISTFormatter):
    """
    Adds ANSI colour codes to log output for terminal readability.

    Colours:
        DEBUG    → Cyan
        INFO     → Green
        WARNING  → Yellow
        ERROR    → Red
        CRITICAL → Bold Red
    """

    COLOURS = {
        logging.DEBUG: "\033[36m",     # Cyan
        logging.INFO: "\033[32m",      # Green
        logging.WARNING: "\033[33m",   # Yellow
        logging.ERROR: "\033[31m",     # Red
        logging.CRITICAL: "\033[1;31m",  # Bold Red
    }
    RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        """Apply colour codes around the level name."""
        colour = self.COLOURS.get(record.levelno, self.RESET)
        record.levelname = f"{colour}{record.levelname:<8}{self.RESET}"
        return super().format(record)


def setup_logging(log_level: str = "INFO", log_dir: str = "logs") -> None:
    """
    Configure the root logger for the trading system.

    Args:
        log_level: Minimum log level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
        log_dir: Directory for log files (created if it doesn't exist).
    """
    # Ensure log directory exists
    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)

    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    # Clear existing handlers to avoid duplicates on reload
    root_logger.handlers.clear()

    # ── Console Handler ──────────────────────────────────────────────
    console_fmt = (
        "%(asctime)s │ %(levelname)s │ %(name)-30s │ %(message)s"
    )
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG)
    console_handler.setFormatter(
        ColouredFormatter(console_fmt, datefmt="%H:%M:%S")
    )
    root_logger.addHandler(console_handler)

    # ── File Handler (rotating, 10 MB × 5 backups) ──────────────────
    file_fmt = (
        "%(asctime)s │ %(levelname)-8s │ %(name)s │ %(funcName)s:%(lineno)d │ %(message)s"
    )
    file_handler = logging.handlers.RotatingFileHandler(
        filename=log_path / "trading.log",
        maxBytes=10 * 1024 * 1024,  # 10 MB
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(ISTFormatter(file_fmt))
    root_logger.addHandler(file_handler)

    # ── Trade-specific File Handler ──────────────────────────────────
    trade_logger = logging.getLogger("trading.trades")
    trade_handler = logging.handlers.RotatingFileHandler(
        filename=log_path / "trades.log",
        maxBytes=5 * 1024 * 1024,
        backupCount=10,
        encoding="utf-8",
    )
    trade_fmt = "%(asctime)s │ %(levelname)-8s │ %(message)s"
    trade_handler.setFormatter(ISTFormatter(trade_fmt))
    trade_logger.addHandler(trade_handler)
    trade_logger.setLevel(logging.INFO)

    # ── Quieten noisy third-party loggers ────────────────────────────
    for noisy in ("uvicorn.access", "httpx", "httpcore", "asyncio"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    root_logger.info("Logging initialised — level=%s, dir=%s", log_level, log_path.resolve())
