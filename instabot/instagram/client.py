"""Instagram client wrapper: authentication, session reuse, and the
rate-limit / challenge handling machinery.

This preserves the behavior of the legacy ``InstagramBot`` auth half: session
reuse via ``session.json``, relogin handling, and the ``freeze`` cooldown that
sleeps the account through Instagram's challenge / rate-limit responses.
"""

import os
import time
from datetime import datetime, timedelta
from pathlib import Path

from dotenv import load_dotenv
from instagrapi import Client
from instagrapi.exceptions import (
    BadPassword,
    ChallengeRequired,
    FeedbackRequired,
    LoginRequired,
    PleaseWaitFewMinutes,
    RecaptchaChallengeForm,
    ReloginAttemptExceeded,
    SelectContactPointRecoveryForm,
)
from instagrapi.utils import json_value

from instabot.logging_config import get_logger

load_dotenv()

logger = get_logger(__name__)

# Project root is two levels up: <root>/instabot/instagram/client.py
PROJECT_ROOT = Path(__file__).resolve().parents[2]

LOGIN_EXCEPTIONS = (
    ReloginAttemptExceeded,
    LoginRequired,
    FeedbackRequired,
    PleaseWaitFewMinutes,
    BadPassword,
    ChallengeRequired,
    SelectContactPointRecoveryForm,
    RecaptchaChallengeForm,
)


class InstagramClient:
    """Authenticated ``instagrapi`` client for a single home account.

    ``username`` is the account to analyze; login credentials come from the
    ``INSTAGRAM_USERNAME`` / ``INSTAGRAM_PASSWORD`` environment variables.
    """

    def __init__(self, username: str):
        self.username = username
        self.login_username = os.getenv("INSTAGRAM_USERNAME")
        self.password = os.getenv("INSTAGRAM_PASSWORD")
        self.client = Client()
        self.session_file = PROJECT_ROOT / "session.json"

    def configure_client(self) -> None:
        self.client.delay_range = [1, 3]
        if self.session_file.exists():
            self.client.load_settings(self.session_file)

    def sign_in(self) -> None:
        logger.info(
            "Signing in as %s (analyzing @%s)", self.login_username, self.username
        )
        try:
            self.configure_client()
            if self.session_file.exists():
                logger.debug("Existing session file found, reusing session.")
                self.login_with_session()
            else:
                logger.debug("No session file, performing first-time login.")
                self.first_time_login()
        except LOGIN_EXCEPTIONS as e:
            logger.warning("Login raised %s, handling.", type(e).__name__)
            self.handle_exception(e)

    def login_with_session(self) -> None:
        session = self.client.load_settings(self.session_file)
        if session:
            try:
                self.client.set_settings(session)
                self.client.login(self.login_username, self.password)
                self.validate_session()
            except LoginRequired:
                self.handle_login_required()

    def validate_session(self) -> None:
        try:
            self.client.get_timeline_feed()
            logger.info("Logged in as %s (session validated).", self.login_username)
        except LoginRequired:
            logger.warning("Session invalid (LoginRequired), re-logging in.")
            self.handle_login_required()

    def handle_login_required(self) -> None:
        logger.info("Re-logging in and refreshing client settings.")
        self.client.relogin()
        self.update_client_settings(self.client.get_settings())

    def first_time_login(self) -> None:
        self.client.login(self.login_username, self.password)
        self.client.dump_settings(self.session_file)
        logger.info(
            "Login successful, session settings saved to %s.", self.session_file
        )

    def handle_exception(self, e: Exception) -> bool:
        logger.debug("handle_exception dispatching %s: %s", type(e).__name__, e)
        if isinstance(e, BadPassword):
            logger.error("BadPassword encountered.", exc_info=e)
            if self.client.relogin_attempt > 0:
                self.freeze(str(e), days=7)
                raise ReloginAttemptExceeded(e)
            self.rebuild_client_settings()
            return self.update_client_settings(self.client.get_settings())
        elif isinstance(e, LoginRequired):
            logger.warning("LoginRequired encountered, re-logging in.", exc_info=e)
            self.client.relogin()
            return self.update_client_settings(self.client.get_settings())
        elif isinstance(e, ChallengeRequired):
            api_path = json_value(self.client.last_json, "challenge", "api_path")
            logger.warning("ChallengeRequired encountered (api_path=%s).", api_path)
            if api_path == "/challenge/":
                self.rebuild_client_settings()
            else:
                try:
                    self.client.challenge_resolve(self.client.last_json)
                    logger.info("Challenge resolved automatically.")
                except ChallengeRequired as challenge_error:
                    logger.error("Manual challenge required, freezing 2 days.")
                    self.freeze("Manual Challenge Required", days=2)
                    raise challenge_error
                except (
                    SelectContactPointRecoveryForm,
                    RecaptchaChallengeForm,
                ) as challenge_error:
                    logger.error(
                        "Unresolvable challenge (%s), freezing 4 days.",
                        type(challenge_error).__name__,
                    )
                    self.freeze(str(challenge_error), days=4)
                    raise challenge_error
                self.update_client_settings(self.client.get_settings())
            return True
        elif isinstance(e, FeedbackRequired):
            message = self.client.last_json["feedback_message"]
            logger.warning("FeedbackRequired: %s", message)
            if "This action was blocked. Please try again later" in message:
                self.freeze(message, hours=12)
            elif "We restrict certain activity to protect our community" in message:
                # 6 hours is not enough
                self.freeze(message, hours=12)
            elif "Your account has been temporarily blocked" in message:
                self.freeze(message)
        elif isinstance(e, PleaseWaitFewMinutes):
            logger.warning("PleaseWaitFewMinutes, rebuilding settings and freezing 1h.")
            self.rebuild_client_settings()
            self.freeze(str(e), hours=1)
        raise e

    def update_client_settings(self, param: dict) -> None:
        old_session = param
        self.client.set_settings({})
        self.client.set_uuids(old_session["uuids"])
        logger.debug("Client settings reset and uuids restored.")

    def rebuild_client_settings(self) -> None:
        logger.info("Rebuilding client settings: deleting session and re-logging in.")
        self.session_file.unlink(missing_ok=True)
        self.first_time_login()

    @staticmethod
    def freeze(reason: str, hours: int = 0, days: int = 0) -> None:
        freeze_duration = timedelta(hours=hours, days=days).total_seconds()
        end_time = datetime.now() + timedelta(seconds=freeze_duration)
        logger.warning(
            "Account frozen until %s (%.0f seconds) due to: %s",
            end_time,
            freeze_duration,
            reason,
        )
        time.sleep(freeze_duration)
        logger.info("Freeze period ended, resuming operations.")
