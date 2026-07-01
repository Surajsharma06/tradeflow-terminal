# 📈 AI-Powered Automated Trading System

> **A professional-grade, multi-market automated trading platform with AI/ML-powered signal generation, hedge fund-grade risk management, and a stunning dark trading terminal dashboard.**

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Python](https://img.shields.io/badge/python-3.12+-brightgreen.svg)
![React](https://img.shields.io/badge/react-19-61DAFB.svg)
![FastAPI](https://img.shields.io/badge/fastapi-0.136+-009688.svg)

---

> [!CAUTION]
> **⚠️ SEBI COMPLIANCE WARNING / सेबी अनुपालन चेतावनी**
> 
> This software is for **educational and research purposes only**. Automated trading in Indian markets is subject to SEBI regulations. Before deploying live trading:
> - Ensure compliance with SEBI's algorithmic trading guidelines
> - Register your trading algorithm with your broker
> - Understand that past backtested performance does NOT guarantee future results
> - **You are solely responsible for any financial losses incurred**
> 
> Paper trading mode is enabled by default. Enable live trading at your own risk.

---

## 🌟 Features

### Multi-Market Coverage
- **Indian Markets**: NSE, BSE — NIFTY 50, SENSEX, F&O, Midcap/Smallcap
- **US Markets**: S&P 500, NASDAQ, NYSE via Alpaca API
- **Crypto**: 24/7 trading via Binance, Coinbase, WazirX, CoinDCX
- **Forex**: USD/INR, EUR/USD, GBP/USD and more via Alpha Vantage / OANDA
- **Commodities**: Gold, Silver, Crude Oil, Natural Gas (MCX + International)

### 6 Trading Strategies (Running Simultaneously)
1. 📈 **Trend Following** — EMA crossover + Supertrend + ADX
2. 🔄 **Mean Reversion** — Bollinger Band squeeze + RSI divergence
3. 🚀 **Momentum Breakout** — 52-week high break + volume surge
4. ⚡ **Scalping** — 1-minute chart patterns (NSE intraday)
5. 🕐 **Swing Trading** — 3–10 day holds on strong setups
6. 🎯 **Options Strategy** — NIFTY/BANKNIFTY weekly expiry (spreads, condors)

### AI/ML Engine (4-Model Ensemble)
- **LSTM** (30% weight) — 60-day sequence → 3-day price prediction
- **XGBoost** (30% weight) — 50+ feature signal classifier
- **PPO RL Agent** (25% weight) — Reinforcement learning for optimal timing
- **FinBERT Sentiment** (15% weight) — Financial news NLP analysis

### Hedge Fund-Grade Risk Management
- Position sizing: ATR-based + VIX-adjusted
- Stop loss: Initial ATR×2, trailing at breakeven/ATR×1.5
- Partial exits: 40% at 2R, 40% at 3R, 20% trail
- Daily/weekly/monthly loss limits (3%/7%/15%)
- Drawdown protocol (5%→conservative, 10%→paper, 15%→halt)
- Portfolio beta management (cap at 1.3)
- Correlation filter (reject >0.8 correlated positions)
- Anti-overtrading rules (5/day max, no first/last minutes)

### Professional Trading Dashboard
- Dark terminal aesthetic with glassmorphic UI
- TradingView Lightweight Charts integration
- Real-time WebSocket price streaming
- Signal scoring breakdown (0–100)
- Risk meter and drawdown visualization
- Global correlation heatmap
- P&L calendar heatmap
- Strategy performance analytics

---

## 🛠 Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | React 19, Tailwind CSS v4, TradingView Charts, Plotly, Zustand |
| Backend | Python 3.12, FastAPI, SQLAlchemy 2.0, asyncpg |
| Database | PostgreSQL 16, Redis 7 |
| AI/ML | PyTorch, XGBoost, Stable-Baselines3, Transformers (FinBERT) |
| Brokers | Zerodha, Upstox, Angel One, Fyers, Alpaca |
| Data | yfinance, ccxt, Alpha Vantage, NSE scraper |
| Alerts | Telegram Bot |
| Deploy | Docker Compose |

---

## 🚀 Quick Start

### Prerequisites
- Node.js 20+
- Python 3.12+
- Docker & Docker Compose (optional, for database services)

### 1. Clone & Setup
```bash
cd Trading

# Copy environment file
cp .env.example .env
# Edit .env with your API keys (optional for paper trading)
```

### 2. Start Database Services
```bash
# Using Docker Compose
cd docker
docker compose up -d postgres redis
cd ..
```

### 3. Backend Setup
```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Run server
uvicorn app.main:app --reload --port 8000
```

### 4. Frontend Setup
```bash
cd frontend
npm install
npm run dev
```

### 5. Open Dashboard
Navigate to **http://localhost:5173** 🎉

---

## 🐳 Docker (Full Stack)
```bash
cd docker
docker compose up --build
```
Access: http://localhost:5173

---

## 📁 Project Structure

```
Trading/
├── frontend/              # React + Vite + Tailwind v4
│   ├── src/
│   │   ├── components/    # UI components (layout, dashboard, analytics, tools)
│   │   ├── pages/         # Route pages
│   │   ├── stores/        # Zustand state management
│   │   ├── services/      # API client, WebSocket
│   │   └── hooks/         # Custom React hooks
│   └── ...
├── backend/               # Python FastAPI
│   ├── app/
│   │   ├── api/v1/        # REST endpoints
│   │   ├── core/          # Config, constants, logging
│   │   ├── domain/        # Business logic (trading, risk, orders, indicators)
│   │   ├── infrastructure/# DB, cache, brokers, data providers
│   │   ├── ml/            # AI/ML models (LSTM, XGBoost, PPO, Sentiment)
│   │   ├── services/      # Service layer
│   │   └── schemas/       # Pydantic models
│   └── ...
├── docker/                # Docker configuration
└── .env.example           # Environment template
```

---

## 📊 Signal Scoring System (0–100)

| Component | Max Points | Source |
|-----------|-----------|--------|
| Technical | 40 | Indicator alignment, trend confirmation |
| Sentiment | 20 | News + social media analysis |
| Volume | 15 | Relative volume, delivery % |
| Market Regime | 15 | Strategy-regime match quality |
| Macro | 10 | VIX, FII flow, global cues |

**Only trades with score > 72 are executed.** Scores > 85 are "high conviction" with 2x position size.

---

## 🛡 Risk Controls Summary

| Control | Limit | Action |
|---------|-------|--------|
| Daily Loss | 3% | Auto-halt trading |
| Weekly Loss | 7% | Halt + alert + manual restart |
| Monthly Loss | 15% | Full halt + review report |
| Max Positions | 10 | Reject new trades |
| Single Stock | 5% capital | Position limit |
| Single Sector | 20% capital | Sector limit |
| Portfolio Beta | 1.3 | Reduce positions |
| Consecutive Losses | 5 | Cut size by 50% |
| Drawdown 5% | Conservative mode | Score threshold → 80 |
| Drawdown 10% | Paper trading only | Until reviewed |
| Drawdown 15% | Full halt | Analysis report |

---

## 🔔 Telegram Alerts

Configure your Telegram bot token and chat ID in `.env`, then receive:
- 🚀 Trade signals with full score breakdown
- ⚠️ Risk limit warnings
- 📊 Daily P&L summaries
- 🔴 Drawdown alerts
- 🌍 Global market crash detection

---

## 🇮🇳 Indian Market Features

- FII/DII daily activity tracking
- Delivery percentage analysis
- Open Interest (OI) buildup detection
- Put-Call Ratio (PCR) for NIFTY/BANKNIFTY
- India VIX-based position sizing
- Promoter holding change alerts
- Bulk/block deal tracking
- Circuit breaker filter
- Full Indian charges calculator (STT, GST, SEBI, stamp duty)
- Tax calculator (STCG 20%, LTCG 12.5%)

---

## ⚙️ Configuration

All configuration is via environment variables in `.env`:

| Variable | Default | Description |
|----------|---------|-------------|
| `PAPER_TRADING` | `true` | Paper trading mode (safe default) |
| `INITIAL_CAPITAL_INR` | `1000000` | Starting capital in ₹ |
| `BASE_RISK_PERCENT` | `1.0` | Risk per trade |
| `SIGNAL_THRESHOLD` | `72` | Min score to trade |
| `MAX_POSITIONS` | `10` | Max open positions |
| `DAILY_LOSS_LIMIT_PERCENT` | `3.0` | Daily loss auto-halt |

See `.env.example` for all available options.

---

## 📜 License

MIT License — See [LICENSE](LICENSE) for details.

---

## 🙏 Disclaimer

This software is provided as-is for educational purposes. The developers are not SEBI-registered investment advisors. Always do your own research before trading. Past performance is not indicative of future results. Use at your own risk.

---

**Built with ❤️ for the Indian & Global trading community**
