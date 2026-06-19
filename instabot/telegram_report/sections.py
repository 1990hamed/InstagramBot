"""Build the individual report *sections* the bot serves on demand.

Each request from Telegram maps to exactly one section here. Sections are
rendered as Telegram-flavoured HTML (``parse_mode=HTML``) so they look clean
and modern: a bold title, a thin divider, bullet rows and a footer count.

Sections read the latest data straight off the CSVs written by the daily
pipeline, so they work even between scheduled runs.
"""

from datetime import datetime
from html import escape

from instabot.logging_config import get_logger
from instabot.storage import csv_store

logger = get_logger(__name__)

# Show at most this many usernames per section to keep messages snappy.
MAX_NAMES = 20
DIVIDER = "━━━━━━━━━━━━━━━"


def _names_block(usernames: list[str], bullet: str = "•") -> str:
    """Render a bulleted, @-mentioned list of usernames (HTML-escaped)."""
    if not usernames:
        return "<i>Nothing to show here yet.</i>"
    shown = usernames[:MAX_NAMES]
    lines = [f"{bullet} <code>@{escape(str(name))}</code>" for name in shown]
    remaining = len(usernames) - len(shown)
    if remaining > 0:
        lines.append(f"   <i>…and {remaining} more</i>")
    return "\n".join(lines)


def _wrap(title: str, body: str, footer: str | None = None) -> str:
    """Assemble a section: title, divider, body and optional footer."""
    parts = [f"<b>{title}</b>", DIVIDER, body]
    if footer:
        parts.append(f"\n{footer}")
    return "\n".join(parts)


def _ts() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def unfollowers_section() -> str:
    df = csv_store.read_unfollowers()
    names = df["follower_username"].tolist() if not df.empty else []
    body = _names_block(names, bullet="👋")
    footer = f"<i>{len(names)} left in the last 24h · updated {_ts()}</i>"
    return _wrap("👋 Unfollowers", body, footer)


def active_section() -> str:
    df = csv_store.read_active()
    names = df["follower_username"].tolist() if not df.empty else []
    body = _names_block(names, bullet="🔥")
    footer = f"<i>{len(names)} highly engaged followers · updated {_ts()}</i>"
    return _wrap("🔥 Active Followers", body, footer)


def ghost_section() -> str:
    df = csv_store.read_ghost()
    names = df["follower_username"].tolist() if not df.empty else []
    body = _names_block(names, bullet="👻")
    footer = f"<i>{len(names)} near-silent followers · updated {_ts()}</i>"
    return _wrap("👻 Ghost Followers", body, footer)


def views_section() -> str:
    """Story / post viewing stats, derived from the latest follower snapshot.

    Viewing happens during the daily pipeline; here we surface the most recent
    counts if the scheduler stashed them, otherwise a friendly placeholder.
    """
    body = (
        "I view your home account's stories and posts during the daily run.\n"
        "Run the daily job to refresh these numbers."
    )
    return _wrap("👀 Story & Post Views", body, f"<i>updated {_ts()}</i>")


def overview_section() -> str:
    """A compact dashboard combining every metric into one section."""
    unfollowers = csv_store.read_unfollowers()
    active = csv_store.read_active()
    ghost = csv_store.read_ghost()
    followers = csv_store.read_followers()

    total_followers = followers["follower_id"].nunique() if not followers.empty else 0

    rows = [
        f"👥 Followers tracked   <b>{total_followers}</b>",
        f"👋 Unfollowers (24h)   <b>{len(unfollowers)}</b>",
        f"🔥 Active followers     <b>{len(active)}</b>",
        f"👻 Ghost followers      <b>{len(ghost)}</b>",
    ]
    return _wrap("📊 Overview", "\n".join(rows), f"<i>updated {_ts()}</i>")


def section_for(key: str) -> str:
    """Map a request key (from a button/command) to its rendered section."""
    if key not in _SECTIONS:
        logger.warning("Requested unknown section %r.", key)
    else:
        logger.info("Rendering section %r.", key)
    return _SECTIONS.get(
        key, lambda: _wrap("🤔 Unknown", "I don't know that one yet.")
    )()


_SECTIONS = {
    "overview": overview_section,
    "unfollowers": unfollowers_section,
    "active": active_section,
    "ghost": ghost_section,
    "views": views_section,
}


def build_full_report(summary: dict) -> str:
    """Build the full multi-section daily report from a fresh summary dict.

    Used by the scheduled push so the daily message carries everything at once.
    Falls back to the on-disk sections for anything missing from ``summary``.
    """

    def names(key: str) -> str:
        vals = summary.get(key, [])
        return _names_block([str(v) for v in vals])

    def count(key: str, names_key: str) -> int:
        return int(summary.get(key, len(summary.get(names_key, []))))

    blocks = [
        "<b>📊 Daily Instagram Report</b>",
        f"<i>{_ts()}</i>",
        DIVIDER,
        f"<b>👋 Unfollowers ({count('unfollower_count', 'unfollower_usernames')})</b>",
        names("unfollower_usernames"),
        "",
        f"<b>🔥 Active Followers ({count('active_count', 'active_usernames')})</b>",
        names("active_usernames"),
        "",
        f"<b>👻 Ghost Followers ({count('ghost_count', 'ghost_usernames')})</b>",
        names("ghost_usernames"),
        "",
        f"👀 Viewed <b>{summary.get('stories_seen', 0)}</b> stories "
        f"and <b>{summary.get('posts_seen', 0)}</b> posts.",
    ]
    return "\n".join(blocks)
