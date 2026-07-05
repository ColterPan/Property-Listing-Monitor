"""Core data models shared across scrapers, storage, and notifications."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class PropertyType(StrEnum):
    HDB = "hdb"
    CONDO = "condo"
    LANDED = "landed"
    OTHER = "other"


class ListingIntent(StrEnum):
    RENT = "rent"
    SALE = "sale"


@dataclass(frozen=True, slots=True)
class Listing:
    """A single scraped property listing."""

    listing_id: str
    url: str
    title: str
    portal: str
    intent: ListingIntent
    scraped_at: datetime
    price: int | None = None
    raw_price_text: str = ""
    location: str = ""
    bedrooms: int | None = None
    property_type: PropertyType | None = None


@dataclass(slots=True)
class SavedSearch:
    """A user-configured search to monitor on a given portal."""

    name: str
    portal: str
    location: str
    property_type: PropertyType
    intent: ListingIntent
    min_price: int | None = None
    max_price: int | None = None
    notify_on_first_run: bool | None = None
    max_pages: int = 1
