# InstagramBot

> **Disclaimer:** This tool is for educational purposes. Automating Instagram
> may violate [Instagram's Terms of Service](https://help.instagram.com/581066165581870)
> and can result in rate-limiting or account suspension. Use at your own risk.

A bot that runs daily, analyzes a home Instagram account, and reports the
results to Telegram:

1. **Unfollowers** — who left since the last scan.
2. **Active followers** — those who like/comment a lot.
3. **Ghost followers** — followers with near-zero interaction.
4. **Story/post viewing** — marks the home account's own stories and recent
   posts as seen daily.
5. **Telegram report** — pushes a daily summary of the above to a chat, and
   serves the same sections on demand through an interactive bot menu.

## Setup

This project uses [`uv`](https://docs.astral.sh/uv/) and Python 3.13.

```bash
uv sync                      # install dependencies into .venv
```

Create a `.env` file in the project root with:

```dotenv
INSTAGRAM_USERNAME=your_login_username
INSTAGRAM_PASSWORD=your_login_password
# Optional: account to analyze if different from the login (defaults to INSTAGRAM_USERNAME)
INSTAGRAM_HOME_USERNAME=home_account_username
# Optional: daily run time, 24h HH:MM local (defaults to 09:00)
DAILY_RUN_AT=09:00
# Optional: console log level (defaults to INFO; the file log is always DEBUG)
LOG_LEVEL=INFO

TELEGRAM_BOT_TOKEN=your_bot_token
```

The destination chat is **not** configured in `.env`. The bot captures it
automatically the first time you message it: run the interactive bot
(`uv run python main.py --bot`) and send `/start` once. The chat id is saved to
`Data/telegram_chat.json`, and the scheduled report reads it back from there.

## Running

```bash
uv run python main.py              # one-off pass: collect → analyze → report
uv run python main.py --schedule   # run once, then repeat daily at DAILY_RUN_AT
uv run python main.py --bot        # interactive Telegram bot (serves sections on demand)
```

## Layout

- `instabot/instagram/` — `client.py` (auth/session + rate-limit/challenge
  handling), `collectors.py` (followers, interactions, story/post viewing),
  `analysis.py` (active/ghost classification, unfollower diff).
- `instabot/storage/csv_store.py` — CSV persistence under `Data/`.
- `instabot/telegram_report/` — `reporter.py` (formats and pushes the daily
  report), `bot.py` (interactive inline-keyboard bot), `sections.py` (renders
  each report section as HTML), `chat_store.py` (remembers the chat id).
- `instabot/scheduler.py` — daily orchestration tying both sides together.
- `instabot/logging_config.py` — console + rotating-file logging (`Logs/`).
- `main.py` — entry point dispatching the run modes above.

Collected data is written to `Data/*.csv`. The unfollower diff relies on
`Data/followers_data.csv` accumulating timestamped snapshots across runs.

## Development

```bash
uv run ruff check .          # lint
uv run ruff format .         # format
uv run pytest                # tests
```

## License

Released under the [MIT License](LICENSE).
