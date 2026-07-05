from datetime import UTC, datetime

import httpx
import pytest

from property_monitor.models import Listing, ListingIntent, PropertyType
from property_monitor.notifier import TelegramNotifier, format_listing_message, format_system_alert


def _listing(**overrides) -> Listing:
    defaults = dict(
        listing_id="1",
        url="https://example.com/1",
        title="3-room HDB flat",
        portal="propertyguru",
        intent=ListingIntent.SALE,
        scraped_at=datetime.now(UTC),
        price=480_000,
        raw_price_text="S$480,000",
        location="Tampines",
        bedrooms=3,
        property_type=PropertyType.HDB,
    )
    defaults.update(overrides)
    return Listing(**defaults)


def test_format_listing_message_includes_key_fields() -> None:
    message = format_listing_message(_listing(), "Tampines 3-room resale")

    assert "Tampines 3-room resale" in message
    assert "S$480,000" in message
    assert "3 bedroom(s)" in message
    assert "https://example.com/1" in message


def test_format_listing_message_falls_back_to_raw_price_text() -> None:
    message = format_listing_message(_listing(price=None, raw_price_text="Contact agent"), "Search A")
    assert "Contact agent" in message


def test_format_listing_message_omits_missing_bedrooms() -> None:
    message = format_listing_message(_listing(bedrooms=None), "Search A")
    assert "bedroom" not in message


def test_format_system_alert_is_terse_and_labeled() -> None:
    message = format_system_alert("Search A", "no listing cards found")
    assert "Search A" in message
    assert "no listing cards found" in message
    assert message.startswith("⚠️")


def test_telegram_notifier_sends_expected_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    captured = {}

    def fake_post(url, json, timeout):
        captured["url"] = url
        captured["json"] = json
        return httpx.Response(200, request=httpx.Request("POST", url))

    monkeypatch.setattr("property_monitor.notifier.httpx.post", fake_post)

    notifier = TelegramNotifier(bot_token="TOKEN", chat_id="42")
    notifier.send("hello")

    assert captured["url"] == "https://api.telegram.org/botTOKEN/sendMessage"
    assert captured["json"] == {"chat_id": "42", "text": "hello"}


def test_telegram_notifier_raises_on_http_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_post(url, json, timeout):
        request = httpx.Request("POST", url)
        return httpx.Response(500, request=request)

    monkeypatch.setattr("property_monitor.notifier.httpx.post", fake_post)

    notifier = TelegramNotifier(bot_token="TOKEN", chat_id="42")
    with pytest.raises(httpx.HTTPStatusError):
        notifier.send("hello")
