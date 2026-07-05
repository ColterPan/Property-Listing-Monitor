"""SQLite-backed dedup store: tracks which listings have already been seen per search."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from types import TracebackType

from property_monitor.models import Listing

_SCHEMA = """
CREATE TABLE IF NOT EXISTS seen_listings (
    search_name     TEXT NOT NULL,
    listing_id      TEXT NOT NULL,
    portal          TEXT NOT NULL,
    url             TEXT NOT NULL,
    title           TEXT,
    price           INTEGER,
    bedrooms        INTEGER,
    property_type   TEXT,
    first_seen_at   TEXT NOT NULL,
    last_checked_at TEXT NOT NULL,
    PRIMARY KEY (search_name, listing_id)
);

CREATE TABLE IF NOT EXISTS run_log (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at    TEXT NOT NULL,
    finished_at   TEXT,
    search_name   TEXT NOT NULL,
    status        TEXT NOT NULL,
    new_count     INTEGER NOT NULL DEFAULT 0,
    error_message TEXT
);
"""


class SeenListingStore:
    """Wraps a SQLite connection providing per-search dedup and run history."""

    def __init__(self, db_path: Path) -> None:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(db_path)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=FULL")
        self._init_schema()

    def _init_schema(self) -> None:
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    def has_prior_successful_run(self, search_name: str) -> bool:
        row = self._conn.execute(
            "SELECT 1 FROM run_log WHERE search_name = ? AND status = 'ok' LIMIT 1",
            (search_name,),
        ).fetchone()
        return row is not None

    def get_seen_ids(self, search_name: str) -> set[str]:
        rows = self._conn.execute(
            "SELECT listing_id FROM seen_listings WHERE search_name = ?",
            (search_name,),
        ).fetchall()
        return {row[0] for row in rows}

    def record_new_listings(self, search_name: str, listings: list[Listing]) -> None:
        """Persist newly-seen listings for a search in a single transaction."""
        now = datetime.now(UTC).isoformat()
        with self._conn:
            self._conn.executemany(
                """
                INSERT INTO seen_listings (
                    search_name, listing_id, portal, url, title, price,
                    bedrooms, property_type, first_seen_at, last_checked_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT (search_name, listing_id) DO UPDATE SET
                    last_checked_at = excluded.last_checked_at
                """,
                [
                    (
                        search_name,
                        listing.listing_id,
                        listing.portal,
                        listing.url,
                        listing.title,
                        listing.price,
                        listing.bedrooms,
                        listing.property_type.value if listing.property_type else None,
                        now,
                        now,
                    )
                    for listing in listings
                ],
            )

    def record_run(
        self,
        search_name: str,
        started_at: datetime,
        status: str,
        new_count: int = 0,
        error_message: str | None = None,
    ) -> None:
        with self._conn:
            self._conn.execute(
                """
                INSERT INTO run_log (started_at, finished_at, search_name, status, new_count, error_message)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    started_at.isoformat(),
                    datetime.now(UTC).isoformat(),
                    search_name,
                    status,
                    new_count,
                    error_message,
                ),
            )

    def last_error_alert_at(self, search_name: str) -> datetime | None:
        row = self._conn.execute(
            """
            SELECT MAX(started_at) FROM run_log
            WHERE search_name = ? AND status = 'error'
            """,
            (search_name,),
        ).fetchone()
        if row is None or row[0] is None:
            return None
        return datetime.fromisoformat(row[0])

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> SeenListingStore:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        self.close()
