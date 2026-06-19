"""Telegram reporting: format the daily analysis summary and push it to a chat.

Reads ``TELEGRAM_BOT_TOKEN`` from the environment. The destination chat id is
*not* configured in ``.env`` — it is learned automatically the first time you
message the bot (see ``bot.py``) and read back here via ``chat_store``.
"""

import asyncio
import os

from dotenv import load_dotenv
from telegram import Bot
from telegram.constants import ParseMode

from instabot.logging_config import get_logger
from instabot.telegram_report import chat_store, sections

load_dotenv()

logger = get_logger(__name__)


def build_message(summary: dict) -> str:
    """Build the daily report text (Telegram HTML) from an analysis summary."""
    return sections.build_full_report(summary)


async def send_daily_report(summary: dict) -> None:
    """Asynchronously push the formatted report to the auto-saved chat."""
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN must be set in the environment.")

    chat_id = chat_store.load_chat_id()
    if not chat_id:
        logger.error("No Telegram chat id saved; cannot send report.")
        raise RuntimeError(
            "No Telegram chat id saved yet. Message the bot once "
            "(run `uv run python -m instabot.telegram_report.bot` and send /start) "
            "so it can capture the chat id, then re-run the report."
        )

    logger.info("Sending daily report to chat %s.", chat_id)
    bot = Bot(token=token)
    async with bot:
        await bot.send_message(
            chat_id=chat_id,
            text=build_message(summary),
            parse_mode=ParseMode.HTML,
        )
    logger.info("Daily report sent.")


def send_report(summary: dict) -> None:
    """Synchronous wrapper so the scheduler can send a report without asyncio."""
    asyncio.run(send_daily_report(summary))
