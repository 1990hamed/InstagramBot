# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A bot that runs daily, analyzes a home Instagram account, and reports the results to Telegram. It is a working implementation organized as the `instabot` package. The five capabilities are all wired up:

1. **Unfollowers** — who left since the last scan (24h diff over follower snapshots).
2. **Active followers** — heavy likers/commenters.
3. **Ghost followers** — followers with near-zero interaction.
4. **Story/post viewing** — marks the home account's own stories and recent posts as seen daily.
5. **Telegram reporting** — pushes a daily report and serves sections on demand via an inline-keyboard bot.

> Historical origin: an earlier Poetry-based prototype lives at `e:\My Workspace\Projects\InstagramBot---\`. It is no longer the source of truth — the current `instabot` package is. Only consult it for archaeology, not for behavior.

## Tooling & commands

Uses **`uv`**. Python **3.13** is pinned in `.python-version`.

```bash
uv sync                      # install deps + dev group into .venv
uv run python main.py        # one-off pipeline run (collect → analyze → report)
uv run python main.py --schedule   # run once, then daily at DAILY_RUN_AT
uv run python main.py --bot        # interactive Telegram bot (long-polling)
uv run python -m instabot.telegram_report.bot   # same interactive bot, directly
uv run pytest                # run tests
uv run pytest tests/test_chat_store.py::test_save_then_load_round_trips   # single test
uv run ruff check .          # lint
uv run ruff check . --fix    # lint + autofix
uv run ruff format .         # format (double quotes, spaces)
```

Ruff config (in `pyproject.toml`): line-length 88, target py313, rules `E,W,F,I,UP,B,C4,N,PTH` with `E501` ignored. `PTH` is enabled — use `pathlib.Path`, not `os.path`. The codebase already follows this.

Build backend is `uv_build` with `module-name = "instabot"`, `module-root = ""` — package code lives under `instabot/`.




## Configuration (`.env`)

Loaded via `python-dotenv` (each module calls `load_dotenv()`).

- `INSTAGRAM_USERNAME` / `INSTAGRAM_PASSWORD` — login credentials.
- `INSTAGRAM_HOME_USERNAME` — account to analyze; falls back to `INSTAGRAM_USERNAME`.
- `DAILY_RUN_AT` — daily run time, `HH:MM` 24h local (default `09:00`).
- `TELEGRAM_BOT_TOKEN` — Telegram bot token (required for any Telegram action).
- `LOG_LEVEL` — console log level (default `INFO`).

There is **no** `TELEGRAM_CHAT_ID`: the bot captures the chat id automatically the first time you message it (`/start`) and saves it to `Data/telegram_chat.json`. The scheduled report reads it back from there.

## Architecture

Entry point is [main.py](main.py): one-off run by default, `--schedule` for daily, `--bot` for the interactive bot.

- [instabot/scheduler.py](instabot/scheduler.py) — orchestration. `run_daily_job()` ties the pipeline together: sign in → collect followers → collect interactions → view stories/posts → classify → diff unfollowers → push Telegram report. `main()` runs it once then loops with the `schedule` library at `DAILY_RUN_AT`.
- [instabot/instagram/client.py](instabot/instagram/client.py) — `InstagramClient`, an `instagrapi.Client` wrapper. Session reuse via `session.json` at project root; `sign_in` → `login_with_session` / `first_time_login`. `handle_exception` covers the full range of login challenges (`ChallengeRequired`, `FeedbackRequired`, `PleaseWaitFewMinutes`, `BadPassword`, etc.) and `freeze(reason, hours, days)` `time.sleep`s the account through cooldowns. **Preserve this machinery through any refactor** — Instagram rate-limits/challenges aggressively.
- [instabot/instagram/collectors.py](instabot/instagram/collectors.py) — `Collector`: `fetch_followers` (appends timestamped follower rows to history), `fetch_media_interactions` (paginates own media, tallies per-user like/comment counts), `view_stories_and_posts` (marks stories + recent posts seen, returns counts).
- [instabot/instagram/analysis.py](instabot/instagram/analysis.py) — `classify_users` (classifies on combined likes + comments: active = ≥ `ACTIVE_RATIO`×media count; ghost = ≤ `GHOST_RATIO`×media count) and `get_leavers` (24h diff of old vs. recent follower snapshots). Both persist CSVs and return summary dicts.
- [instabot/storage/csv_store.py](instabot/storage/csv_store.py) — all CSV persistence under project-root `Data/`. Read/write helpers per file; empty frames with fixed column schemas when a file is missing.
- [instabot/telegram_report/](instabot/telegram_report/) — built on **`python-telegram-bot`** (async):
  - `reporter.py` — `send_report(summary)` (sync wrapper around async send) pushes the daily HTML report to the saved chat.
  - `bot.py` — interactive inline-keyboard menu; each button serves one section; auto-saves the chat id on any message.
  - `sections.py` — renders each section as Telegram HTML, reading the latest CSVs (so sections work between scheduled runs). `build_full_report(summary)` builds the all-in-one daily message.
  - `chat_store.py` — persists/loads the chat id in `Data/telegram_chat.json`.
- [instabot/logging_config.py](instabot/logging_config.py) — `get_logger(__name__)` everywhere; `setup_logging()` is idempotent. Console at `LOG_LEVEL`, rotating file at DEBUG under `Logs/instabot.log`. Noisy libs (`instagrapi`, `httpx`, …) pinned to WARNING.

## Data files (`Data/`)

The pipeline is CSV-file based; analysis steps read what collection wrote.

- `followers_data.csv` — `follower_id, follower_username, timestamp`. **History-accumulating**: new snapshots are appended, old rows preserved. The unfollower diff depends on this — don't overwrite history.
- `interactions_data.csv` — `follower_id, follower_username, like, comment`.
- `active_users.csv` / `ghost_users.csv` — classification outputs (interaction schema).
- `unfollower_data.csv` — latest detected unfollowers (follower schema).
- `telegram_chat.json` — `{"chat_id": "..."}`.

## Gotchas

- Preserve the `freeze` / `handle_exception` cooldown logic — it exists because `instagrapi` triggers challenges/rate-limits aggressively.
- The follower history file must accumulate, not be overwritten — the 24h unfollower diff reads multiple snapshots out of it.
- Telegram sends are async (`python-telegram-bot`); the scheduler uses the sync `send_report` wrapper. Don't call `asyncio.run` inside an already-running loop.

## Branching & Commits

- [Conventional Commits](https://www.conventionalcommits.org/): `type(scope): description`
  - Types: `feat`, `fix`, `refactor`, `chore`, `docs`, `test`
  - Example: `feat(telegram): add ghost-followers section to daily report`
- Before pushing: `uv run ruff check .` and `uv run pytest` must both pass.

## Git Rules

- Always commit using the repo's configured git identity.
- Do not override user.name or user.email when committing.
- Do not add `Co-Authored-By` trailers or any Claude/Anthropic attribution to commit messages or PR bodies.
