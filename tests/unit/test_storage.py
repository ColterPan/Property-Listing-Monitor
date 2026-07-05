from datetime import UTC, datetime
from pathlib import Path

from property_monitor.models import Listing, ListingIntent, PropertyType
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
        bedrooms=3,
        property_type=PropertyType.HDB,
    )


def test_first_run_has_no_seen_listings(tmp_path: Path) -> None:
    with SeenListingStore(tmp_path / "listings.db") as store:
        assert store.get_seen_ids("Search A") == set()
        assert store.has_prior_successful_run("Search A") is False


def test_record_and_retrieve_new_listings(tmp_path: Path) -> None:
    with SeenListingStore(tmp_path / "listings.db") as store:
        store.record_new_listings("Search A", [_listing("1"), _listing("2")])
        assert store.get_seen_ids("Search A") == {"1", "2"}


def test_same_listing_id_isolated_per_search(tmp_path: Path) -> None:
    with SeenListingStore(tmp_path / "listings.db") as store:
        store.record_new_listings("Search A", [_listing("shared")])
        assert store.get_seen_ids("Search A") == {"shared"}
        assert store.get_seen_ids("Search B") == set()


def test_record_run_and_has_prior_successful_run(tmp_path: Path) -> None:
    with SeenListingStore(tmp_path / "listings.db") as store:
        assert store.has_prior_successful_run("Search A") is False
        store.record_run("Search A", datetime.now(UTC), status="ok", new_count=2)
        assert store.has_prior_successful_run("Search A") is True


def test_last_error_alert_at_tracks_only_error_runs(tmp_path: Path) -> None:
    with SeenListingStore(tmp_path / "listings.db") as store:
        assert store.last_error_alert_at("Search A") is None
        store.record_run("Search A", datetime.now(UTC), status="ok", new_count=1)
        assert store.last_error_alert_at("Search A") is None
        store.record_run("Search A", datetime.now(UTC), status="error", error_message="boom")
        assert store.last_error_alert_at("Search A") is not None


def test_record_new_listings_is_atomic_on_failure(tmp_path: Path) -> None:
    with SeenListingStore(tmp_path / "listings.db") as store:
        bad_listing = _listing("1")
        object.__setattr__(bad_listing, "listing_id", None)  # forces an INSERT failure (NOT NULL)

        try:
            store.record_new_listings("Search A", [_listing("ok"), bad_listing])
        except Exception:
            pass

        assert store.get_seen_ids("Search A") == set()
