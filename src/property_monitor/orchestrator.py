"""Ties config, scraper, storage, and notifier together for a single run."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from property_monitor.config import AppConfig
from property_monitor.models import Listing, SavedSearch
from property_monitor.notifier import NotifierBase, format_listing_message, format_system_alert
from property_monitor.scrapers.base import ScraperBase
from property_monitor.scrapers.exceptions import ScrapeError
from property_monitor.storage import SeenListingStore

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class SearchResult:
    search_name: str
    checked: bool = False
    new_count: int = 0
    failed: bool = False


@dataclass(slots=True)
class RunSummary:
    results: list[SearchResult] = field(default_factory=list)

    @property
    def total_new(self) -> int:
        return sum(r.new_count for r in self.results)

    @property
    def total_failed(self) -> int:
        return sum(1 for r in self.results if r.failed)


class MonitorRun:
    def __init__(
        self,
        config: AppConfig,
        store: SeenListingStore,
        notifier: NotifierBase,
        scraper_registry: dict[str, type[ScraperBase]],
        dry_run: bool = False,
    ) -> None:
        self._config = config
        self._store = store
        self._notifier = notifier
        self._scraper_registry = scraper_registry
        self._dry_run = dry_run

    def run(self) -> RunSummary:
        summary = RunSummary()
        for search in self._config.searches:
            summary.results.append(self._run_one(search))
        logger.info(
            "Run complete: %d search(es) checked, %d new listing(s), %d failed",
            len(summary.results),
            summary.total_new,
            summary.total_failed,
        )
        return summary

    def _run_one(self, search: SavedSearch) -> SearchResult:
        started_at = datetime.now(UTC)
        result = SearchResult(search_name=search.name)

        scraper_cls = self._scraper_registry.get(search.portal)
        if scraper_cls is None:
            logger.error("No scraper registered for portal '%s' (search '%s')", search.portal, search.name)
            result.failed = True
            self._record_failure(search, started_at, f"Unknown portal '{search.portal}'")
            return result

        try:
            scraper = scraper_cls(headless=self._config.headless)
            listings = scraper.fetch_listings(search)
        except ScrapeError as exc:
            logger.error("Scrape failed for search '%s': %s", search.name, exc, exc_info=True)
            result.failed = True
            self._record_failure(search, started_at, str(exc))
            return result
        except Exception as exc:  # noqa: BLE001 - boundary: log fully, keep other searches running
            logger.error("Unexpected error scraping search '%s'", search.name, exc_info=True)
            result.failed = True
            self._record_failure(search, started_at, f"Unexpected error: {exc}")
            return result

        result.checked = True
        self._process_listings(search, listings, started_at, result)
        return result

    def _process_listings(
        self,
        search: SavedSearch,
        listings: list[Listing],
        started_at: datetime,
        result: SearchResult,
    ) -> None:
        seen_ids = self._store.get_seen_ids(search.name)
        is_first_run = not seen_ids and not self._store.has_prior_successful_run(search.name)
        notify_first_run = (
            search.notify_on_first_run
            if search.notify_on_first_run is not None
            else self._config.notify_on_first_run
        )

        new_listings = [listing for listing in listings if listing.listing_id not in seen_ids]

        should_alert = new_listings and not (is_first_run and not notify_first_run)

        sent: list[Listing] = []
        if should_alert and not self._dry_run:
            for listing in new_listings:
                try:
                    self._notifier.send(format_listing_message(listing, search.name))
                    sent.append(listing)
                except Exception:  # noqa: BLE001 - one failed send shouldn't drop the rest
                    logger.error(
                        "Failed to send alert for listing %s in search '%s'",
                        listing.listing_id,
                        search.name,
                        exc_info=True,
                    )
        elif self._dry_run:
            sent = new_listings

        if is_first_run:
            logger.info("Baseline established for search '%s': %d listing(s) recorded", search.name, len(listings))

        if not self._dry_run:
            to_persist = listings if is_first_run else sent
            self._store.record_new_listings(search.name, to_persist)
            self._store.record_run(search.name, started_at, status="ok", new_count=len(sent))

        result.new_count = len(sent)

    def _record_failure(self, search: SavedSearch, started_at: datetime, error_message: str) -> None:
        if self._dry_run:
            return

        last_alert = self._store.last_error_alert_at(search.name)
        self._store.record_run(search.name, started_at, status="error", error_message=error_message)

        cooldown = timedelta(hours=self._config.self_alert_cooldown_hours)
        if last_alert is not None and datetime.now(UTC) - last_alert < cooldown:
            logger.info("Suppressing duplicate self-alert for search '%s' (within cooldown)", search.name)
            return

        try:
            self._notifier.send(format_system_alert(search.name, error_message))
        except Exception:  # noqa: BLE001 - self-alert failure must not crash the run
            logger.error("Failed to send self-alert for search '%s'", search.name, exc_info=True)
