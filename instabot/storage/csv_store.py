"""CSV-backed persistence for collected and analyzed Instagram data.

Data is partitioned **per Instagram account** under ``Data/<account>/`` so that
switching ``INSTAGRAM_HOME_USERNAME`` never mixes one account's follower history
into another's. Each account keeps its own files (and history), and switching
back to a previous account picks its data up again losslessly.

Column schemas are kept identical to the legacy pipeline:

- followers:    ``follower_id, follower_username, timestamp``
- interactions: ``follower_id, follower_username, like, comment``

The *active account* is process-global. It defaults to a sanitized
``INSTAGRAM_HOME_USERNAME`` (falling back to ``INSTAGRAM_USERNAME``) and can be
set explicitly via :func:`set_account` by the scheduler and the Telegram bot so
that on-disk reads resolve to the right account's folder.
"""

import os
import re
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv

from instabot.logging_config import get_logger

load_dotenv()

logger = get_logger(__name__)

# Project root is two levels up from this file: <root>/instabot/storage/csv_store.py
DATA_ROOT = Path(__file__).resolve().parents[2] / "Data"

FOLLOWER_COLUMNS = ["follower_id", "follower_username", "timestamp"]
INTERACTION_COLUMNS = ["follower_id", "follower_username", "like", "comment"]


def _sanitize(account: str | None) -> str:
    """Turn a username into a safe folder name (or ``_default`` if unset)."""
    if not account:
        return "_default"
    # Instagram usernames are [a-zA-Z0-9._]; strip anything else defensively.
    cleaned = re.sub(r"[^A-Za-z0-9._-]", "_", account.strip().lower())
    return cleaned or "_default"


# The account whose data the read/write helpers operate on. Defaults to the
# configured home account so scripts that never call set_account still work.
_ACTIVE_ACCOUNT = _sanitize(
    os.getenv("INSTAGRAM_HOME_USERNAME") or os.getenv("INSTAGRAM_USERNAME")
)


def set_account(account: str | None) -> None:
    """Point all subsequent reads/writes at ``account``'s data folder."""
    global _ACTIVE_ACCOUNT
    _ACTIVE_ACCOUNT = _sanitize(account)
    logger.debug("Active data account set to %r.", _ACTIVE_ACCOUNT)


def get_account() -> str:
    """Return the sanitized name of the currently active account."""
    return _ACTIVE_ACCOUNT


def data_dir() -> Path:
    """Return the active account's data directory (``Data/<account>/``)."""
    return DATA_ROOT / _ACTIVE_ACCOUNT


def followers_csv() -> Path:
    return data_dir() / "followers_data.csv"


def interactions_csv() -> Path:
    return data_dir() / "interactions_data.csv"


def active_csv() -> Path:
    return data_dir() / "active_users.csv"


def ghost_csv() -> Path:
    return data_dir() / "ghost_users.csv"


def unfollower_csv() -> Path:
    return data_dir() / "unfollower_data.csv"


def ensure_data_dir() -> None:
    """Create the active account's data directory if it does not exist."""
    data_dir().mkdir(parents=True, exist_ok=True)


def _save(df: pd.DataFrame, path: Path) -> None:
    """Write a frame to ``path`` (creating the account dir first) and log it."""
    ensure_data_dir()
    df.to_csv(path, index=False)
    logger.debug("Wrote %d rows to %s/%s", len(df), _ACTIVE_ACCOUNT, path.name)


def read_followers() -> pd.DataFrame:
    """Return the accumulated follower snapshots, or an empty frame if none yet."""
    path = followers_csv()
    if path.exists():
        return pd.read_csv(path)
    return pd.DataFrame(columns=FOLLOWER_COLUMNS)


def write_followers(df: pd.DataFrame) -> None:
    """Persist the (history-accumulating) follower snapshots."""
    _save(df, followers_csv())


def read_interactions() -> pd.DataFrame:
    """Return per-user like/comment tallies, or an empty frame if none yet."""
    path = interactions_csv()
    if path.exists():
        return pd.read_csv(path)
    return pd.DataFrame(columns=INTERACTION_COLUMNS)


def write_interactions(df: pd.DataFrame) -> None:
    """Persist per-user like/comment tallies."""
    _save(df, interactions_csv())


def write_active(df: pd.DataFrame) -> None:
    """Persist the active-followers classification."""
    _save(df, active_csv())


def read_active() -> pd.DataFrame:
    """Return the latest active-followers classification, or an empty frame."""
    path = active_csv()
    if path.exists():
        return pd.read_csv(path)
    return pd.DataFrame(columns=INTERACTION_COLUMNS)


def write_ghost(df: pd.DataFrame) -> None:
    """Persist the ghost-followers classification."""
    _save(df, ghost_csv())


def read_ghost() -> pd.DataFrame:
    """Return the latest ghost-followers classification, or an empty frame."""
    path = ghost_csv()
    if path.exists():
        return pd.read_csv(path)
    return pd.DataFrame(columns=INTERACTION_COLUMNS)


def write_unfollowers(df: pd.DataFrame) -> None:
    """Persist the detected unfollowers for the latest window."""
    _save(df, unfollower_csv())


def read_unfollowers() -> pd.DataFrame:
    """Return the latest detected unfollowers, or an empty frame."""
    path = unfollower_csv()
    if path.exists():
        return pd.read_csv(path)
    return pd.DataFrame(columns=FOLLOWER_COLUMNS)
