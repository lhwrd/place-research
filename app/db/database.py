"""SQLite database: the only data store.

A connection is opened per operation. Calls are small and local, so they run directly in
the event loop. Photos are stored as BLOBs so the whole dataset is one file to back up.
"""

import json
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional

from app.core.config import settings


class PropertyStatus:
    """Enrichment state of a property."""

    NEW = "new"  # added; enrichment queued
    ENRICHING = "enriching"
    ENRICHED = "enriched"
    ERROR = "error"

    PENDING = (NEW, ENRICHING)


SCHEMA = """
CREATE TABLE IF NOT EXISTS properties (
    id            INTEGER PRIMARY KEY,
    address       TEXT NOT NULL,
    zillow_url    TEXT,
    zillow_id     TEXT UNIQUE,
    status        TEXT NOT NULL DEFAULT 'new',
    error         TEXT,
    listing_json  TEXT,
    price         INTEGER,
    beds          REAL,
    baths         REAL,
    sqft          INTEGER,
    lot_acres     REAL,
    year_built    INTEGER,
    property_type TEXT,
    garage_spaces INTEGER,
    latitude      REAL,
    longitude     REAL,
    -- JSON object: provider name -> that provider's latest successful data
    enrichment    TEXT NOT NULL DEFAULT '{}',
    enriched_at   TEXT,
    -- JSON object: provider name -> {"at", "ok", "inputs"} for its latest run, which decides
    -- whether a refresh needs to call it again
    enrichment_meta TEXT NOT NULL DEFAULT '{}',
    -- Yours; enrichment never writes these
    notes         TEXT NOT NULL DEFAULT '',
    rating        INTEGER,
    -- 1-5: how the neighborhood looks (e.g. on Street View)
    neighborhood_rating INTEGER,
    visited       INTEGER NOT NULL DEFAULT 0,
    created_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS photos (
    id           INTEGER PRIMARY KEY,
    property_id  INTEGER NOT NULL REFERENCES properties(id) ON DELETE CASCADE,
    filename     TEXT NOT NULL,
    content_type TEXT NOT NULL,
    data         BLOB NOT NULL,
    created_at   TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS photos_property ON photos(property_id);

CREATE TABLE IF NOT EXISTS locations (
    id       INTEGER PRIMARY KEY,
    name     TEXT NOT NULL,
    address  TEXT NOT NULL,
    type     TEXT,
    active   INTEGER NOT NULL DEFAULT 1,
    priority INTEGER NOT NULL DEFAULT 0,
    -- Geocoded once from the address; cleared when the address changes
    latitude  REAL,
    longitude REAL,
    city      TEXT,
    state     TEXT
);

CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""

# Columns callers may set through create_property / update_property
PROPERTY_COLUMNS = frozenset(
    {
        "address",
        "zillow_url",
        "zillow_id",
        "status",
        "error",
        "listing_json",
        "price",
        "beds",
        "baths",
        "sqft",
        "lot_acres",
        "year_built",
        "property_type",
        "garage_spaces",
        "latitude",
        "longitude",
        "enrichment",
        "enriched_at",
        "enrichment_meta",
        "notes",
        "rating",
        "neighborhood_rating",
        "visited",
    }
)

# Columns added after the first release: (table, column, definition). Databases created
# before then get them via ALTER TABLE on startup; CREATE TABLE above has them already.
ADDED_COLUMNS = [
    ("properties", "neighborhood_rating", "INTEGER"),
    ("properties", "garage_spaces", "INTEGER"),
    ("properties", "enrichment_meta", "TEXT NOT NULL DEFAULT '{}'"),
    ("locations", "latitude", "REAL"),
    ("locations", "longitude", "REAL"),
    ("locations", "city", "TEXT"),
    ("locations", "state", "TEXT"),
]
LOCATION_GEOCODE_COLUMNS = ("latitude", "longitude", "city", "state")
LOCATION_COLUMNS = frozenset(
    {"name", "address", "type", "active", "priority", *LOCATION_GEOCODE_COLUMNS}
)
LOCATION_TYPES = ("Family", "Friend", "Work", "Other")

# Sortable columns on the property list: query value -> ORDER BY clause
PROPERTY_SORTS = {
    "newest": "created_at DESC",
    "price": "price IS NULL, price",
    "price_desc": "price IS NULL, price DESC",
    "rating": "rating IS NULL, rating DESC",
    "neighborhood": "neighborhood_rating IS NULL, neighborhood_rating DESC",
    "address": "address COLLATE NOCASE",
}


@dataclass
class Photo:
    id: int
    property_id: int
    filename: str
    content_type: str
    data: bytes


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Database:
    """Thin data-access layer over one SQLite file."""

    def __init__(self, path: Path | str):
        self.path = str(path)
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.executescript(SCHEMA)
            _add_missing_columns(conn)
            _remove_stored_walk_scores(conn)

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            with conn:  # commits on success, rolls back on error
                yield conn
        finally:
            conn.close()

    # Properties

    def create_property(self, values: Dict[str, Any]) -> int:
        values = self._encode(values)
        values.setdefault("status", PropertyStatus.NEW)
        values["created_at"] = _now()
        _check_columns(values, PROPERTY_COLUMNS | {"created_at"})
        columns = ", ".join(values)
        placeholders = ", ".join("?" for _ in values)
        with self._connect() as conn:
            cursor = conn.execute(
                f"INSERT INTO properties ({columns}) VALUES ({placeholders})",
                list(values.values()),
            )
            return int(cursor.lastrowid or 0)

    def get_property(self, property_id: int) -> Optional[Dict[str, Any]]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT p.*, (SELECT COUNT(*) FROM photos WHERE property_id = p.id) AS photo_count"
                " FROM properties p WHERE p.id = ?",
                (property_id,),
            ).fetchone()
        return self._decode(row) if row else None

    def find_property(self, *, zillow_id: Optional[str] = None, address: Optional[str] = None):
        """The first property matching a zpid, or an address (case-insensitive)."""
        if zillow_id:
            sql, arg = "SELECT id FROM properties WHERE zillow_id = ?", zillow_id
        elif address:
            sql, arg = (
                "SELECT id FROM properties WHERE lower(trim(address)) = lower(trim(?))",
                address,
            )
        else:
            return None
        with self._connect() as conn:
            row = conn.execute(sql, (arg,)).fetchone()
        return row["id"] if row else None

    def list_properties(self, sort: str = "newest") -> List[Dict[str, Any]]:
        order = PROPERTY_SORTS.get(sort, PROPERTY_SORTS["newest"])
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT p.*, (SELECT id FROM photos WHERE property_id = p.id ORDER BY id LIMIT 1)"
                f" AS cover_photo_id FROM properties p ORDER BY {order}, id DESC"
            ).fetchall()
        return [self._decode(r) for r in rows]

    def property_ids_with_status(self, *statuses: str) -> List[int]:
        placeholders = ", ".join("?" for _ in statuses)
        with self._connect() as conn:
            rows = conn.execute(
                f"SELECT id FROM properties WHERE status IN ({placeholders}) ORDER BY id",
                statuses,
            ).fetchall()
        return [r["id"] for r in rows]

    def update_property(self, property_id: int, values: Dict[str, Any]) -> bool:
        if not values:
            return True
        values = self._encode(values)
        _check_columns(values, PROPERTY_COLUMNS)
        assignments = ", ".join(f"{k} = ?" for k in values)
        with self._connect() as conn:
            cursor = conn.execute(
                f"UPDATE properties SET {assignments} WHERE id = ?",
                [*values.values(), property_id],
            )
            return cursor.rowcount > 0

    def delete_property(self, property_id: int) -> bool:
        with self._connect() as conn:
            return conn.execute("DELETE FROM properties WHERE id = ?", (property_id,)).rowcount > 0

    # Photos

    def add_photo(self, property_id: int, filename: str, content_type: str, data: bytes) -> int:
        with self._connect() as conn:
            cursor = conn.execute(
                "INSERT INTO photos (property_id, filename, content_type, data, created_at)"
                " VALUES (?, ?, ?, ?, ?)",
                (property_id, filename, content_type, data, _now()),
            )
            return int(cursor.lastrowid or 0)

    def photo_ids(self, property_id: int) -> List[int]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT id FROM photos WHERE property_id = ? ORDER BY id", (property_id,)
            ).fetchall()
        return [r["id"] for r in rows]

    def get_photo(self, photo_id: int) -> Optional[Photo]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT id, property_id, filename, content_type, data FROM photos WHERE id = ?",
                (photo_id,),
            ).fetchone()
        return Photo(**dict(row)) if row else None

    def delete_photo(self, photo_id: int) -> bool:
        with self._connect() as conn:
            return conn.execute("DELETE FROM photos WHERE id = ?", (photo_id,)).rowcount > 0

    # Locations

    def list_locations(self, active_only: bool = False) -> List[Dict[str, Any]]:
        where = "WHERE active = 1" if active_only else ""
        with self._connect() as conn:
            rows = conn.execute(
                f"SELECT * FROM locations {where} ORDER BY priority DESC, name COLLATE NOCASE"
            ).fetchall()
        return [{**dict(r), "active": bool(r["active"])} for r in rows]

    def create_location(self, values: Dict[str, Any]) -> int:
        _check_columns(values, LOCATION_COLUMNS)
        columns = ", ".join(values)
        placeholders = ", ".join("?" for _ in values)
        with self._connect() as conn:
            cursor = conn.execute(
                f"INSERT INTO locations ({columns}) VALUES ({placeholders})",
                list(values.values()),
            )
            return int(cursor.lastrowid or 0)

    def update_location(self, location_id: int, values: Dict[str, Any]) -> bool:
        """Update a location. A new address drops the stored coordinates of the old one."""
        _check_columns(values, LOCATION_COLUMNS)
        if not values:
            return True
        with self._connect() as conn:
            if "address" in values and "latitude" not in values:
                row = conn.execute(
                    "SELECT address FROM locations WHERE id = ?", (location_id,)
                ).fetchone()
                if row is not None and row["address"] != values["address"]:
                    values = {**values, **dict.fromkeys(LOCATION_GEOCODE_COLUMNS)}
            assignments = ", ".join(f"{k} = ?" for k in values)
            cursor = conn.execute(
                f"UPDATE locations SET {assignments} WHERE id = ?",
                [*values.values(), location_id],
            )
            return cursor.rowcount > 0

    def delete_location(self, location_id: int) -> bool:
        with self._connect() as conn:
            return conn.execute("DELETE FROM locations WHERE id = ?", (location_id,)).rowcount > 0

    # Settings (key/value)

    def get_setting(self, key: str, default: str = "") -> str:
        with self._connect() as conn:
            row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
        return row["value"] if row else default

    def set_setting(self, key: str, value: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO settings (key, value) VALUES (?, ?)"
                " ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (key, value),
            )

    # Encoding

    @staticmethod
    def _encode(values: Dict[str, Any]) -> Dict[str, Any]:
        encoded = dict(values)
        for column in ("enrichment", "enrichment_meta"):
            if column in encoded and not isinstance(encoded[column], str):
                encoded[column] = json.dumps(encoded[column])
        if "visited" in encoded:
            encoded["visited"] = int(bool(encoded["visited"]))
        return encoded

    @staticmethod
    def _decode(row: sqlite3.Row) -> Dict[str, Any]:
        record = dict(row)
        record["enrichment"] = json.loads(record.get("enrichment") or "{}")
        record["enrichment_meta"] = json.loads(record.get("enrichment_meta") or "{}")
        record["visited"] = bool(record.get("visited"))
        return record


def _remove_stored_walk_scores(conn: sqlite3.Connection) -> None:
    """
    Earlier versions saved Walk Score results with the other enrichment data. Its terms
    don't allow storing them (they're now fetched per page view), so delete any that remain.
    """
    conn.execute(
        """
        UPDATE properties
        SET enrichment = json_remove(enrichment, '$.walk_score_provider'),
            enrichment_meta = json_remove(enrichment_meta, '$.walk_score_provider')
        WHERE enrichment LIKE '%"walk_score_provider"%'
           OR enrichment_meta LIKE '%"walk_score_provider"%'
        """
    )


def _add_missing_columns(conn: sqlite3.Connection) -> None:
    for table, column, definition in ADDED_COLUMNS:
        existing = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}
        if column not in existing:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def _check_columns(values: Dict[str, Any], allowed: frozenset) -> None:
    unknown = set(values) - allowed
    if unknown:
        raise ValueError(f"Unknown columns: {sorted(unknown)}")


@lru_cache(maxsize=1)
def get_database() -> Database:
    """Process-wide database at DATABASE_PATH."""
    return Database(settings.database_path)
