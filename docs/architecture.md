# Architecture

## Data flow (one invocation = one full cycle)

```
cli.main
  -> config.load_config          (YAML + .env -> AppConfig, fails fast on bad config)
  -> logging_setup.configure_logging
  -> storage.SeenListingStore     (opens/creates SQLite db)
  -> notifier.TelegramNotifier
  -> orchestrator.MonitorRun.run()
       for each SavedSearch:
         -> scrapers.SCRAPER_REGISTRY[search.portal] -> ScraperBase.fetch_listings(search)
         -> diff against store.get_seen_ids(search.name)
         -> send Telegram alert per new listing (skip on first run, unless configured otherwise)
         -> persist newly-seen listings in one transaction
         -> record_run() in SQLite for troubleshooting + self-alert cooldown tracking
  -> process exits (0 = ok, 1 = config error, 2 = unhandled error)
```

There is no long-running process; the script is invoked repeatedly by Windows
Task Scheduler (or cron), each run being fully self-contained.

## Why a scraper interface

`scrapers/base.py` defines `ScraperBase.fetch_listings(search) -> list[Listing]`
and a `SCRAPER_REGISTRY` mapping portal name -> scraper class. The
orchestrator only ever talks to this interface, keyed by `SavedSearch.portal`.
Adding 99.co later means writing `scrapers/ninetynine.py` and registering it
in `scrapers/__init__.py` -- no changes to `orchestrator.py`, `storage.py`,
or `notifier.py`.

## Dedup semantics

See the "Dedup / diff algorithm" section of the plan and the docstrings in
`storage.py` / `orchestrator.py`. Key points:

- Dedup key is `(search_name, listing_id)` -- the same physical listing
  matching two different saved searches is tracked independently per search.
- A search's first-ever run establishes a silent baseline (no alerts) unless
  `notify_on_first_run` is set, to avoid flooding you with alerts for
  pre-existing listings the first time a search runs.
- Alerts are sent *before* the corresponding listings are persisted as seen,
  so a crash or Telegram outage mid-run can produce a duplicate alert on the
  next run, but never a silently dropped one.

## Error handling

A `ScrapeError` (selector broken / site layout changed) or unexpected scraper
exception is isolated to that one search -- other searches in the same run
still proceed. A Telegram "monitor is broken" self-alert is sent for such
failures, rate-limited via `run_log` (`self_alert_cooldown_hours` in config)
so a persistently broken scraper doesn't spam identical alerts every run.
