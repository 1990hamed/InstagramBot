8# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project status

This is a **fresh `uv` scaffold** for an Instagram analytics + Telegram reporting bot. `main.py` and `README.md` are currently empty — the real implementation is being migrated/refactored here.

The prior, working implementation lives in a **separate legacy folder**: `e:\My Workspace\Projects\InstagramBot---\` (a Poetry project). It is the source of truth for existing behavior and must be read before rewriting anything. Treat this `InstagramBot` directory as the destination for refactored code.

## Goal

Build a bot that runs daily and reports to a Telegram account:
1. Detect **unfollowers** (who left since the last scan).
2. Detect **active followers** (those who like/comment a lot).
3. Detect **ghost followers** (followers with near-zero interaction).
4. **View** the home account's stories and posts daily.
5. **Report** all of the above to Telegram.

Sections 1–4 (Instagram side) exist in the legacy folder. The **Telegram reporting side is unbuilt** — `telegramBot.py` there is only a generic echo/keyboard demo, not wired to any Instagram data.

## Tooling & commands

This project uses **`uv`** (not Poetry — the legacy folder uses Poetry). Python **3.13** is pinned in `.python-version`.

```bash
uv sync                      # install deps + dev group into .venv
uv run python main.py        # run the app
uv run pytest                # run tests (testpaths = ["tests"], dir not yet created)
uv run pytest tests/test_x.py::test_name   # run a single test
uv run ruff check .          # lint
uv run ruff check . --fix    # lint + autofix
uv run ruff format .         # format (double quotes, spaces)
```

Ruff config (in `pyproject.toml`): line-length 88, target py313, rules `E,W,F,I,UP,B,C4,N,PTH` with `E501` ignored. Note `PTH` is enabled — prefer `pathlib.Path` over `os.path`/`os` filesystem calls (the legacy code uses `os.path`/`os.makedirs`/`os.remove`; these should become `Path` when refactored).

Build backend is `uv_build` with `module-name = "src"`, `module-root = ""` — i.e. package code is expected under a `src/` module.

## Legacy code architecture (to refactor)

All paths below are under `e:\My Workspace\Projects\InstagramBot---\`.

- **`InstagramBot/Bot.py`** — the core. A single `InstagramBot` class built on `instagrapi.Client`:
  - **Auth/session**: `sign_in` → `login_with_session` (reuses `session.json`) or `first_time_login`. Robust exception handling in `handle_exception` for the full range of `instagrapi` login challenges (`ChallengeRequired`, `FeedbackRequired`, `PleaseWaitFewMinutes`, `BadPassword`, etc.), with a `freeze(reason, hours, days)` that `time.sleep`s the account through cooldowns. Credentials come from `.env` (`INSTAGRAM_USERNAME`, `INSTAGRAM_PASSWORD`).
  - **Data collection → CSV** (under `Data/`): `fetch_followers` (followers + timestamp → `followers_data.csv`), `fetch_media_interactions` (paginates own media, tallies per-user like/comment counts → `interactions_data.csv`).
  - **Analysis**: `classify_users` derives active/ghost users from interaction counts vs. thresholds (active = ≥50% of media count, ghost = ≤1%) → `active_users.csv` / `ghost_users.csv`. `get_leavers` diffs old vs. recent follower snapshots (24h window) → `unfollower_data.csv`.
  - **`view`** is an empty stub (story/post viewing not implemented in this class).
  - **`main`** wires `schedule.every(...).hours.do(...)` jobs (currently commented out) into a polling loop. Scheduling via the `schedule` library is the intended runtime model.
- **`InstagramBot/story_viewer.py`** — a standalone script (not a method) experimenting with `cl.user_stories` / `cl.story_viewers`. Imports a `config` module (not present) rather than `.env`. The "view stories/posts daily" feature should be folded into the bot proper.
- **`TelegramBot/telegramBot.py`** — a `pyTelegramBotAPI` (`telebot`) echo/keyboard demo. Token from `.env` (`API_TOKEN`). Not connected to Instagram data — needs to be replaced with real reporting (read the analysis CSVs and push summaries to Telegram).
- Legacy `pyproject.toml` lists **both** `python-telegram-bot` and `pytelegrambotapi`; only `telebot` (pytelegrambotapi) is actually used. The current `uv` project has **no Telegram dependency yet** — one must be added when building the Telegram side.

## Key gotchas

- The data pipeline is **CSV-file based**, passed between collection and analysis steps via the `Data/` directory. Snapshot-diffing for unfollowers depends on `followers_data.csv` accumulating timestamped rows across runs — don't overwrite history.
- `instagrapi` actions trigger rate-limits/challenges aggressively; the `freeze`/`handle_exception` machinery exists for that reason and should be preserved through any refactor.
- Two dependency managers exist across the two folders (uv here, Poetry in legacy) — when porting deps, translate them into the `uv` `pyproject.toml`, don't copy the Poetry block.
