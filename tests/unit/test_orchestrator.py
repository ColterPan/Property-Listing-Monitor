from datetime import UTC, datetime
from pathlib import Path

import pytest

from property_monitor.config import AppConfig
from property_monitor.models import Listing, ListingIntent, PropertyType, SavedSearch
from property_monitor.notifier import NotifierBase
from property_monitor.orchestrator import MonitorRun
from property_monitor.scrapers.base import ScraperBase
from property_monitor.scrapers.exceptions import ScrapeError
from property_monitor.storage import SeenListingStore


def _listing(listing_id: str) -> Listing:
    return Listing(
        listing_id=listing_id,
        url=f"https://example.com/{listing_id}",
        title="Test listing",
        portal="propertyguru",
        intent=ListingIntent.SALE,
        scraped_at=datetime.now(UTC),
        price=500_000,
        property_type=PropertyType.HDB,
    )


def _search(name: str = "Search A", notify_on_first_run: bool | None = None) -> SavedSearch:
    return SavedSearch(
        name=name,
        portal="fake",
        location="Tampines",
        property_type=PropertyType.HDB,
        intent=ListingIntent.SALE,
        notify_on_first_run=notify_on_first_run,
    )


def _config(searches: list[SavedSearch], notify_on_first_run: bool = False) -> AppConfig:
    return AppConfig(
        telegram_bot_token="token",
        telegram_chat_id="chat",
        searches=searches,
        notify_on_first_run=notify_on_first_run,
    )


class FakeNotifier(NotifierBase):
    def __init__(self, fail: bool = False) -> None:
        self.sent: list[str] = []
        self._fail = fail

    def send(self, message: str) -> None:
        if self._fail:
            raise RuntimeError("simulated send failure")
        self.sent.append(message)


class FakeScraper(ScraperBase):
    portal_name = "fake"
    queued_listings: list[Listing] = []
    raise_error: bool = False

    def __init__(self, headless: bool = True) -> None:
        self.headless = headless

    def fetch_listings(self, search: SavedSearch) -> list[Listing]:
        if FakeScraper.raise_error:
            raise ScrapeError("simulated scrape failure")
        return FakeScraper.queued_listings


@pytest.fixture(autouse=True)
def _reset_fake_scraper():
    FakeScraper.queued_listings = []
    FakeScraper.raise_error = False
    yield
    FakeScraper.queued_listings = []
    FakeScraper.raise_error = False


def _registry() -> dict[str, type[ScraperBase]]:
    return {"fake": FakeScraper}


def test_first_run_establishes_baseline_without_alerts(tmp_path: Path) -> None:
    FakeScraper.queued_listings = [_listing("1"), _listing("2")]
    search = _search()
    notifier = FakeNotifier()

    with SeenListingStore(tmp_path / "listings.db") as store:
        run = MonitorRun(_config([search]), store, notifier, _registry())
        summary = run.run()

        assert notifier.sent == []
        assert summary.results[0].new_count == 0
        assert store.get_seen_ids(search.name) == {"1", "2"}


def test_second_run_alerts_only_on_new_listings(tmp_path: Path) -> None:
    search = _search()
    notifier = FakeNotifier()

    with SeenListingStore(tmp_path / "listings.db") as store:
        FakeScraper.queued_listings = [_listing("1")]
        MonitorRun(_config([search]), store, notifier, _registry()).run()

        FakeScraper.queued_listings = [_listing("1"), _listing("2")]
        summary = MonitorRun(_config([search]), store, notifier, _registry()).run()

        assert len(notifier.sent) == 1
        assert "2" in "".join(notifier.sent)
        assert summary.results[0].new_count == 1
        assert store.get_seen_ids(search.name) == {"1", "2"}


def test_notify_on_first_run_override_sends_alerts_immediately(tmp_path: Path) -> None:
    FakeScraper.queued_listings = [_listing("1")]
    search = _search(notify_on_first_run=True)
    notifier = FakeNotifier()

    with SeenListingStore(tmp_path / "listings.db") as store:
        summary = MonitorRun(_config([search]), store, notifier, _registry()).run()

        assert len(notifier.sent) == 1
        assert summary.results[0].new_count == 1


def test_scraper_failure_is_isolated_to_one_search(tmp_path: Path) -> None:
    good_search = _search(name="Good")
    bad_search = _search(name="Bad")
    notifier = FakeNotifier()

    with SeenListingStore(tmp_path / "listings.db") as store:
        # First establish a baseline for both so "Good" is past its first run.
        FakeScraper.queued_listings = [_listing("1")]
        MonitorRun(_config([good_search, bad_search]), store, notifier, _registry()).run()

        FakeScraper.queued_listings = [_listing("1"), _listing("2")]
        FakeScraper.raise_error = False

        class SometimesFailingScraper(FakeScraper):
            def fetch_listings(self, search: SavedSearch) -> list[Listing]:
                if search.name == "Bad":
                    raise ScrapeError("boom")
                return FakeScraper.queued_listings

        registry = {"fake": SometimesFailingScraper}
        summary = MonitorRun(_config([good_search, bad_search]), store, notifier, registry).run()

        good_result = next(r for r in summary.results if r.search_name == "Good")
        bad_result = next(r for r in summary.results if r.search_name == "Bad")

        assert good_result.failed is False
        assert good_result.new_count == 1
        assert bad_result.failed is True


def test_failed_notifier_send_prevents_listing_from_being_persisted(tmp_path: Path) -> None:
    search = _search()
    notifier = FakeNotifier()

    with SeenListingStore(tmp_path / "listings.db") as store:
        FakeScraper.queued_listings = [_listing("1")]
        MonitorRun(_config([search]), store, notifier, _registry()).run()

        failing_notifier = FakeNotifier(fail=True)
        FakeScraper.queued_listings = [_listing("1"), _listing("2")]
        summary = MonitorRun(_config([search]), store, failing_notifier, _registry()).run()

        assert summary.results[0].new_count == 0
        # "2" was never successfully alerted, so it must not be marked as seen --
        # otherwise it would silently disappear on the next run.
        assert "2" not in store.get_seen_ids(search.name)


def test_dry_run_does_not_persist_or_send(tmp_path: Path) -> None:
    FakeScraper.queued_listings = [_listing("1")]
    search = _search()
    notifier = FakeNotifier()

    with SeenListingStore(tmp_path / "listings.db") as store:
        MonitorRun(_config([search]), store, notifier, _registry(), dry_run=True).run()

        assert notifier.sent == []
        assert store.get_seen_ids(search.name) == set()
        assert store.has_prior_successful_run(search.name) is False
