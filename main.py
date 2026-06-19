"""Entry point for the Instagram analytics + Telegram reporting bot.

By default this runs a single pipeline pass (collect → analyze → report) and
exits. Pass ``--schedule`` to instead run once and then keep running the job
daily at the configured time (``DAILY_RUN_AT``). Pass ``--bot`` to run the
interactive Telegram bot that serves report sections on demand.

    uv run python main.py              # one-off run
    uv run python main.py --schedule   # run daily
    uv run python main.py --bot        # interactive Telegram bot
"""

import sys

from instabot import scheduler
from instabot.logging_config import get_logger
from instabot.telegram_report import bot

logger = get_logger(__name__)


def main() -> None:
    if "--bot" in sys.argv:
        logger.info("Starting in interactive bot mode.")
        bot.main()
    elif "--schedule" in sys.argv:
        logger.info("Starting in scheduled mode.")
        scheduler.main()
    else:
        logger.info("Starting in one-off run mode.")
        summary = scheduler.run_daily_job()
        logger.info("Run summary: %s", summary)


if __name__ == "__main__":
    main()
