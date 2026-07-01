#!/usr/bin/env python3
"""
🤖 Telegram Bot Quick Setup Script
Run: python3 setup_telegram.py
"""

import os
import sys
import asyncio
import json

def print_banner():
    print("""
╔══════════════════════════════════════════════╗
║     🤖 AI Trading Bot — Telegram Setup       ║
╚══════════════════════════════════════════════╝
""")

def step(n, text):
    print(f"\n{'='*50}")
    print(f"  STEP {n}: {text}")
    print(f"{'='*50}")

async def test_bot(token: str, chat_id: str) -> bool:
    """Send a test message to verify bot works."""
    try:
        from telegram import Bot
        bot = Bot(token=token)
        me = await bot.get_me()
        print(f"\n  ✅ Bot found: @{me.username} ({me.first_name})")

        msg = await bot.send_message(
            chat_id=chat_id,
            text=(
                "🎉 <b>AI Trading Bot Connected!</b>\n\n"
                "✅ Setup successful!\n"
                "📡 You will receive:\n"
                "  • BUY/SELL signals with entry/SL/target\n"
                "  • Risk alerts\n"
                "  • Daily P&L summary\n"
                "  • Market crash alerts\n\n"
                "📋 Commands:\n"
                "  /signals - Latest signals\n"
                "  /status  - Bot status\n"
                "  /pause   - Pause alerts\n"
                "  /resume  - Resume alerts\n"
                "  /help    - All commands\n\n"
                "🚀 <i>Bot is now monitoring markets!</i>"
            ),
            parse_mode="HTML"
        )
        print(f"  ✅ Test message sent! Message ID: {msg.message_id}")
        return True
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return False


def get_chat_id_instructions():
    print("""
  HOW TO GET YOUR CHAT ID:
  ─────────────────────────────────────
  Method 1 (Easiest):
    1. Telegram mein @userinfobot ko message karo
    2. Bot tumhara ID reply karega
    3. Woh ID yahan paste karo

  Method 2:
    1. Apne Bot ko /start message bhejo
    2. Browser mein kholo:
       https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates
    3. "id" field dekho under "chat"
  ─────────────────────────────────────
""")


def update_env_file(token: str, chat_id: str):
    """Update or create .env file with Telegram credentials."""
    env_path = os.path.join(os.path.dirname(__file__), ".env")

    # Read existing .env if present
    lines = []
    if os.path.exists(env_path):
        with open(env_path, "r") as f:
            lines = f.readlines()

    # Update or add Telegram lines
    updated_token = False
    updated_chat = False
    new_lines = []

    for line in lines:
        if line.startswith("TELEGRAM_BOT_TOKEN="):
            new_lines.append(f"TELEGRAM_BOT_TOKEN={token}\n")
            updated_token = True
        elif line.startswith("TELEGRAM_CHAT_ID="):
            new_lines.append(f"TELEGRAM_CHAT_ID={chat_id}\n")
            updated_chat = True
        else:
            new_lines.append(line)

    if not updated_token:
        new_lines.append(f"\nTELEGRAM_BOT_TOKEN={token}\n")
    if not updated_chat:
        new_lines.append(f"TELEGRAM_CHAT_ID={chat_id}\n")

    with open(env_path, "w") as f:
        f.writelines(new_lines)

    print(f"\n  ✅ .env file updated: {env_path}")


async def main():
    print_banner()

    # ── STEP 1: Install library ──────────────────────────────────────
    step(1, "Check python-telegram-bot library")
    try:
        import telegram
        print(f"  ✅ python-telegram-bot installed (version {telegram.__version__})")
    except ImportError:
        print("  ⚠️  python-telegram-bot not installed. Installing...")
        os.system(f"{sys.executable} -m pip install 'python-telegram-bot>=20.0' -q")
        print("  ✅ Installed!")

    # ── STEP 2: BotFather instructions ───────────────────────────────
    step(2, "Create Telegram Bot (via @BotFather)")
    print("""
  Agar bot nahi banaya to:
  ─────────────────────────────────────
  1. Telegram mein @BotFather ko message karo
  2. /newbot type karo
  3. Bot ka naam dena (e.g. "My Trading Bot")
  4. Username dena (e.g. "mytrading_signals_bot")
  5. Token milega — copy karo (1234567890:ABCdefGHI...)
  ─────────────────────────────────────
""")

    # ── STEP 3: Get Token ────────────────────────────────────────────
    step(3, "Enter Your Bot Token")
    token = input("  Paste Bot Token: ").strip()

    if not token or ":" not in token:
        print("  ❌ Invalid token format! Token should look like: 1234567890:ABCdef...")
        sys.exit(1)

    # ── STEP 4: Get Chat ID ──────────────────────────────────────────
    step(4, "Enter Your Chat ID")
    get_chat_id_instructions()
    chat_id = input("  Paste Chat ID (e.g. 123456789): ").strip()

    if not chat_id:
        print("  ❌ Chat ID required!")
        sys.exit(1)

    # ── STEP 5: Test connection ──────────────────────────────────────
    step(5, "Testing Connection...")
    success = await test_bot(token, chat_id)

    if not success:
        print("\n  ❌ Connection failed! Check token and chat ID.")
        retry = input("\n  Retry? (y/n): ").strip().lower()
        if retry != "y":
            sys.exit(1)

    # ── STEP 6: Save to .env ─────────────────────────────────────────
    step(6, "Saving to .env file")
    update_env_file(token, chat_id)

    # ── Done ─────────────────────────────────────────────────────────
    print(f"""
{'='*50}
  🎉 TELEGRAM SETUP COMPLETE!
{'='*50}

  ✅ Bot Token: {token[:20]}...
  ✅ Chat ID: {chat_id}
  ✅ Test message sent to your Telegram

  NEXT STEPS:
  1. Backend restart karo:
     cd backend && python3 -m uvicorn app.main:app --reload

  2. Telegram mein commands try karo:
     /start   → Welcome message
     /signals → Latest signals
     /status  → Bot status
     /help    → All commands

  📊 Dashboard: http://localhost:5173
  📡 API Docs:  http://localhost:8000/docs
{'='*50}
""")


if __name__ == "__main__":
    asyncio.run(main())
