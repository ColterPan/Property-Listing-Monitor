"""Scraper implementations, registered by portal name in SCRAPER_REGISTRY."""

from __future__ import annotations

from property_monitor.scrapers.base import SCRAPER_REGISTRY, ScraperBase
from property_monitor.scrapers.ninetynine import NinetyNineScraper
from property_monitor.scrapers.propertyguru import PropertyGuruScraper

SCRAPER_REGISTRY[PropertyGuruScraper.portal_name] = PropertyGuruScraper
SCRAPER_REGISTRY[NinetyNineScraper.portal_name] = NinetyNineScraper

__all__ = ["ScraperBase", "SCRAPER_REGISTRY", "PropertyGuruScraper", "NinetyNineScraper"]
