"""CSV-backed persistence for collected and analyzed Instagram data.

All data lives under a project-root ``Data/`` directory. Column schemas are kept
identical to the legacy pipeline so that historical files remain compatible:

- followers:    ``follower_id, follower_username, timestamp``
- interactions: ``follower_id, follower_username, like, comment``
"""

from pathlib import Path

import pandas as pd

from instabot.logging_config import get_logger

logger = get_logger(__name__)

# Project root is two levels up from this file: <root>/instabot/storage/csv_store.py
DATA_DIR = Path(__file__).resolve().parents[2] / "Data"

FOLLOWERS_CSV = DATA_DIR / "followers_data.csv"
INTERACTIONS_CSV = DATA_DIR / "interactions_data.csv"
ACTIVE_CSV = DATA_DIR / "active_users.csv"
GHOST_CSV = DATA_DIR / "ghost_users.csv"
UNFOLLOWER_CSV = DATA_DIR / "unfollower_data.csv"

FOLLOWER_COLUMNS = ["follower_id", "follower_username", "timestamp"]
INTERACTION_COLUMNS = ["follower_id", "follower_username", "like", "comment"]


def ensure_data_dir() -> None:
    """Create the Data/ directory if it does not exist."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def _save(df: pd.DataFrame, path: Path) -> None:
    """Write a frame to ``path`` (creating Data/ first) and log the action."""
    ensure_data_dir()
    df.to_csv(path, index=False)
    logger.debug("Wrote %d rows to %s", len(df), path.name)


def read_followers() -> pd.DataFrame:
    """Return the accumulated follower snapshots, or an empty frame if none yet."""
    if FOLLOWERS_CSV.exists():
        return pd.read_csv(FOLLOWERS_CSV)
    return pd.DataFrame(columns=FOLLOWER_COLUMNS)


def write_followers(df: pd.DataFrame) -> None:
    """Persist the (history-accumulating) follower snapshots."""
    _save(df, FOLLOWERS_CSV)


def read_interactions() -> pd.DataFrame:
    """Return per-user like/comment tallies, or an empty frame if none yet."""
    if INTERACTIONS_CSV.exists():
        return pd.read_csv(INTERACTIONS_CSV)
    return pd.DataFrame(columns=INTERACTION_COLUMNS)


def write_interactions(df: pd.DataFrame) -> None:
    """Persist per-user like/comment tallies."""
    _save(df, INTERACTIONS_CSV)


def write_active(df: pd.DataFrame) -> None:
    """Persist the active-followers classification."""
    _save(df, ACTIVE_CSV)


def read_active() -> pd.DataFrame:
    """Return the latest active-followers classification, or an empty frame."""
    if ACTIVE_CSV.exists():
        return pd.read_csv(ACTIVE_CSV)
    return pd.DataFrame(columns=INTERACTION_COLUMNS)


def write_ghost(df: pd.DataFrame) -> None:
    """Persist the ghost-followers classification."""
    _save(df, GHOST_CSV)


def read_ghost() -> pd.DataFrame:
    """Return the latest ghost-followers classification, or an empty frame."""
    if GHOST_CSV.exists():
        return pd.read_csv(GHOST_CSV)
    return pd.DataFrame(columns=INTERACTION_COLUMNS)


def write_unfollowers(df: pd.DataFrame) -> None:
    """Persist the detected unfollowers for the latest window."""
    _save(df, UNFOLLOWER_CSV)


def read_unfollowers() -> pd.DataFrame:
    """Return the latest detected unfollowers, or an empty frame."""
    if UNFOLLOWER_CSV.exists():
        return pd.read_csv(UNFOLLOWER_CSV)
    return pd.DataFrame(columns=FOLLOWER_COLUMNS)
