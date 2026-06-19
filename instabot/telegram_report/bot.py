"""Interactive Telegram bot.

You message the bot; it replies with whatever section you ask for. The chat id
is captured automatically from your first message (no ``TELEGRAM_CHAT_ID`` in
``.env`` needed) and saved so the scheduled daily report knows where to send.

The UI is a modern inline-keyboard menu — each button fetches one section
(unfollowers, active, ghost, views, overview) rendered as clean HTML.

    uv run python -m instabot.telegram_report.bot   # run the interactive bot
"""

import os

from dotenv import load_dotenv
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from instabot.logging_config import get_logger
from instabot.storage import csv_store
from instabot.telegram_report import chat_store, sections

load_dotenv()

logger = get_logger(__name__)

# Each button -> (label, section key). The section key is also the callback data.
MENU = [
    ("📊 Overview", "overview"),
    ("👋 Unfollowers", "unfollowers"),
    ("🔥 Active Followers", "active"),
    ("👻 Ghost Followers", "ghost"),
    ("👀 Story & Post Views", "views"),
]

WELCOME = (
    "<b>👋 Welcome to your Instagram Analytics bot!</b>\n"
    "━━━━━━━━━━━━━━━\n"
    "Tap a button below and I'll send that section.\n"
    "Each reply is one clean, self-contained card.\n\n"
    "<i>You can re-open this menu anytime with /menu.</i>"
)


def _menu_markup() -> InlineKeyboardMarkup:
    """Build the inline keyboard, one button per row for a tidy mobile layout."""
    rows = [[InlineKeyboardButton(label, callback_data=key)] for label, key in MENU]
    return InlineKeyboardMarkup(rows)


async def _remember_chat(update: Update) -> None:
    """Persist the chat id so scheduled reports can reach this chat."""
    if update.effective_chat:
        logger.debug("Remembering chat id %s.", update.effective_chat.id)
        chat_store.save_chat_id(update.effective_chat.id)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _remember_chat(update)
    await update.message.reply_text(
        WELCOME, parse_mode=ParseMode.HTML, reply_markup=_menu_markup()
    )


async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _remember_chat(update)
    await update.message.reply_text(
        "<b>📋 Menu</b>\nWhat would you like to see?",
        parse_mode=ParseMode.HTML,
        reply_markup=_menu_markup(),
    )


async def on_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle an inline-keyboard tap: send the requested section as its own card."""
    query = update.callback_query
    await query.answer()  # stop the button's loading spinner
    await _remember_chat(update)

    logger.info("Button tapped: %r", query.data)
    text = sections.section_for(query.data)
    # Send a fresh message so each request is its own standalone section,
    # then re-show the menu for the next request.
    await query.message.reply_text(text, parse_mode=ParseMode.HTML)
    await query.message.reply_text(
        "<i>Pick another section:</i>",
        parse_mode=ParseMode.HTML,
        reply_markup=_menu_markup(),
    )


async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Any free-text message just (re)shows the menu and saves the chat id."""
    await _remember_chat(update)
    await update.message.reply_text(
        "Tap a button to get a report 👇",
        reply_markup=_menu_markup(),
    )


def build_application() -> Application:
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN must be set in the environment.")

    # Serve sections from the configured home account's data folder.
    csv_store.set_account(
        os.getenv("INSTAGRAM_HOME_USERNAME") or os.getenv("INSTAGRAM_USERNAME")
    )

    app = Application.builder().token(token).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("menu", menu))
    app.add_handler(CallbackQueryHandler(on_button))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))
    return app


def main() -> None:
    """Run the interactive bot until interrupted (long-polling)."""
    app = build_application()
    logger.info("Interactive Telegram bot running (long-polling). Ctrl+C to stop.")
    app.run_polling()


if __name__ == "__main__":
    main()
