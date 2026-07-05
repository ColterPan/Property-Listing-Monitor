from property_monitor.models import ListingIntent, PropertyType, SavedSearch
from property_monitor.scrapers.ninetynine import NinetyNineScraper


def _search(**overrides) -> SavedSearch:
    defaults = dict(
        name="Test search",
        portal="99co",
        location="Tampines",
        property_type=PropertyType.HDB,
        intent=ListingIntent.SALE,
        min_price=400_000,
        max_price=550_000,
    )
    defaults.update(overrides)
    return SavedSearch(**defaults)


def test_build_search_url_uses_sale_path_and_confirmed_params() -> None:
    scraper = NinetyNineScraper()
    url = scraper._build_search_url(_search())

    assert url.startswith("https://www.99.co/singapore/sale?")
    assert "keywords=Tampines" in url
    assert "price_min=400000" in url
    assert "price_max=550000" in url
    assert "property_segments=residential" in url


def test_build_search_url_uses_rent_path_for_rent_intent() -> None:
    scraper = NinetyNineScraper()
    url = scraper._build_search_url(_search(intent=ListingIntent.RENT, min_price=None, max_price=None))

    assert url.startswith("https://www.99.co/singapore/rent?")
    assert "price_min" not in url
    assert "price_max" not in url


def test_extract_listing_id_from_real_url_shape() -> None:
    url = "https://www.99.co/singapore/sale/property/165-bukit-batok-west-avenue-8-hdb-bKkQB8cCtKqkJuHAFNUFN2"
    assert NinetyNineScraper._extract_listing_id(url) == "bKkQB8cCtKqkJuHAFNUFN2"


def test_extract_listing_id_falls_back_to_url_when_pattern_unrecognized() -> None:
    url = "https://www.99.co/singapore/sale/property/no-id-here"
    # "here" is only 4 chars, below the 10-char minimum -- falls back to the full URL
    assert NinetyNineScraper._extract_listing_id(url) == url


def test_parse_price_extracts_price_and_ignores_psf_suffix() -> None:
    assert NinetyNineScraper._parse_price("S$ 520,000S$ 465 psf") == 520_000


def test_parse_price_returns_none_when_no_match() -> None:
    assert NinetyNineScraper._parse_price("Contact agent") is None
