"""99.co scraper.

Search-URL params and the listing-card selectors below were verified against
the live site on 2026-07-05 -- see docs/99co_notes.md for the exact method
and for the parts that are still unconfirmed (property-type sub-filtering,
"newest first" sort, rent-path assumption). Re-verify periodically; the
site's DOM/params can change without notice.
"""

from __future__ import annotations

import logging
import re
from datetime import UTC, datetime
from urllib.parse import quote_plus

from playwright.sync_api import Locator, Page, TimeoutError as PlaywrightTimeoutError, sync_playwright

from property_monitor.models import Listing, ListingIntent, SavedSearch
from property_monitor.scrapers.base import ScraperBase
from property_monitor.scrapers.exceptions import ScrapeError

logger = logging.getLogger(__name__)

BASE_URL = "https://www.99.co"

# Confirmed working: https://www.99.co/singapore/{sale|rent}?keywords=...&price_min=...&price_max=...
# NOT confirmed: per-property-type segment slugs (hdb/condo/landed all returned
# zero results) -- "residential" is the site's own default and is what's used
# here; property_type is NOT filtered at the query level. See docs/99co_notes.md.
_PROPERTY_SEGMENT = "residential"

LISTING_CARD_SELECTOR = "[data-cy='listingCard']"
_LISTING_ID_RE = re.compile(r"-([A-Za-z0-9]{10,})/?(?:\?.*)?$")
_PRICE_RE = re.compile(r"S\$\s?[\d,]+(?!\s*psf)")
_BEDROOM_RE = re.compile(r"(\d+)\s*Bed")

_MIN_PARSE_SUCCESS_RATIO = 0.5


class NinetyNineScraper(ScraperBase):
    portal_name = "99co"

    def __init__(self, headless: bool = True, timeout_ms: int = 30_000) -> None:
        self._headless = headless
        self._timeout_ms = timeout_ms

    def fetch_listings(self, search: SavedSearch) -> list[Listing]:
        url = self._build_search_url(search)
        logger.debug("Navigating to 99.co search URL: %s", url)

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=self._headless)
            try:
                page = browser.new_page(
                    user_agent=(
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
                    )
                )
                page.goto(url, timeout=self._timeout_ms, wait_until="domcontentloaded")
                return self._extract_listings(page, search)
            finally:
                browser.close()

    def _build_search_url(self, search: SavedSearch) -> str:
        segment = "rent" if search.intent == ListingIntent.RENT else "sale"
        params = [
            f"keywords={quote_plus(search.location)}",
            "main_category=all",
            f"page_size={max(search.max_pages, 1) * 36}",
            f"property_segments={_PROPERTY_SEGMENT}",
            "query_ids=singapore",
            "query_type=city",
            "sort_field=relevance",
            "sort_order=desc",
        ]
        if search.min_price is not None:
            params.append(f"price_min={search.min_price}")
        if search.max_price is not None:
            params.append(f"price_max={search.max_price}")

        return f"{BASE_URL}/singapore/{segment}?{'&'.join(params)}"

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
            name_el = card.locator("[data-cy='listingName']").first
            href = name_el.get_attribute("href") or ""
            if not href:
                logger.warning("Listing card had no href; skipping")
                return None
            url = href if href.startswith("http") else f"{BASE_URL}{href}"

            listing_id = self._extract_listing_id(url)
            title = name_el.inner_text().strip()

            price_block = card.locator("[data-cy='listingPsfPrice']").first
            raw_price_text = price_block.inner_text().strip() if price_block.count() else ""

            return Listing(
                listing_id=listing_id,
                url=url,
                title=title,
                portal=self.portal_name,
                intent=search.intent,
                scraped_at=datetime.now(UTC),
                price=self._parse_price(raw_price_text),
                raw_price_text=raw_price_text,
                location=title,
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
            "Could not extract a listing ID from URL '%s'; falling back to full URL "
            "as the dedup key (the ID extraction regex may need updating)",
            url,
        )
        return url

    @staticmethod
    def _parse_price(text: str) -> int | None:
        match = _PRICE_RE.search(text)
        if not match:
            return None
        digits = re.sub(r"[^\d]", "", match.group(0))
        return int(digits) if digits else None

    @staticmethod
    def _parse_bedrooms(card: Locator) -> int | None:
        try:
            text = card.inner_text()
        except Exception:
            return None
        match = _BEDROOM_RE.search(text)
        return int(match.group(1)) if match else None
