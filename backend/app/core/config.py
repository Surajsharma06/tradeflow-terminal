"""
Application configuration using Pydantic Settings.

Loads all environment variables from .env file with proper validation,
defaults, and type coercion. Paper trading is enabled by default.
"""

from functools import lru_cache
from typing import Optional

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Central configuration for the Trading System.

    All sensitive credentials are loaded from environment variables.
    Paper trading mode is enabled by default for safety.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Application ──────────────────────────────────────────────────
    app_name: str = "Trading System API"
    app_version: str = "1.0.0"
    debug: bool = False
    environment: str = "development"
    timezone: str = "Asia/Kolkata"
    log_level: str = "INFO"
    secret_key: str = "change-me-in-production"

    # ── Database (SQLite by default, PostgreSQL if DATABASE_URL is set) ─
    database_url: str = "sqlite+aiosqlite:///./trading.db"
    db_pool_size: int = 5
    db_max_overflow: int = 10
    db_pool_timeout: int = 30
    db_echo: bool = False

    # ── Redis ────────────────────────────────────────────────────────
    redis_url: str = "redis://localhost:6379/0"
    redis_password: Optional[str] = None
    redis_max_connections: int = 50
    redis_ttl_seconds: int = 300  # default cache TTL

    # ── Zerodha / Kite Connect ───────────────────────────────────────
    kite_api_key: Optional[str] = None
    kite_api_secret: Optional[str] = None
    kite_access_token: Optional[str] = None
    kite_request_token: Optional[str] = None

    # ── Angel One / SmartAPI ─────────────────────────────────────────
    angel_api_key: Optional[str] = None
    angel_client_id: Optional[str] = None
    angel_password: Optional[str] = None
    angel_totp_secret: Optional[str] = None

    # ── Alpaca (US Markets) ──────────────────────────────────────────
    alpaca_api_key: Optional[str] = None
    alpaca_secret_key: Optional[str] = None
    alpaca_base_url: str = "https://paper-api.alpaca.markets"

    # ── Binance (Crypto) ─────────────────────────────────────────────
    binance_api_key: Optional[str] = None
    binance_secret_key: Optional[str] = None

    # ── Data Provider Keys ───────────────────────────────────────────
    alpha_vantage_key: Optional[str] = None
    polygon_api_key: Optional[str] = None
    finnhub_api_key: Optional[str] = None
    news_api_key: Optional[str] = None
    twelve_data_api_key: Optional[str] = None

    # ── Telegram Notifications ───────────────────────────────────────
    telegram_bot_token: Optional[str] = None
    telegram_chat_id: Optional[str] = None

    # ── Trading Parameters ───────────────────────────────────────────
    paper_trading: bool = True
    initial_capital: float = 1_000_000.0  # ₹10 Lakh default
    max_capital_per_trade_pct: float = 5.0  # % of capital per trade
    max_open_positions: int = 10
    max_daily_loss_pct: float = 3.0  # stop trading after 3% daily loss
    max_weekly_loss_pct: float = 7.0
    max_monthly_loss_pct: float = 12.0
    default_stop_loss_pct: float = 2.0
    default_take_profit_pct: float = 4.0
    min_signal_score: float = 65.0  # minimum score to act on signal

    # ── Rate Limiting ────────────────────────────────────────────────
    rate_limit_requests_per_second: int = 5
    rate_limit_burst: int = 10

    # ── ML / AI ──────────────────────────────────────────────────────
    ml_model_dir: str = "models"
    sentiment_model: str = "yiyanghkust/finbert-tone"

    # ── CORS ─────────────────────────────────────────────────────────
    cors_origins: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "https://*.onrender.com",
        "https://*.netlify.app",
        "https://*.vercel.app",
    ]
    cors_allow_all: bool = False

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """Ensure log level is a valid Python logging level."""
        allowed = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        upper = v.upper()
        if upper not in allowed:
            raise ValueError(f"log_level must be one of {allowed}")
        return upper

    @field_validator("max_capital_per_trade_pct", "max_daily_loss_pct")
    @classmethod
    def validate_percentage(cls, v: float) -> float:
        """Ensure percentages are within sane bounds."""
        if not 0.0 < v <= 100.0:
            raise ValueError("Percentage must be between 0 and 100")
        return v


@lru_cache
def get_settings() -> Settings:
    """
    Return a cached Settings singleton.

    Uses lru_cache so the .env file is read only once per process.
    """
    return Settings()
