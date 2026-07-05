"""Common scraper interface. Each portal implements this and registers itself.

Adding a new portal later (e.g. 99.co) means implementing this interface and
adding one entry to SCRAPER_REGISTRY -- no changes to the orchestrator.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import ClassVar

from property_monitor.models import Listing, SavedSearch


class ScraperBase(ABC):
    portal_name: ClassVar[str]

    @abstractmethod
    def fetch_listings(self, search: SavedSearch) -> list[Listing]:
        """Return the current listings matching `search`.

        Raises property_monitor.scrapers.exceptions.ScrapeError if the page
        structure can't be reliably parsed (as opposed to returning an empty
        list, which means "zero results matched the filters").
        """


SCRAPER_REGISTRY: dict[str, type[ScraperBase]] = {}
