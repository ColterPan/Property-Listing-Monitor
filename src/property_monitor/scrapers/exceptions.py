"""Exceptions raised by scraper implementations."""

from __future__ import annotations


class ScrapeError(Exception):
    """Raised when a scraper cannot reliably extract listings.

    Distinct from "zero listings matched the search" (a legitimate, silent
    outcome) -- this signals the page structure/selectors are likely broken
    and should trigger an operator-facing alert.
    """
