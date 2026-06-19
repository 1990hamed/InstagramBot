"""Persist the Telegram chat id that the bot should report to.

Rather than requiring ``TELEGRAM_CHAT_ID`` in ``.env``, the bot learns the chat
id automatically the first time someone messages it (see ``bot.py``) and stores
it here. The scheduled daily report then reads it back to know where to send.
"""

import json
from pathlib import Path

from instabot.logging_config import get_logger

logger = get_logger(__name__)

# Sit alongside the CSV data so everything lives under one Data/ directory.
DATA_DIR = Path(__file__).resolve().parents[2] / "Data"
CHAT_FILE = DATA_DIR / "telegram_chat.json"


def save_chat_id(chat_id: int | str) -> None:
    """Remember the chat id to send future reports to."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    CHAT_FILE.write_text(json.dumps({"chat_id": str(chat_id)}), encoding="utf-8")
    logger.debug("Saved Telegram chat id %s to %s.", chat_id, CHAT_FILE.name)


def load_chat_id() -> str | None:
    """Return the saved chat id, or ``None`` if the bot hasn't been messaged yet."""
    if not CHAT_FILE.exists():
        logger.debug("No saved chat id file at %s.", CHAT_FILE.name)
        return None
    try:
        data = json.loads(CHAT_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        logger.warning("Failed to read chat id file %s.", CHAT_FILE.name, exc_info=True)
        return None
    chat_id = data.get("chat_id")
    return str(chat_id) if chat_id else None
