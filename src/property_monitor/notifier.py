"""Telegram notifications for new listings and monitor self-alerts."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod

import httpx

from property_monitor.models import Listing

logger = logging.getLogger(__name__)

_TELEGRAM_API_BASE = "https://api.telegram.org"


class NotifierBase(ABC):
    @abstractmethod
    def send(self, message: str) -> None:
        """Send a plain message. Raises on delivery failure."""


def format_listing_message(listing: Listing, search_name: str) -> str:
    """Pure formatting function -- no I/O, easy to unit test."""
    lines = [f"\U0001f3e0 New listing: {search_name}"]

    descriptor_parts = [p for p in (listing.location, listing.property_type, listing.intent) if p]
    if descriptor_parts:
        lines.append(" · ".join(str(p).title() for p in descriptor_parts))

    if listing.price is not None:
        lines.append(f"\U0001f4b0 S${listing.price:,}")
    elif listing.raw_price_text:
        lines.append(f"\U0001f4b0 {listing.raw_price_text}")

    if listing.bedrooms is not None:
        lines.append(f"\U0001f6cf {listing.bedrooms} bedroom(s)")

    lines.append(f"\U0001f517 {listing.url}")
    lines.append(f"\nMatched search: \"{search_name}\"")
    return "\n".join(lines)


def format_system_alert(search_name: str, error_summary: str) -> str:
    return (
        f"⚠️ Property Monitor error\n"
        f"Search: {search_name}\n"
        f"{error_summary}\n"
        f"See log for details."
    )


class TelegramNotifier(NotifierBase):
    def __init__(self, bot_token: str, chat_id: str, timeout_seconds: float = 15.0) -> None:
        self._chat_id = chat_id
        self._url = f"{_TELEGRAM_API_BASE}/bot{bot_token}/sendMessage"
        self._timeout_seconds = timeout_seconds

    def send(self, message: str) -> None:
        try:
            response = httpx.post(
                self._url,
                json={"chat_id": self._chat_id, "text": message},
                timeout=self._timeout_seconds,
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            logger.error("Failed to send Telegram message: %s", exc, exc_info=True)
            raise

    def send_listing_alert(self, listing: Listing, search_name: str) -> None:
        self.send(format_listing_message(listing, search_name))

    def send_system_alert(self, search_name: str, error_summary: str) -> None:
        self.send(format_system_alert(search_name, error_summary))
