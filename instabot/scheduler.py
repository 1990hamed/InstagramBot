"""Daily orchestration: run the full collect → analyze → report pipeline.

A single ``run_daily_job`` ties the Instagram and Telegram sides together. It
can be run once (``run_daily_job``) or scheduled to run every day (``main``).
"""

import os
import time

import schedule
from dotenv import load_dotenv

from instabot.instagram import analysis
from instabot.instagram.client import InstagramClient
from instabot.instagram.collectors import Collector
from instabot.logging_config import get_logger
from instabot.storage import csv_store
from instabot.telegram_report import reporter

load_dotenv()

logger = get_logger(__name__)

# Account whose followers / media are analyzed.
HOME_USERNAME = os.getenv("INSTAGRAM_HOME_USERNAME", os.getenv("INSTAGRAM_USERNAME"))
# Time of day to run, HH:MM 24h local time.
DAILY_RUN_AT = os.getenv("DAILY_RUN_AT", "09:00")


def run_daily_job() -> dict:
    """Run one full pipeline pass and push a report to Telegram."""
    logger.info("===== Starting daily pipeline for @%s =====", HOME_USERNAME)
    try:
        # Scope all storage to this account so switching INSTAGRAM_HOME_USERNAME
        # never mixes another account's follower history into this run.
        csv_store.set_account(HOME_USERNAME)

        ig = InstagramClient(HOME_USERNAME)
        ig.sign_in()

        collector = Collector(ig)
        collector.fetch_followers()
        collector.fetch_media_interactions()
        view_summary = collector.view_stories_and_posts()

        classification = analysis.classify_users(ig)
        leavers = analysis.get_leavers()

        summary = {**view_summary, **classification, **leavers}
        reporter.send_report(summary)
    except Exception:
        logger.exception("Daily pipeline failed.")
        raise
    logger.info("===== Daily pipeline finished =====")
    return summary


def main() -> None:
    """Run the job once immediately, then schedule it daily."""
    run_daily_job()

    schedule.every().day.at(DAILY_RUN_AT).do(run_daily_job)
    logger.info("Scheduled daily report at %s. Press Ctrl+C to stop.", DAILY_RUN_AT)
    try:
        while True:
            schedule.run_pending()
            time.sleep(60)
    except KeyboardInterrupt:
        logger.info("Scheduler stopped by user.")
