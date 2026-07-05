"""PropertyGuru scraper.

IMPORTANT: The search-URL query parameters and the CSS selectors below are
best-effort placeholders. They MUST be verified against the live site before
relying on this in production -- see docs/propertyguru_notes.md, which should
be updated with the verification date once confirmed. Site DOM/URL formats
change over time; treat this file as needing periodic re-verification.
"""

from __future__ import annotations

import logging
import re
from datetime import UTC, datetime
from urllib.parse import quote_plus

from playwright.sync_api import Locator, Page, TimeoutError as PlaywrightTimeoutError, sync_playwright

from property_monitor.models import Listing, ListingIntent, PropertyType, SavedSearch
from property_monitor.scrapers.base import ScraperBase
from property_monitor.scrapers.exceptions import ScrapeError

logger = logging.getLogger(__name__)

BASE_URL = "https://www.propertyguru.com.sg"

# NEEDS LIVE VERIFICATION: confirm these map to PropertyGuru's actual filter codes.
_PROPERTY_TYPE_CODES: dict[PropertyType, str] = {
    PropertyType.HDB: "H",
    PropertyType.CONDO: "N",
    PropertyType.LANDED: "L",
    PropertyType.OTHER: "",
}

# NEEDS LIVE VERIFICATION: confirm the listing-card container selector.
LISTING_CARD_SELECTOR = "[data-testid='listing-card']"
_LISTING_ID_RE = re.compile(r"-(\d+)(?:\.html)?/?$")

_MIN_PARSE_SUCCESS_RATIO = 0.5


class PropertyGuruScraper(ScraperBase):
    portal_name = "propertyguru"

    def __init__(self, headless: bool = True, timeout_ms: int = 30_000) -> None:
        self._headless = headless
        self._timeout_ms = timeout_ms

    def fetch_listings(self, search: SavedSearch) -> list[Listing]:
        url = self._build_search_url(search)
        logger.debug("Navigating to PropertyGuru search URL: %s", url)

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=self._headless)
            try:
                page = browser.new_page()
                page.goto(url, timeout=self._timeout_ms)
                return self._extract_listings(page, search)
            finally:
                browser.close()

    def _build_search_url(self, search: SavedSearch) -> str:
        segment = "property-for-rent" if search.intent == ListingIntent.RENT else "property-for-sale"
        params = [f"freetext={quote_plus(search.location)}"]

        if search.min_price is not None:
            params.append(f"minprice={search.min_price}")
        if search.max_price is not None:
            params.append(f"maxprice={search.max_price}")

        code = _PROPERTY_TYPE_CODES.get(search.property_type, "")
        if code:
            params.append(f"property_type={code}")

        return f"{BASE_URL}/{segment}?{'&'.join(params)}"

    def _extract_listings(self, page: Page, search: SavedSearch) -> list[Listing]:
        try:
            page.wait_for_selector(LISTING_CARD_SELECTOR, timeout=self._timeout_ms)
        except PlaywrightTimeoutError as exc:
            raise ScrapeError(
                f"No listing cards found for search '{search.name}' "
                f"(selector '{LISTING_CARD_SELECTOR}' may be stale, or the site layout changed)"
            ) from exc

        cards = page.locator(LISTING_CARD_SELECTOR)
        count = cards.count()
        if count == 0:
            raise ScrapeError(f"No listing cards found for search '{search.name}'")

        listings: list[Listing] = []
        failures = 0
        for i in range(count):
            listing = self._parse_card(cards.nth(i), search)
            if listing is None:
                failures += 1
            else:
                listings.append(listing)

        if failures / count > _MIN_PARSE_SUCCESS_RATIO:
            raise ScrapeError(
                f"{failures}/{count} listing cards failed to parse for search "
                f"'{search.name}' -- selectors likely need updating"
            )

        return listings

    def _parse_card(self, card: Locator, search: SavedSearch) -> Listing | None:
        try:
            href = card.locator("a").first.get_attribute("href") or ""
            if not href:
                logger.warning("Listing card had no href; skipping")
                return None
            url = href if href.startswith("http") else f"{BASE_URL}{href}"

            listing_id = self._extract_listing_id(url)
            title = card.locator("h3, h2").first.inner_text().strip()
            raw_price_text = card.locator("[data-testid='listing-price']").first.inner_text().strip()
            location = card.locator("[data-testid='listing-location']").first.inner_text().strip()

            return Listing(
                listing_id=listing_id,
                url=url,
                title=title,
                portal=self.portal_name,
                intent=search.intent,
                scraped_at=datetime.now(UTC),
                price=self._parse_price(raw_price_text),
                raw_price_text=raw_price_text,
                location=location,
                bedrooms=self._parse_bedrooms(card),
                property_type=search.property_type,
            )
        except Exception:
            logger.warning("Failed to parse a listing card for search '%s'", search.name, exc_info=True)
            return None

    @staticmethod
    def _extract_listing_id(url: str) -> str:
        match = _LISTING_ID_RE.search(url)
        if match:
            return match.group(1)
        logger.warning(
            "Could not extract a numeric listing ID from URL '%s'; falling back to full URL "
            "as the dedup key (the ID extraction regex may need updating)",
            url,
        )
        return url

    @staticmethod
    def _parse_price(text: str) -> int | None:
        digits = re.sub(r"[^\d]", "", text)
        return int(digits) if digits else None

    @staticmethod
    def _parse_bedrooms(card: Locator) -> int | None:
        try:
            label = card.locator("[aria-label*='bedroom']").first.get_attribute("aria-label") or ""
            match = re.search(r"(\d+)", label)
            return int(match.group(1)) if match else None
        except Exception:
            return None
