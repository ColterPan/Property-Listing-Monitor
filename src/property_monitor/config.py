"""Loads and validates application configuration from a YAML file plus .env secrets."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from dotenv import load_dotenv

from property_monitor.models import ListingIntent, PropertyType, SavedSearch


class ConfigError(Exception):
    """Raised when configuration is missing or invalid. Fails fast at startup."""


@dataclass(slots=True)
class AppConfig:
    telegram_bot_token: str
    telegram_chat_id: str
    searches: list[SavedSearch]
    poll_interval_minutes: int = 20
    headless: bool = True
    log_level: str = "INFO"
    notify_on_first_run: bool = False
    self_alert_cooldown_hours: int = 6
    db_path: Path = field(default_factory=lambda: Path("data/listings.db"))
    log_dir: Path = field(default_factory=lambda: Path("logs"))


def _require_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise ConfigError(
            f"Missing required environment variable '{name}'. "
            "Copy .env.example to .env and fill in your Telegram credentials."
        )
    return value


def _parse_search(raw: dict, index: int) -> SavedSearch:
    try:
        name = str(raw["name"]).strip()
        portal = str(raw["portal"]).strip().lower()
        location = str(raw["location"]).strip()
        intent = ListingIntent(str(raw["intent"]).strip().lower())
        property_type = PropertyType(str(raw["property_type"]).strip().lower())
    except KeyError as exc:
        raise ConfigError(f"searches[{index}] is missing required field {exc}") from exc
    except ValueError as exc:
        raise ConfigError(f"searches[{index}] has an invalid enum value: {exc}") from exc

    if not name:
        raise ConfigError(f"searches[{index}].name must not be empty")
    if not location:
        raise ConfigError(f"searches[{index}].location must not be empty")

    min_price = raw.get("min_price")
    max_price = raw.get("max_price")
    if min_price is not None and max_price is not None and min_price > max_price:
        raise ConfigError(
            f"searches[{index}] ('{name}'): min_price ({min_price}) exceeds max_price ({max_price})"
        )

    return SavedSearch(
        name=name,
        portal=portal,
        location=location,
        property_type=property_type,
        intent=intent,
        min_price=min_price,
        max_price=max_price,
        notify_on_first_run=raw.get("notify_on_first_run"),
        max_pages=int(raw.get("max_pages", 1)),
    )


def load_config(config_path: Path, env_path: Path | None = None) -> AppConfig:
    """Load YAML config + .env secrets into a validated AppConfig.

    Raises ConfigError on any missing/invalid field rather than failing later
    inside a scrape run.
    """
    if not config_path.exists():
        raise ConfigError(f"Config file not found: {config_path}")

    load_dotenv(dotenv_path=env_path)

    try:
        raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        raise ConfigError(f"Failed to parse {config_path}: {exc}") from exc

    raw_searches = raw.get("searches")
    if not raw_searches:
        raise ConfigError("Config must define at least one entry under 'searches'")

    searches = [_parse_search(item, i) for i, item in enumerate(raw_searches)]

    names_seen = set()
    for search in searches:
        if search.name in names_seen:
            raise ConfigError(
                f"Duplicate search name '{search.name}' -- names must be unique "
                "since they key the dedup store"
            )
        names_seen.add(search.name)

    return AppConfig(
        telegram_bot_token=_require_env("TELEGRAM_BOT_TOKEN"),
        telegram_chat_id=_require_env("TELEGRAM_CHAT_ID"),
        searches=searches,
        poll_interval_minutes=int(raw.get("poll_interval_minutes", 20)),
        headless=bool(raw.get("headless", True)),
        log_level=str(raw.get("log_level", "INFO")).upper(),
        notify_on_first_run=bool(raw.get("notify_on_first_run", False)),
        self_alert_cooldown_hours=int(raw.get("self_alert_cooldown_hours", 6)),
    )
