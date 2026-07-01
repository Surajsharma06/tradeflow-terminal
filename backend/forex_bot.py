#!/usr/bin/env python3
"""
🤖 Forex Signal Bot — Standalone Runner
========================================
Run karo:  python3 forex_bot.py

Kya karta hai:
  • Har 4 ghante mein sare major forex pairs scan karta hai
  • BUY/SELL signals nikalta hai — Entry, SL, TP1/TP2/TP3 ke saath
  • Telegram pe seedha bhejta hai
  • Terminal mein bhi dikhata hai (bina Telegram ke bhi kaam karta hai)
  • London + NY session mein automatically jyada scan karta hai

Koi API key NAHI chahiye — yfinance (free) use karta hai.
"""

import asyncio
import logging
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

# ── Path setup so we can import app modules ───────────────────────────────
ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

# ── Logging ───────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("forex_bot")

IST = ZoneInfo("Asia/Kolkata")


# ── Load .env manually (no pydantic-settings needed for standalone) ───────
def load_env():
    env_file = ROOT / ".env"
    if not env_file.exists():
        return
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        os.environ.setdefault(key.strip(), val.strip())


load_env()

TELEGRAM_TOKEN   = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

# ── Pairs to scan (change as needed) ─────────────────────────────────────
PAIRS_TO_SCAN = [
    "EUR/USD",
    "GBP/USD",
    "USD/JPY",
    "AUD/USD",
    "USD/CAD",
    "NZD/USD",
    "USD/CHF",
    "GBP/JPY",
    "EUR/GBP",
    "EUR/JPY",
    "USD/INR",
]

# ── Scan intervals ────────────────────────────────────────────────────────
SCAN_INTERVAL_NORMAL  = 4 * 60 * 60   # 4 hours
SCAN_INTERVAL_ACTIVE  = 1 * 60 * 60   # 1 hour (during London/NY session)
MIN_CONFIDENCE        = 65.0           # Only show signals above this

# ── Sent signal deduplication (avoid sending same signal twice) ──────────
_sent_signals: set[str] = set()


# ── Telegram sender (pure httpx, no library needed) ──────────────────────
async def send_telegram(message: str) -> bool:
    """Send message via Telegram Bot API using httpx."""
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        return False
    try:
        import httpx
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message,
            "parse_mode": "HTML",
        }
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(url, json=payload)
            if resp.status_code == 200:
                logger.info("✅ Telegram message sent")
                return True
            else:
                logger.warning("Telegram error: %s", resp.text[:200])
                return False
    except Exception as e:
        logger.error("Telegram send failed: %s", e)
        return False


def print_signal_terminal(sig) -> None:
    """Print signal nicely to terminal."""
    dir_symbol = "▲ BUY " if sig.direction == "BUY" else "▼ SELL"
    sess_badge = f"🔥 {sig.session} (BEST!)" if sig.best_session else sig.session
    print(f"""
{'='*60}
  {dir_symbol} {sig.pair}
{'='*60}
  Strategy  : {sig.strategy}
  Timeframe : {sig.timeframe}
  Session   : {sess_badge}
  Time      : {sig.timestamp}
{'─'*60}
  Entry     : {sig.entry:.5f}
  Stop Loss : {sig.stop_loss:.5f}  ({sig.pips_risk:.0f} pips)
  TP1       : {sig.target_1:.5f}  (conservative)
  TP2       : {sig.target_2:.5f}  (moderate)
  TP3       : {sig.target_3:.5f}  (aggressive)
  R:R Ratio : 1:{sig.risk_reward:.1f}
{'─'*60}
  AI Confidence : {sig.confidence:.1f}%
  Notes     : {sig.notes}
{'='*60}
""")


async def run_scan() -> None:
    """Run one full scan cycle across all pairs."""
    from app.domain.trading.forex_signals import (
        scan_forex_signals,
        format_signal_for_telegram,
        get_active_session,
    )

    now       = datetime.now(IST).strftime("%d %b %Y, %I:%M %p IST")
    session, is_best = get_active_session()

    logger.info("🔍 Starting scan | Time: %s | Session: %s", now, session)

    signals = scan_forex_signals(
        pairs=PAIRS_TO_SCAN,
        min_confidence=MIN_CONFIDENCE,
        timeframe="1d",
        period="90d",
    )

    if not signals:
        msg = (
            f"⏳ <b>Forex Scan — {now}</b>\n"
            f"📍 Session: {session}\n\n"
            f"No high-confidence signals right now.\n"
            f"Best time: London (1:30 PM – 5:30 PM IST) or NY (6:30 PM – 11:30 PM IST)"
        )
        logger.info("No signals this cycle.")
        await send_telegram(msg)
        return

    logger.info("✅ Found %d signal(s)", len(signals))

    # Send each signal
    for sig in signals:
        sig_key = f"{sig.pair}_{sig.direction}_{sig.entry:.5f}"
        if sig_key in _sent_signals:
            logger.info("Skip duplicate: %s", sig_key)
            continue

        # Show in terminal
        print_signal_terminal(sig)

        # Send to Telegram
        tg_msg = format_signal_for_telegram(sig)
        sent   = await send_telegram(tg_msg)

        if sent:
            _sent_signals.add(sig_key)
            # Keep set small
            if len(_sent_signals) > 100:
                oldest = list(_sent_signals)[:50]
                for k in oldest:
                    _sent_signals.discard(k)

        await asyncio.sleep(1.5)  # rate limit between messages


async def main_loop() -> None:
    """Main infinite loop — scans on schedule."""
    print("""
╔══════════════════════════════════════════════════╗
║       🤖 Forex Signal Bot — RUNNING              ║
╠══════════════════════════════════════════════════╣
║  Signals will appear here + on Telegram          ║
║  Press Ctrl+C to stop                           ║
╚══════════════════════════════════════════════════╝
""")

    if TELEGRAM_TOKEN and TELEGRAM_CHAT_ID:
        logger.info("✅ Telegram configured — signals will be sent")
        # Send startup message
        await send_telegram(
            "🤖 <b>Forex Signal Bot Started!</b>\n\n"
            "Scanning pairs:\n" +
            "\n".join(f"  • {p}" for p in PAIRS_TO_SCAN) +
            "\n\n📡 First scan starting now..."
        )
    else:
        logger.warning(
            "⚠️  Telegram NOT configured — signals will only show in terminal.\n"
            "   Run: python3 setup_telegram.py to configure Telegram."
        )

    # First scan immediately
    try:
        await run_scan()
    except Exception as e:
        logger.error("Scan error: %s", e)

    while True:
        try:
            from app.domain.trading.forex_signals import get_active_session
            _, is_best = get_active_session()
            interval = SCAN_INTERVAL_ACTIVE if is_best else SCAN_INTERVAL_NORMAL

            next_scan = datetime.now(IST)
            h, m      = divmod(interval // 60, 60)
            logger.info("💤 Next scan in %dh %02dm", h, m)

            await asyncio.sleep(interval)
            await run_scan()

        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error("Loop error: %s — retrying in 5 min", e)
            await asyncio.sleep(300)


if __name__ == "__main__":
    try:
        asyncio.run(main_loop())
    except KeyboardInterrupt:
        print("\n\n👋 Forex Bot stopped. Goodbye!\n")
