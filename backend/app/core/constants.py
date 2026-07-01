"""
Trading system constants.

Centralises all static reference data: indices, trading pairs, market hours,
Indian brokerage charges, tax rates, strategy definitions, and market regimes.
"""

from enum import Enum


# ═══════════════════════════════════════════════════════════════════════
# Market Indices
# ═══════════════════════════════════════════════════════════════════════

INDIAN_INDICES: list[dict[str, str]] = [
    {"symbol": "NIFTY 50", "name": "Nifty 50", "exchange": "NSE"},
    {"symbol": "NIFTY BANK", "name": "Nifty Bank", "exchange": "NSE"},
    {"symbol": "NIFTY IT", "name": "Nifty IT", "exchange": "NSE"},
    {"symbol": "NIFTY MIDCAP 50", "name": "Nifty Midcap 50", "exchange": "NSE"},
    {"symbol": "NIFTY FIN SERVICE", "name": "Nifty Financial Services", "exchange": "NSE"},
    {"symbol": "SENSEX", "name": "BSE Sensex", "exchange": "BSE"},
    {"symbol": "NIFTY PHARMA", "name": "Nifty Pharma", "exchange": "NSE"},
    {"symbol": "NIFTY AUTO", "name": "Nifty Auto", "exchange": "NSE"},
    {"symbol": "NIFTY METAL", "name": "Nifty Metal", "exchange": "NSE"},
    {"symbol": "NIFTY ENERGY", "name": "Nifty Energy", "exchange": "NSE"},
]

US_INDICES: list[dict[str, str]] = [
    {"symbol": "SPX", "name": "S&P 500", "exchange": "NYSE"},
    {"symbol": "DJI", "name": "Dow Jones Industrial Average", "exchange": "NYSE"},
    {"symbol": "IXIC", "name": "NASDAQ Composite", "exchange": "NASDAQ"},
    {"symbol": "RUT", "name": "Russell 2000", "exchange": "NYSE"},
    {"symbol": "VIX", "name": "CBOE Volatility Index", "exchange": "CBOE"},
]

CRYPTO_PAIRS: list[str] = [
    "BTC/USDT",
    "ETH/USDT",
    "SOL/USDT",
    "BNB/USDT",
    "XRP/USDT",
    "ADA/USDT",
    "AVAX/USDT",
    "DOGE/USDT",
    "DOT/USDT",
    "MATIC/USDT",
]

FOREX_PAIRS: list[str] = [
    "USD/INR",
    "EUR/INR",
    "GBP/INR",
    "JPY/INR",
    "EUR/USD",
    "GBP/USD",
    "USD/JPY",
    "AUD/USD",
]

COMMODITY_SYMBOLS: list[str] = [
    "GOLD",
    "SILVER",
    "CRUDEOIL",
    "NATURALGAS",
    "COPPER",
    "ALUMINIUM",
    "ZINC",
    "COTTON",
]

# ═══════════════════════════════════════════════════════════════════════
# Popular Indian Stocks (with realistic base prices in ₹)
# ═══════════════════════════════════════════════════════════════════════

INDIAN_STOCKS: dict[str, dict] = {
    "RELIANCE": {"name": "Reliance Industries", "base_price": 2800.0, "lot": 1},
    "TCS": {"name": "Tata Consultancy Services", "base_price": 4200.0, "lot": 1},
    "HDFCBANK": {"name": "HDFC Bank", "base_price": 1800.0, "lot": 1},
    "INFY": {"name": "Infosys", "base_price": 1750.0, "lot": 1},
    "ICICIBANK": {"name": "ICICI Bank", "base_price": 1300.0, "lot": 1},
    "HINDUNILVR": {"name": "Hindustan Unilever", "base_price": 2400.0, "lot": 1},
    "ITC": {"name": "ITC Limited", "base_price": 450.0, "lot": 1},
    "SBIN": {"name": "State Bank of India", "base_price": 850.0, "lot": 1},
    "BAJFINANCE": {"name": "Bajaj Finance", "base_price": 7200.0, "lot": 1},
    "BHARTIARTL": {"name": "Bharti Airtel", "base_price": 1650.0, "lot": 1},
    "KOTAKBANK": {"name": "Kotak Mahindra Bank", "base_price": 1850.0, "lot": 1},
    "LT": {"name": "Larsen & Toubro", "base_price": 3500.0, "lot": 1},
    "ASIANPAINT": {"name": "Asian Paints", "base_price": 2900.0, "lot": 1},
    "MARUTI": {"name": "Maruti Suzuki", "base_price": 12500.0, "lot": 1},
    "TATAMOTORS": {"name": "Tata Motors", "base_price": 950.0, "lot": 1},
    "SUNPHARMA": {"name": "Sun Pharma", "base_price": 1550.0, "lot": 1},
    "WIPRO": {"name": "Wipro", "base_price": 480.0, "lot": 1},
    "HCLTECH": {"name": "HCL Technologies", "base_price": 1600.0, "lot": 1},
    "ADANIENT": {"name": "Adani Enterprises", "base_price": 3200.0, "lot": 1},
    "TATASTEEL": {"name": "Tata Steel", "base_price": 155.0, "lot": 1},
}

US_STOCKS: dict[str, dict] = {
    "AAPL": {"name": "Apple Inc.", "base_price": 195.0},
    "MSFT": {"name": "Microsoft Corp.", "base_price": 430.0},
    "GOOGL": {"name": "Alphabet Inc.", "base_price": 175.0},
    "AMZN": {"name": "Amazon.com Inc.", "base_price": 185.0},
    "NVDA": {"name": "NVIDIA Corp.", "base_price": 135.0},
    "TSLA": {"name": "Tesla Inc.", "base_price": 250.0},
    "META": {"name": "Meta Platforms", "base_price": 510.0},
}


# ═══════════════════════════════════════════════════════════════════════
# Market Hours
# ═══════════════════════════════════════════════════════════════════════

MARKET_HOURS: dict[str, dict[str, str]] = {
    "NSE": {
        "pre_open_start": "09:00",
        "pre_open_end": "09:08",
        "market_open": "09:15",
        "market_close": "15:30",
        "post_close_end": "16:00",
        "timezone": "Asia/Kolkata",
        "days": "Mon-Fri",
    },
    "BSE": {
        "pre_open_start": "09:00",
        "pre_open_end": "09:08",
        "market_open": "09:15",
        "market_close": "15:30",
        "post_close_end": "16:00",
        "timezone": "Asia/Kolkata",
        "days": "Mon-Fri",
    },
    "NYSE": {
        "pre_market_start": "04:00",
        "market_open": "09:30",
        "market_close": "16:00",
        "after_hours_end": "20:00",
        "timezone": "America/New_York",
        "days": "Mon-Fri",
    },
    "NASDAQ": {
        "pre_market_start": "04:00",
        "market_open": "09:30",
        "market_close": "16:00",
        "after_hours_end": "20:00",
        "timezone": "America/New_York",
        "days": "Mon-Fri",
    },
    "CRYPTO": {
        "market_open": "00:00",
        "market_close": "23:59",
        "timezone": "UTC",
        "days": "Mon-Sun",
    },
    "MCX": {
        "market_open": "09:00",
        "market_close": "23:30",
        "timezone": "Asia/Kolkata",
        "days": "Mon-Fri",
    },
}


# ═══════════════════════════════════════════════════════════════════════
# Indian Brokerage Charges (Equity Delivery – Zerodha-like)
# ═══════════════════════════════════════════════════════════════════════

INDIAN_CHARGES: dict[str, float] = {
    # Securities Transaction Tax
    "stt_delivery_buy": 0.001,       # 0.1 % on buy side
    "stt_delivery_sell": 0.001,      # 0.1 % on sell side
    "stt_intraday_sell": 0.00025,    # 0.025 % on sell side only
    "stt_fno_sell": 0.000125,        # 0.0125 % on sell side (options on premium)
    # Exchange Transaction Charges
    "exchange_nse": 0.0000297,       # 0.00297 %
    "exchange_bse": 0.0000030,       # 0.00030 %
    # GST on (brokerage + exchange charges)
    "gst_rate": 0.18,               # 18 %
    # SEBI Turnover Fee
    "sebi_fee": 0.000001,           # ₹1 per crore  → 0.0001 %
    # Stamp Duty (buy side only)
    "stamp_duty_delivery": 0.00015,  # 0.015 %
    "stamp_duty_intraday": 0.00003,  # 0.003 %
    "stamp_duty_futures": 0.00002,   # 0.002 %
    "stamp_duty_options": 0.00003,   # 0.003 %
    # Brokerage
    "brokerage_delivery": 0.0,       # Zerodha: free delivery
    "brokerage_intraday": 0.0003,    # 0.03 % or ₹20 max
    "brokerage_max_per_order": 20.0, # ₹20 max per order
}

# ═══════════════════════════════════════════════════════════════════════
# Indian Tax Rates (FY 2025-26)
# ═══════════════════════════════════════════════════════════════════════

TAX_RATES: dict[str, float] = {
    "stcg_equity": 0.20,         # 20 % Short-Term Capital Gains (listed equity)
    "ltcg_equity": 0.125,        # 12.5 % Long-Term Capital Gains (listed equity)
    "ltcg_exemption": 125_000.0, # ₹1.25 lakh exemption per FY
    "stcg_fno": 0.30,            # FnO taxed as business income (slab-based, ~30 %)
    "surcharge_50l_1cr": 0.10,   # 10 % surcharge for ₹50L – ₹1Cr income
    "surcharge_1cr_2cr": 0.15,   # 15 % surcharge for ₹1Cr – ₹2Cr
    "cess": 0.04,                # 4 % Health & Education Cess
}


# ═══════════════════════════════════════════════════════════════════════
# Strategy Names
# ═══════════════════════════════════════════════════════════════════════

class StrategyName(str, Enum):
    """All available trading strategies."""

    MOMENTUM = "momentum"
    MEAN_REVERSION = "mean_reversion"
    BREAKOUT = "breakout"
    TREND_FOLLOWING = "trend_following"
    VWAP = "vwap"
    RSI_DIVERGENCE = "rsi_divergence"
    MACD_CROSSOVER = "macd_crossover"
    BOLLINGER_SQUEEZE = "bollinger_squeeze"
    SUPPORT_RESISTANCE = "support_resistance"
    ORB = "opening_range_breakout"
    SUPERTREND = "supertrend"
    EMA_CROSSOVER = "ema_crossover"
    FIBONACCI = "fibonacci_retracement"
    VOLUME_PROFILE = "volume_profile"
    ML_ENSEMBLE = "ml_ensemble"
    RL_AGENT = "rl_agent"
    SENTIMENT = "sentiment"
    PAIR_TRADING = "pair_trading"
    SCALPING = "scalping"
    SWING = "swing"


# ═══════════════════════════════════════════════════════════════════════
# Market Regime
# ═══════════════════════════════════════════════════════════════════════

class MarketRegime(str, Enum):
    """Detected market regime states."""

    STRONG_BULLISH = "strong_bullish"
    BULLISH = "bullish"
    NEUTRAL = "neutral"
    BEARISH = "bearish"
    STRONG_BEARISH = "strong_bearish"
    HIGH_VOLATILITY = "high_volatility"
    LOW_VOLATILITY = "low_volatility"
    TRENDING = "trending"
    RANGING = "ranging"


class TradeDirection(str, Enum):
    """Trade direction."""

    LONG = "long"
    SHORT = "short"


class TradeStatus(str, Enum):
    """Trade lifecycle status."""

    PENDING = "pending"
    OPEN = "open"
    CLOSED = "closed"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class SignalStatus(str, Enum):
    """Signal lifecycle status."""

    ACTIVE = "active"
    EXECUTED = "executed"
    EXPIRED = "expired"
    REJECTED = "rejected"


class MarketType(str, Enum):
    """Supported market types."""

    INDIAN_EQUITY = "indian_equity"
    US_EQUITY = "us_equity"
    CRYPTO = "crypto"
    FOREX = "forex"
    COMMODITY = "commodity"
    FNO = "fno"
