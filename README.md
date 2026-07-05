# Property Listing Monitor

Monitors PropertyGuru (99.co planned as a second portal) for new listings
matching your saved search criteria -- location, budget, property type -- and
sends an instant Telegram alert when a new one appears, instead of you
manually refreshing search pages.

Runs as a **scheduled task**, not a background daemon: each invocation loads
your config, scrapes current results, diffs against what it's already seen
(SQLite), sends Telegram alerts for anything new, and exits.

> **Note on portal Terms of Service:** PropertyGuru and 99.co prohibit
> automated scraping in their ToS. This tool is intended for personal,
> low-frequency, non-redistributed use (checking your own saved searches
> every 15-30 minutes) -- not for commercial or high-volume use. Use at your
> own discretion and risk.

## Status

The PropertyGuru scraper's search-URL parameters and CSS selectors are
**best-effort placeholders that have not yet been verified against the live
site** -- see [`docs/propertyguru_notes.md`](docs/propertyguru_notes.md) for
exactly what needs confirming before this reliably finds real listings.

## Install

Requires Python 3.11+.

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -e ".[dev]"
playwright install chromium     # one-time browser binary download
```

## Configure

1. Copy the example config and edit your saved searches:
   ```bash
   copy config.example.yaml config.yaml
   ```
2. Copy the example env file and add your Telegram credentials:
   ```bash
   copy .env.example .env
   ```

### Setting up your Telegram bot

1. Open a chat with [`@BotFather`](https://t.me/BotFather) on Telegram, send
   `/newbot`, and follow the prompts. Copy the token it gives you.
2. Send any message to your new bot (it can't message you until you've
   messaged it first).
3. Find your chat ID: message [`@userinfobot`](https://t.me/userinfobot), or
   call `https://api.telegram.org/bot<your-token>/getUpdates` after step 2
   and read `message.chat.id` from the JSON response.
4. Put both values into `.env` as `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID`.

## Usage

Dry run (scrapes and diffs, but sends no Telegram messages and writes no
state -- safe to run repeatedly while testing):

```bash
property-monitor --config config.yaml --dry-run
```

Real run:

```bash
property-monitor --config config.yaml
```

On first run for a new saved search, listings found are recorded as a
baseline **without** sending alerts (so you don't get flooded with alerts for
listings that already existed) -- set `notify_on_first_run: true` in config
to change that, globally or per-search.

## Scheduling (Windows Task Scheduler)

1. Create the venv and install dependencies as above (in this project
   folder).
2. Open Task Scheduler -> Create Task:
   - **Action**: Start a program -> `run_monitor.bat` (in this repo root).
   - **Start in**: this repo's folder (the `.bat` also anchors its own
     working directory via `%~dp0`, so this is a safety net).
   - **Trigger**: repeat every 15-30 minutes, indefinitely.
   - Under Settings, enable "Stop the task if it runs longer than" as a
     safety net against a hung browser process.
3. Logs land in `logs/property_monitor.log` (rotated automatically).

## Architecture

See [`docs/architecture.md`](docs/architecture.md) for the full data flow,
the scraper interface that lets a second portal be added later, and the
dedup/error-handling semantics.

## Testing

```bash
pytest                       # unit tests only (default; fast, no network)
pytest -m integration        # live-site checks (manual, hits PropertyGuru)
```

## License

MIT -- see [LICENSE](LICENSE).
