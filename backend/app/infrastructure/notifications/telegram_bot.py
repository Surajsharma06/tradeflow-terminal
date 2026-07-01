"""
Telegram notification bot for the Trading System.

Sends richly formatted trading alerts, risk warnings, daily summaries,
drawdown alerts, market-crash notifications, and regime-change updates
via the Telegram Bot API.

Also supports interactive COMMANDS from Telegram:
  /start    - Welcome message
  /help     - All commands list
  /signals  - Latest active signals
  /status   - Bot + market status
  /pause    - Pause signal alerts
  /resume   - Resume signal alerts
  /summary  - Today's P&L summary

Gracefully degrades to logging when no bot token is configured.
"""

import asyncio
import logging
from datetime import datetime
from typing import Any, Optional
from zoneinfo import ZoneInfo

try:
    from telegram import Bot, Update, InlineKeyboardButton, InlineKeyboardMarkup
    from telegram.constants import ParseMode
    from telegram.ext import Application, CommandHandler, ContextTypes
    HAS_TELEGRAM = True
except ImportError:
    HAS_TELEGRAM = False

from app.core.config import get_settings

logger = logging.getLogger(__name__)
IST = ZoneInfo("Asia/Kolkata")

# Global pause state
_alerts_paused: bool = False
_active_signals: list[dict] = []  # in-memory last signals cache


class TradingTelegramBot:
    """
    Telegram notification service for trading signals and alerts.

    If TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID are not set,
    all methods fall back to logger.info so the system can still
    operate without Telegram.
    """

    def __init__(
        self,
        token: Optional[str] = None,
        chat_id: Optional[str] = None,
    ) -> None:
        settings = get_settings()
        self._token = token or settings.telegram_bot_token
        self._chat_id = chat_id or settings.telegram_chat_id
        self._bot: Optional[Any] = None
        self._app: Optional[Any] = None

        if self._token and HAS_TELEGRAM:
            self._bot = Bot(token=self._token)
            logger.info("TradingTelegramBot initialised (chat_id=%s)", self._chat_id)
        elif not HAS_TELEGRAM:
            logger.info("python-telegram-bot not installed — alerts will be logged only")
        else:
            logger.info("Telegram bot token not configured — alerts will be logged only")

    # ── Internal send helper ─────────────────────────────────────────

    async def _send(self, text: str, parse_mode: str = "HTML", reply_markup=None) -> bool:
        """Send a message via Telegram Bot API."""
        if not self._bot or not self._chat_id:
            logger.info("[Telegram stub] %s", text[:200])
            return False

        try:
            await self._bot.send_message(
                chat_id=self._chat_id,
                text=text,
                parse_mode=parse_mode,
                reply_markup=reply_markup,
            )
            logger.debug("Telegram message sent (%d chars)", len(text))
            return True
        except Exception as exc:
            logger.error("Failed to send Telegram message: %s", exc)
            return False

    def _send_sync(self, text: str) -> bool:
        """Synchronous wrapper for _send."""
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self._send(text))
            return True
        except RuntimeError:
            return asyncio.run(self._send(text))

    # ── Signal alert ─────────────────────────────────────────────────

    async def send_signal_alert(self, signal: dict[str, Any]) -> bool:
        """
        Send a formatted trade signal alert with Zerodha Kite deeplink.

        Args:
            signal: Dict with keys symbol, direction, entry_price,
                    stop_loss, take_profit, score, strategy,
                    timeframe, risk_reward, confidence.
        """
        global _alerts_paused, _active_signals

        if _alerts_paused:
            logger.info("Alerts paused — skipping signal for %s", signal.get("symbol"))
            return False

        # Cache signal for /signals command
        signal["sent_at"] = datetime.now(IST).strftime("%H:%M:%S")
        _active_signals = ([signal] + _active_signals)[:5]  # keep last 5

        direction = signal.get("direction", "BUY").upper()
        symbol    = signal.get("symbol", "N/A")
        entry     = signal.get("entry_price", 0)
        sl        = signal.get("stop_loss", 0)
        tp        = signal.get("take_profit", 0)
        score     = signal.get("score", 0)
        rr        = signal.get("risk_reward", 0)
        strategy  = signal.get("strategy", "N/A")
        timeframe = signal.get("timeframe", "Swing")
        conf      = signal.get("confidence", 0)

        dir_emoji  = "🚀" if direction == "BUY" else "🔻"
        conviction = "🔥 HIGH" if score >= 80 else "✅ MODERATE" if score >= 65 else "⚠️ LOW"
        time_now   = datetime.now(IST).strftime("%d %b %Y, %I:%M %p IST")

        # Risk in %
        risk_pct = round(abs(entry - sl) / entry * 100, 2) if entry else 0
        rwd_pct  = round(abs(tp - entry) / entry * 100, 2) if entry else 0

        text = (
            f"{dir_emoji} <b>{direction} SIGNAL — {symbol}</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"📊 <b>Strategy:</b> {strategy}\n"
            f"⏱ <b>Timeframe:</b> {timeframe}\n"
            f"🕐 <b>Time:</b> {time_now}\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"▶️ <b>Entry:</b> ₹{entry:,.2f}\n"
            f"🛑 <b>Stop Loss:</b> ₹{sl:,.2f}  <i>(-{risk_pct}%)</i>\n"
            f"🎯 <b>Target:</b> ₹{tp:,.2f}  <i>(+{rwd_pct}%)</i>\n"
            f"📐 <b>Risk:Reward:</b> 1:{rr:.1f}\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"🔥 <b>AI Score:</b> {score}/100  {conviction}\n"
            f"🤖 <b>Confidence:</b> {conf:.0%}\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"💡 <i>Manual execution on Zerodha Kite ↓</i>"
        )

        # Inline buttons for quick action
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(
                    f"📲 Place {direction} on Kite",
                    url=f"https://kite.zerodha.com/chart/ext/ciq/NSE/{symbol}/D"
                ),
            ],
            [
                InlineKeyboardButton("📊 Dashboard", url="http://localhost:5173"),
                InlineKeyboardButton("✅ Noted", callback_data=f"noted_{symbol}"),
            ]
        ]) if HAS_TELEGRAM else None

        logger.info(
            "Signal alert: %s %s @ ₹%.2f (score: %d)",
            direction, symbol, entry, score,
        )
        return await self._send(text, reply_markup=keyboard)

    # ── Risk alert ───────────────────────────────────────────────────

    async def send_risk_alert(self, alert_type: str, details: dict[str, Any]) -> bool:
        """Send a risk management warning."""
        text = (
            f"⚠️ <b>RISK ALERT — {alert_type}</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
        )
        for key, value in details.items():
            text += f"• <b>{key}:</b> {value}\n"
        text += (
            f"━━━━━━━━━━━━━━━━━━\n"
            f"🛡 <i>Check risk dashboard immediately.</i>"
        )
        logger.warning("Risk alert [%s]: %s", alert_type, details)
        return await self._send(text)

    # ── Daily summary ────────────────────────────────────────────────

    async def send_daily_summary(self, summary: dict[str, Any]) -> bool:
        """Send end-of-day performance summary."""
        pnl       = summary.get("total_pnl", 0)
        pnl_emoji = "🟢" if pnl >= 0 else "🔴"
        date_str  = summary.get("date", datetime.now(IST).strftime("%d %b %Y"))

        text = (
            f"📋 <b>DAILY SUMMARY — {date_str}</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"{pnl_emoji} <b>Total P&L:</b> ₹{pnl:,.2f}\n"
            f"📊 <b>Win Rate:</b> {summary.get('win_rate', 0):.1f}%\n"
            f"🔄 <b>Trades Taken:</b> {summary.get('trades_taken', 0)}\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"🏆 <b>Best Trade:</b> {summary.get('best_trade', 'N/A')}\n"
            f"😞 <b>Worst Trade:</b> {summary.get('worst_trade', 'N/A')}\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"💰 <b>Portfolio Value:</b> ₹{summary.get('portfolio_value', 0):,.2f}\n"
            f"📉 <b>Drawdown:</b> {summary.get('drawdown', 0):.2f}%\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"🤖 <i>AI Trading Bot — Auto Report</i>"
        )
        logger.info("Daily summary: P&L ₹%.2f, %d trades", pnl, summary.get("trades_taken", 0))
        return await self._send(text)

    # ── Drawdown alert ───────────────────────────────────────────────

    async def send_drawdown_alert(self, drawdown_pct: float, action: str) -> bool:
        """Send a drawdown warning when thresholds are breached."""
        severity = "🔴 CRITICAL" if drawdown_pct > 10 else "🟡 WARNING"
        text = (
            f"📉 <b>{severity} — DRAWDOWN ALERT</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"📊 <b>Current Drawdown:</b> {drawdown_pct:.2f}%\n"
            f"🎬 <b>Action Taken:</b> {action}\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"💡 <i>Automated risk controls activated.</i>"
        )
        logger.warning("Drawdown alert: %.2f%% — action: %s", drawdown_pct, action)
        return await self._send(text)

    # ── Market crash alert ───────────────────────────────────────────

    async def send_market_crash_alert(self, market: str, change_pct: float) -> bool:
        """Send an alert when a major market index drops sharply."""
        text = (
            f"🚨 <b>MARKET CRASH ALERT</b> 🚨\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"📈 <b>Market:</b> {market}\n"
            f"📉 <b>Change:</b> {change_pct:+.2f}%\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"⚡ <i>Sharp movement detected!</i>\n"
            f"🛡 <i>Review all open positions immediately.</i>"
        )
        logger.critical("Market crash alert: %s at %+.2f%%", market, change_pct)
        return await self._send(text)

    # ── Regime change ────────────────────────────────────────────────

    async def send_regime_change(self, old_regime: str, new_regime: str) -> bool:
        """Notify when the detected market regime changes."""
        regime_emoji = {
            "strong_bullish": "🟢🟢", "bullish": "🟢",
            "neutral": "⚪", "bearish": "🔴",
            "strong_bearish": "🔴🔴", "high_volatility": "⚡",
            "low_volatility": "😴", "trending": "📈", "ranging": "↔️",
        }
        old_e = regime_emoji.get(old_regime, "⚪")
        new_e = regime_emoji.get(new_regime, "⚪")
        text = (
            f"🔄 <b>REGIME CHANGE DETECTED</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"📊 <b>Previous:</b> {old_e} {old_regime.replace('_', ' ').title()}\n"
            f"📊 <b>Current:</b> {new_e} {new_regime.replace('_', ' ').title()}\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"🤖 <i>Strategy weights adjusted automatically.</i>"
        )
        logger.info("Regime change: %s → %s", old_regime, new_regime)
        return await self._send(text)

    # ── Interactive command server ────────────────────────────────────

    def start_command_listener(self) -> None:
        """
        Start the Telegram bot command listener in background.
        Supports: /start /help /signals /status /pause /resume /summary
        """
        if not HAS_TELEGRAM or not self._token:
            logger.info("Telegram command listener disabled (no token)")
            return

        async def _run():
            app = Application.builder().token(self._token).build()

            app.add_handler(CommandHandler("start",   _cmd_start))
            app.add_handler(CommandHandler("help",    _cmd_help))
            app.add_handler(CommandHandler("signals", _cmd_signals))
            app.add_handler(CommandHandler("status",  _cmd_status))
            app.add_handler(CommandHandler("pause",   _cmd_pause))
            app.add_handler(CommandHandler("resume",  _cmd_resume))
            app.add_handler(CommandHandler("summary", _cmd_summary))

            logger.info("Telegram command listener started")
            await app.run_polling(drop_pending_updates=True)

        try:
            loop = asyncio.get_event_loop()
            loop.create_task(_run())
        except Exception as e:
            logger.warning("Could not start Telegram command listener: %s", e)


# ── Standalone command handlers (module-level) ───────────────────────────

async def _cmd_start(update: Any, context: Any) -> None:
    await update.message.reply_text(
        "🤖 <b>AI Trading Bot — Active!</b>\n\n"
        "Main tumhe trading signals bhejunga.\n"
        "Use <b>/help</b> for all commands.\n\n"
        "📊 Dashboard: http://localhost:5173",
        parse_mode="HTML"
    )


async def _cmd_help(update: Any, context: Any) -> None:
    await update.message.reply_text(
        "📋 <b>Available Commands:</b>\n\n"
        "/signals — Latest 5 active signals\n"
        "/status  — Bot + market status\n"
        "/pause   — Pause signal alerts\n"
        "/resume  — Resume signal alerts\n"
        "/summary — Today's P&L summary\n"
        "/help    — This message\n\n"
        "🔗 Dashboard: http://localhost:5173\n"
        "📈 Kite: https://kite.zerodha.com",
        parse_mode="HTML"
    )


async def _cmd_signals(update: Any, context: Any) -> None:
    global _active_signals
    if not _active_signals:
        await update.message.reply_text("⏳ No signals generated yet. Bot is scanning...")
        return

    text = "📡 <b>Latest Signals:</b>\n━━━━━━━━━━━━━━━━━━\n"
    for i, sig in enumerate(_active_signals, 1):
        d = sig.get("direction", "?")
        emoji = "🚀" if d == "BUY" else "🔻"
        text += (
            f"{i}. {emoji} <b>{d} {sig.get('symbol','?')}</b>\n"
            f"   Entry: ₹{sig.get('entry_price',0):,.2f} | "
            f"SL: ₹{sig.get('stop_loss',0):,.2f} | "
            f"Target: ₹{sig.get('take_profit',0):,.2f}\n"
            f"   Score: {sig.get('score',0)}/100 | "
            f"Time: {sig.get('sent_at','?')}\n\n"
        )
    await update.message.reply_text(text, parse_mode="HTML")


async def _cmd_status(update: Any, context: Any) -> None:
    global _alerts_paused
    now    = datetime.now(IST).strftime("%d %b %Y, %I:%M %p IST")
    status = "⏸ PAUSED" if _alerts_paused else "✅ RUNNING"
    await update.message.reply_text(
        f"🤖 <b>Bot Status:</b> {status}\n"
        f"🕐 <b>Time (IST):</b> {now}\n"
        f"📡 <b>Signals cached:</b> {len(_active_signals)}\n\n"
        f"🔗 Dashboard: http://localhost:5173\n"
        f"📡 API: http://localhost:8000/docs",
        parse_mode="HTML"
    )


async def _cmd_pause(update: Any, context: Any) -> None:
    global _alerts_paused
    _alerts_paused = True
    await update.message.reply_text(
        "⏸ <b>Alerts PAUSED.</b>\nUse /resume to restart.",
        parse_mode="HTML"
    )


async def _cmd_resume(update: Any, context: Any) -> None:
    global _alerts_paused
    _alerts_paused = False
    await update.message.reply_text(
        "▶️ <b>Alerts RESUMED.</b>\nSignals will now be sent.",
        parse_mode="HTML"
    )


async def _cmd_summary(update: Any, context: Any) -> None:
    today = datetime.now(IST).strftime("%d %b %Y")
    await update.message.reply_text(
        f"📋 <b>Summary for {today}</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🔄 Signals sent: {len(_active_signals)}\n"
        f"📊 For detailed P&L: http://localhost:5173\n\n"
        f"<i>Full analytics available on dashboard.</i>",
        parse_mode="HTML"
    )
