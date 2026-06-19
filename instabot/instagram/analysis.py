"""Analysis over collected follower / interaction data.

- ``classify_users``: split followers into active (heavy likers/commenters) and
  ghost (near-zero interaction) based on thresholds relative to the account's
  total media count.
- ``get_leavers``: diff the most recent follower snapshot against older ones to
  detect who unfollowed in the last 24 hours.
"""

import pandas as pd

from instabot.instagram.client import InstagramClient
from instabot.logging_config import get_logger
from instabot.storage import csv_store

logger = get_logger(__name__)

ACTIVE_RATIO = 0.5
GHOST_RATIO = 0.01


def classify_users(ig: InstagramClient) -> dict:
    """Classify followers into active/ghost and persist both to CSV.

    Returns a summary with counts and a few representative usernames.
    """
    logger.info("Classifying followers into active / ghost for @%s.", ig.username)
    user_id = str(ig.client.user_id_from_username(ig.username))
    total_medias = len(ig.client.user_medias(user_id=user_id, amount=9999))

    active_threshold = total_medias * ACTIVE_RATIO
    ghost_threshold = total_medias * GHOST_RATIO
    logger.debug(
        "total_medias=%d active_threshold=%.2f ghost_threshold=%.2f",
        total_medias,
        active_threshold,
        ghost_threshold,
    )

    interaction_df = csv_store.read_interactions()

    # Total engagement per user; classify on the sum of likes + comments so a
    # follower is never both active and ghost. (A pure OR on each column would
    # flag almost everyone as ghost, since most users have zero of either.)
    engagement = interaction_df["like"] + interaction_df["comment"]

    active_users = interaction_df[engagement >= active_threshold]
    ghost_users = interaction_df[engagement <= ghost_threshold]

    csv_store.write_active(active_users)
    csv_store.write_ghost(ghost_users)
    logger.info(
        "Classified %d active and %d ghost followers.",
        len(active_users),
        len(ghost_users),
    )

    return {
        "active_count": len(active_users),
        "active_usernames": active_users["follower_username"].tolist(),
        "ghost_count": len(ghost_users),
        "ghost_usernames": ghost_users["follower_username"].tolist(),
    }


def get_leavers() -> dict:
    """Detect unfollowers by diffing the two most recent follower snapshots.

    Each pipeline run records a complete follower snapshot (see
    ``Collector.fetch_followers``). Unfollowers are whoever appeared in the
    previous snapshot but not in the latest one. This is robust to re-follows
    and does not depend on a fixed 24h window — it compares actual successive
    snapshots, however far apart they were taken.

    Returns a summary with the unfollower count and usernames.
    """
    logger.info("Detecting unfollowers from the last two snapshots.")
    follower_df = csv_store.read_followers()
    if follower_df.empty:
        logger.warning("No follower history yet; cannot detect unfollowers.")
        csv_store.write_unfollowers(follower_df)
        return {"unfollower_count": 0, "unfollower_usernames": []}

    follower_df["timestamp"] = pd.to_datetime(follower_df["timestamp"])
    snapshots = sorted(follower_df["timestamp"].unique())
    if len(snapshots) < 2:
        logger.info("Only one snapshot so far; no previous snapshot to diff.")
        empty = follower_df.iloc[0:0]
        csv_store.write_unfollowers(empty)
        return {"unfollower_count": 0, "unfollower_usernames": []}

    previous_ts, latest_ts = snapshots[-2], snapshots[-1]
    previous = follower_df[follower_df["timestamp"] == previous_ts]
    latest_ids = set(follower_df[follower_df["timestamp"] == latest_ts]["follower_id"])

    leavers = set(previous["follower_id"]).difference(latest_ids)
    unfollower_df = previous[previous["follower_id"].isin(leavers)].reset_index(
        drop=True
    )

    csv_store.write_unfollowers(unfollower_df)
    logger.info(
        "Detected %d unfollower(s) between %s and %s.",
        len(unfollower_df),
        previous_ts,
        latest_ts,
    )

    return {
        "unfollower_count": len(unfollower_df),
        "unfollower_usernames": unfollower_df["follower_username"].tolist(),
    }
