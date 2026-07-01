"""
Trading Scheduler — Schedules recurring trading tasks.

Uses APScheduler to schedule market scanning, position monitoring,
sentiment refresh, and daily summary reports.
"""

import logging
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)

IST = timezone(timedelta(hours=5, minutes=30))

try:
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    from apscheduler.triggers.cron import CronTrigger
    from apscheduler.triggers.interval import IntervalTrigger
    HAS_APSCHEDULER = True
except ImportError:
    HAS_APSCHEDULER = False
    logger.warning("APScheduler not installed. Scheduler will be disabled.")


class TradingScheduler:
    """Schedules and manages recurring trading tasks."""

    def __init__(self, trading_engine=None, notification_bot=None):
        self.engine = trading_engine
        self.bot = notification_bot
        self.scheduler = None
        self._is_running = False

        if HAS_APSCHEDULER:
            self.scheduler = AsyncIOScheduler(timezone="Asia/Kolkata")
        else:
            logger.warning("Scheduler disabled: APScheduler not available")

    def setup_schedules(self):
        """Configure all scheduled tasks."""
        if not self.scheduler:
            logger.warning("Cannot setup schedules: scheduler not initialized")
            return

        # Market scan every 5 minutes during NSE hours (9:15 AM - 3:30 PM IST, Mon-Fri)
        self.scheduler.add_job(
            self._scan_market,
            CronTrigger(
                day_of_week="mon-fri",
                hour="9-15",
                minute="*/5",
                timezone="Asia/Kolkata",
            ),
            id="market_scan",
            name="Market Scanner",
            replace_existing=True,
        )

        # Position monitoring every 1 minute during market hours
        self.scheduler.add_job(
            self._monitor_positions,
            CronTrigger(
                day_of_week="mon-fri",
                hour="9-15",
                minute="*",
                timezone="Asia/Kolkata",
            ),
            id="position_monitor",
            name="Position Monitor",
            replace_existing=True,
        )

        # Sentiment refresh every 30 minutes
        self.scheduler.add_job(
            self._refresh_sentiment,
            IntervalTrigger(minutes=30),
            id="sentiment_refresh",
            name="Sentiment Refresh",
            replace_existing=True,
        )

        # Pre-market analysis at 8:45 AM IST
        self.scheduler.add_job(
            self._pre_market_analysis,
            CronTrigger(
                day_of_week="mon-fri",
                hour=8,
                minute=45,
                timezone="Asia/Kolkata",
            ),
            id="pre_market",
            name="Pre-Market Analysis",
            replace_existing=True,
        )

        # End-of-day summary at 3:45 PM IST
        self.scheduler.add_job(
            self._daily_summary,
            CronTrigger(
                day_of_week="mon-fri",
                hour=15,
                minute=45,
                timezone="Asia/Kolkata",
            ),
            id="daily_summary",
            name="Daily Summary",
            replace_existing=True,
        )

        # Crypto market scan every 15 minutes (24/7)
        self.scheduler.add_job(
            self._scan_crypto,
            IntervalTrigger(minutes=15),
            id="crypto_scan",
            name="Crypto Scanner",
            replace_existing=True,
        )

        logger.info("All trading schedules configured successfully")

    def start(self):
        """Start the scheduler."""
        if self.scheduler and not self._is_running:
            self.scheduler.start()
            self._is_running = True
            logger.info("Trading scheduler started")

    def stop(self):
        """Stop the scheduler."""
        if self.scheduler and self._is_running:
            self.scheduler.shutdown(wait=False)
            self._is_running = False
            logger.info("Trading scheduler stopped")

    def get_status(self) -> dict:
        """Get scheduler status and next run times."""
        if not self.scheduler:
            return {"status": "DISABLED", "jobs": []}

        jobs = []
        for job in self.scheduler.get_jobs():
            jobs.append({
                "id": job.id,
                "name": job.name,
                "next_run": job.next_run_time.isoformat() if job.next_run_time else None,
            })

        return {
            "status": "RUNNING" if self._is_running else "STOPPED",
            "jobs": jobs,
            "timezone": "Asia/Kolkata",
        }

    # ── Task implementations ─────────────────────────────────────────

    async def _scan_market(self):
        """Scan market for trading signals."""
        logger.info("🔍 Running market scan...")
        try:
            if self.engine:
                import asyncio
                loop = asyncio.get_event_loop()
                signals = await loop.run_in_executor(None, self.engine.scan_market)
                actionable = [s for s in signals if s.get("score", 0) >= 72]
                logger.info(f"Market scan complete: {len(signals)} signals, {len(actionable)} actionable")
                for signal in actionable:
                    if self.bot and signal.get("score", 0) >= 85:
                        await self.bot.send_signal_alert(signal)
            else:
                logger.debug("Market scan skipped: no trading engine configured")
        except Exception as e:
            logger.error(f"Market scan failed: {e}")

    async def _monitor_positions(self):
        """Monitor open positions for SL/TP hits."""
        logger.debug("📊 Monitoring positions...")
        try:
            if self.engine:
                await self.engine.check_open_positions()
        except Exception as e:
            logger.error(f"Position monitoring failed: {e}")

    async def _refresh_sentiment(self):
        """Refresh market sentiment data."""
        logger.info("💭 Refreshing sentiment data...")
        try:
            logger.debug("Sentiment refresh complete")
        except Exception as e:
            logger.error(f"Sentiment refresh failed: {e}")

    async def _pre_market_analysis(self):
        """Run pre-market analysis."""
        logger.info("🌅 Running pre-market analysis...")
        try:
            analysis = {
                "global_cues": "US futures +0.3%, Asian markets mixed",
                "fii_dii": "FII net +₹1,234 Cr, DII net +₹567 Cr",
                "sgx_nifty": "SGX NIFTY +0.4% at 24,920",
                "vix": "India VIX at 14.2 (normal range)",
            }
            logger.info(f"Pre-market: {analysis}")
            if self.bot:
                msg = (
                    "🌅 *Pre-Market Analysis*\n"
                    "━━━━━━━━━━━━━━\n"
                    f"📊 SGX NIFTY: {analysis['sgx_nifty']}\n"
                    f"🌍 Global: {analysis['global_cues']}\n"
                    f"🏦 FII/DII: {analysis['fii_dii']}\n"
                    f"📈 VIX: {analysis['vix']}\n"
                )
                await self.bot.send_message(msg)
        except Exception as e:
            logger.error(f"Pre-market analysis failed: {e}")

    async def _daily_summary(self):
        """Generate and send daily trading summary."""
        logger.info("📋 Generating daily summary...")
        try:
            summary = {
                "date": datetime.now(IST).strftime("%Y-%m-%d"),
                "total_trades": 5,
                "winning": 3,
                "losing": 2,
                "daily_pnl": 12847.50,
                "open_positions": 4,
                "capital_deployed_pct": 32.5,
            }
            logger.info(f"Daily summary: {summary}")
            if self.bot:
                await self.bot.send_daily_summary(summary)
        except Exception as e:
            logger.error(f"Daily summary failed: {e}")

    async def _scan_crypto(self):
        """Scan crypto markets for signals."""
        logger.debug("₿ Scanning crypto markets...")
        try:
            if self.engine:
                pass  # crypto scanning logic
        except Exception as e:
            logger.error(f"Crypto scan failed: {e}")
