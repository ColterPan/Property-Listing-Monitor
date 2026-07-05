from datetime import UTC, datetime

from property_monitor.models import Listing, ListingIntent, PropertyType, SavedSearch


def test_listing_construction_with_optional_fields_defaulted() -> None:
    listing = Listing(
        listing_id="123",
        url="https://example.com/123",
        title="Nice place",
        portal="propertyguru",
        intent=ListingIntent.RENT,
        scraped_at=datetime.now(UTC),
    )
    assert listing.price is None
    assert listing.bedrooms is None
    assert listing.property_type is None


def test_saved_search_enum_coercion_from_strings() -> None:
    search = SavedSearch(
        name="Test",
        portal="propertyguru",
        location="Tampines",
        property_type=PropertyType("hdb"),
        intent=ListingIntent("sale"),
    )
    assert search.property_type is PropertyType.HDB
    assert search.intent is ListingIntent.SALE
