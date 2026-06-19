"""Central logging configuration for the whole project.

Every module gets its logger via :func:`get_logger`, and the logging stack
itself is configured exactly once by :func:`setup_logging` (idempotent, so it
is safe to call from each entry point). Logs go to two places:

- the console (stderr), at the level given by ``LOG_LEVEL`` (default ``INFO``);
- a rotating file under ``Logs/instabot.log``, always at ``DEBUG`` so the file
  keeps the full, detailed history regardless of the console verbosity.

The ``instagrapi`` and ``httpx`` libraries are noisy; their loggers are pinned
to ``WARNING`` so they don't drown out the bot's own action log.

Usage in any module::

    from instabot.logging_config import get_logger

    logger = get_logger(__name__)
    logger.info("did the thing")
"""

import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# Project root is one level up: <root>/instabot/logging_config.py
PROJECT_ROOT = Path(__file__).resolve().parents[1]
LOG_DIR = PROJECT_ROOT / "Logs"
LOG_FILE = LOG_DIR / "instabot.log"

# 5 MB per file, keep 5 old files (~25 MB of history at most).
MAX_BYTES = 5 * 1024 * 1024
BACKUP_COUNT = 5

_LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# Libraries we don't want flooding our logs at DEBUG/INFO.
_NOISY_LIBRARIES = ("instagrapi", "httpx", "httpcore", "urllib3", "private_request")

_configured = False


def setup_logging() -> None:
    """Configure the root logger once: console + rotating file handlers.

    Idempotent — repeated calls are no-ops, so every entry point can call it
    defensively without stacking handlers.
    """
    global _configured
    if _configured:
        return

    LOG_DIR.mkdir(parents=True, exist_ok=True)

    console_level = os.getenv("LOG_LEVEL", "INFO").upper()
    formatter = logging.Formatter(_LOG_FORMAT, datefmt=_DATE_FORMAT)

    root = logging.getLogger()
    # Root passes everything through; handlers decide their own thresholds.
    root.setLevel(logging.DEBUG)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(console_level)
    console_handler.setFormatter(formatter)
    root.addHandler(console_handler)

    file_handler = RotatingFileHandler(
        LOG_FILE,
        maxBytes=MAX_BYTES,
        backupCount=BACKUP_COUNT,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    root.addHandler(file_handler)

    for name in _NOISY_LIBRARIES:
        logging.getLogger(name).setLevel(logging.WARNING)

    _configured = True


def get_logger(name: str) -> logging.Logger:
    """Return a logger for ``name``, ensuring logging is configured first."""
    setup_logging()
    return logging.getLogger(name)
