"""Data collection against the home Instagram account.

Collects follower snapshots (timestamped, history-accumulating), per-user
like/comment tallies across the account's own media, and marks the account's
own stories and recent posts as seen.
"""

from datetime import datetime

import pandas as pd

from instabot.instagram.client import InstagramClient
from instabot.logging_config import get_logger
from instabot.storage import csv_store

logger = get_logger(__name__)


class Collector:
    """Pulls follower and interaction data using an authenticated client."""

    def __init__(self, ig: InstagramClient):
        self.ig = ig
        self.client = ig.client
        self.username = ig.username

    def _user_id(self) -> str:
        return str(self.client.user_id_from_username(self.username))

    def fetch_followers(self, keep_snapshots: int = 30) -> pd.DataFrame:
        """Append a *complete* timestamped follower snapshot to the history file.

        Every follower the account currently has gets one row tagged with this
        run's timestamp. Unlike the old "only new IDs" approach, this records a
        full snapshot each run, so :func:`analysis.get_leavers` can diff the
        latest snapshot against the previous one (see that function).

        Older snapshots beyond ``keep_snapshots`` distinct timestamps are pruned
        so the file does not grow unbounded; two snapshots are enough for the
        diff, the rest are kept for history.
        """
        logger.info("Fetching follower snapshot for @%s.", self.username)
        followers = self.client.user_followers(user_id=self._user_id(), amount=0)
        timestamp = datetime.now()
        logger.debug("Instagram returned %d followers.", len(followers))

        snapshot = pd.DataFrame(
            [
                {
                    "follower_id": follower.pk,
                    "follower_username": follower.username,
                    "timestamp": timestamp,
                }
                for follower in followers.values()
            ],
            columns=csv_store.FOLLOWER_COLUMNS,
        )

        history = csv_store.read_followers()
        follower_df = pd.concat([history, snapshot], ignore_index=True)

        # Keep only the most recent ``keep_snapshots`` distinct snapshots.
        timestamps = follower_df["timestamp"].astype(str)
        keep = set(sorted(timestamps.unique())[-keep_snapshots:])
        follower_df = follower_df[timestamps.isin(keep)].reset_index(drop=True)

        logger.info(
            "Recorded snapshot of %d follower(s); %d distinct snapshots in history.",
            len(snapshot),
            follower_df["timestamp"].astype(str).nunique(),
        )
        csv_store.write_followers(follower_df)
        return follower_df

    def fetch_media_interactions(self) -> pd.DataFrame:
        """Tally per-user like and comment counts across the account's media."""
        logger.info("Fetching media interactions for @%s.", self.username)
        user_id = self._user_id()
        interaction_df = csv_store.read_interactions()
        likes_list: list[dict] = []
        comments_list: list[dict] = []
        end_cursor = None
        media_processed = 0

        try:
            while True:
                media_list, end_cursor = self.client.user_medias_paginated(
                    user_id=user_id, amount=10, end_cursor=end_cursor
                )
                logger.debug("Fetched a page of %d media.", len(media_list))

                for media in media_list:
                    media_processed += 1
                    for user in self.client.media_likers(media.id):
                        if user.pk in interaction_df["follower_id"].values:
                            idx = interaction_df.index[
                                interaction_df["follower_id"] == user.pk
                            ].tolist()[0]
                            interaction_df.at[idx, "like"] += 1
                        else:
                            likes_list.append(
                                {
                                    "follower_id": user.pk,
                                    "follower_username": user.username,
                                    "like": 1,
                                    "comment": 0,
                                }
                            )

                    for comment in self.client.media_comments(media.id):
                        if comment.user.pk in interaction_df["follower_id"].values:
                            idx = interaction_df.index[
                                interaction_df["follower_id"] == comment.user.pk
                            ].tolist()[0]
                            interaction_df.at[idx, "comment"] += 1
                        else:
                            comments_list.append(
                                {
                                    "follower_id": comment.user.pk,
                                    "follower_username": comment.user.username,
                                    "like": 0,
                                    "comment": 1,
                                }
                            )

                if likes_list:
                    interaction_df = pd.concat(
                        [interaction_df, pd.DataFrame(likes_list)], ignore_index=True
                    )
                    likes_list = []
                if comments_list:
                    interaction_df = pd.concat(
                        [interaction_df, pd.DataFrame(comments_list)],
                        ignore_index=True,
                    )
                    comments_list = []

                if not end_cursor:
                    break

        except Exception:
            logger.exception("Error while fetching media interactions.")

        interaction_df = (
            interaction_df.groupby(["follower_id", "follower_username"])
            .sum()
            .reset_index()
        )
        logger.info(
            "Processed %d media; %d users with interactions.",
            media_processed,
            len(interaction_df),
        )
        csv_store.write_interactions(interaction_df)
        return interaction_df

    def view_stories_and_posts(self, posts_amount: int = 5) -> dict:
        """Mark the home account's own stories and recent posts as seen.

        Returns a small summary with the counts of stories and posts viewed.
        """
        logger.info("Viewing stories and posts for @%s.", self.username)
        user_id = self._user_id()
        stories_seen = 0
        posts_seen = 0

        try:
            stories = self.client.user_stories(user_id=user_id)
            if stories:
                self.client.story_seen([story.pk for story in stories])
                stories_seen = len(stories)
        except Exception:
            logger.exception("Error viewing stories.")

        try:
            medias = self.client.user_medias(user_id=user_id, amount=posts_amount)
            for media in medias:
                self.client.media_seen([media.pk])
                posts_seen += 1
        except Exception:
            logger.exception("Error viewing posts.")

        logger.info("Viewed %d stories and %d posts.", stories_seen, posts_seen)
        return {"stories_seen": stories_seen, "posts_seen": posts_seen}
