"""Command-line entrypoint: one invocation = one scrape-diff-alert cycle."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from property_monitor.config import ConfigError, load_config
from property_monitor.logging_setup import configure_logging
from property_monitor.notifier import TelegramNotifier
from property_monitor.orchestrator import MonitorRun
from property_monitor.scrapers import SCRAPER_REGISTRY
from property_monitor.storage import SeenListingStore

logger = logging.getLogger(__name__)


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Property Listing Monitor")
    parser.add_argument("--config", type=Path, default=Path("config.yaml"), help="Path to config.yaml")
    parser.add_argument("--env-file", type=Path, default=None, help="Path to .env (defaults to .env in cwd)")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Scrape and diff but do not send Telegram alerts or persist state",
    )
    parser.add_argument("--log-level", default=None, help="Override the configured log level")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)

    try:
        config = load_config(args.config, env_path=args.env_file)
    except ConfigError as exc:
        # Logging isn't configured yet at this point, so surface config errors directly.
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 1

    log_level = args.log_level or config.log_level
    configure_logging(config.log_dir, level=log_level)

    logger.info(
        "Starting run (dry_run=%s) with %d saved search(es)", args.dry_run, len(config.searches)
    )

    try:
        with SeenListingStore(config.db_path) as store:
            notifier = TelegramNotifier(config.telegram_bot_token, config.telegram_chat_id)
            run = MonitorRun(
                config=config,
                store=store,
                notifier=notifier,
                scraper_registry=SCRAPER_REGISTRY,
                dry_run=args.dry_run,
            )
            run.run()
    except Exception:  # noqa: BLE001 - top-level boundary: log fully, exit non-zero
        logger.error("Unhandled error during run", exc_info=True)
        return 2

    return 0


if __name__ == "__main__":
    sys.exit(main())
