"""Tests for the SQLite data layer."""

import sqlite3

import pytest

from app.db import Database, PropertyStatus


def test_schema_is_idempotent(tmp_path):
    path = tmp_path / "nested" / "dir" / "app.db"
    first = Database(path)
    property_id = first.create_property({"address": "1 Main"})

    second = Database(path)

    assert second.get_property(property_id)["address"] == "1 Main"


def test_property_round_trip(db):
    property_id = db.create_property(
        {"address": "1 Main", "price": 500000, "enrichment": {"x": {"a": 1}}, "visited": True}
    )

    prop = db.get_property(property_id)

    assert prop["status"] == PropertyStatus.NEW
    assert prop["enrichment"] == {"x": {"a": 1}}
    assert prop["visited"] is True
    assert prop["notes"] == ""
    assert prop["photo_count"] == 0
    assert prop["created_at"]


def test_update_and_delete(db):
    property_id = db.create_property({"address": "1 Main"})

    assert db.update_property(property_id, {"rating": 4, "visited": False}) is True
    assert db.get_property(property_id)["rating"] == 4
    assert db.update_property(999, {"rating": 1}) is False

    assert db.delete_property(property_id) is True
    assert db.get_property(property_id) is None


def test_rejects_unknown_columns(db):
    with pytest.raises(ValueError, match="Unknown columns"):
        db.create_property({"address": "1 Main", "id; DROP TABLE properties": 1})
    property_id = db.create_property({"address": "1 Main"})
    with pytest.raises(ValueError):
        db.update_property(property_id, {"created_at": "x"})


def test_find_property(db):
    property_id = db.create_property({"address": "1 Main St", "zillow_id": "123"})

    assert db.find_property(zillow_id="123") == property_id
    assert db.find_property(address=" 1 main st ") == property_id
    assert db.find_property(zillow_id="999") is None
    assert db.find_property() is None


def test_list_sorts_and_cover_photo(db):
    cheap = db.create_property({"address": "B", "price": 100})
    pricey = db.create_property({"address": "A", "price": 900})
    db.create_property({"address": "C"})
    first_photo = db.add_photo(cheap, "a.jpg", "image/jpeg", b"1")
    db.add_photo(cheap, "b.jpg", "image/jpeg", b"2")

    assert [p["address"] for p in db.list_properties("price")] == ["B", "A", "C"]
    assert [p["address"] for p in db.list_properties("price_desc")] == ["A", "B", "C"]
    assert [p["address"] for p in db.list_properties("address")] == ["A", "B", "C"]
    # Unknown sorts fall back to newest
    assert [p["address"] for p in db.list_properties("nope; DROP")][0] == "C"
    by_id = {p["id"]: p for p in db.list_properties()}
    assert by_id[cheap]["cover_photo_id"] == first_photo
    assert by_id[pricey]["cover_photo_id"] is None


def test_photos_are_deleted_with_property(db):
    property_id = db.create_property({"address": "1 Main"})
    photo_id = db.add_photo(property_id, "a.jpg", "image/jpeg", b"jpeg")

    assert db.get_photo(photo_id).data == b"jpeg"
    assert db.get_property(property_id)["photo_count"] == 1

    db.delete_property(property_id)

    assert db.get_photo(photo_id) is None


def test_delete_photo(db):
    property_id = db.create_property({"address": "1 Main"})
    photo_id = db.add_photo(property_id, "a.jpg", "image/jpeg", b"jpeg")

    assert db.delete_photo(photo_id) is True
    assert db.photo_ids(property_id) == []


def test_property_ids_with_status(db):
    a = db.create_property({"address": "A"})
    b = db.create_property({"address": "B", "status": PropertyStatus.ENRICHING})
    db.create_property({"address": "C", "status": PropertyStatus.ENRICHED})

    assert db.property_ids_with_status(*PropertyStatus.PENDING) == [a, b]


def test_locations(db):
    work = db.create_location({"name": "Work", "address": "1 Office", "priority": 1})
    mom = db.create_location({"name": "Mom", "address": "2 Home", "priority": 5})
    db.create_location({"name": "Old", "address": "3 Rd", "active": 0})

    assert [loc["name"] for loc in db.list_locations()] == ["Mom", "Work", "Old"]
    assert [loc["name"] for loc in db.list_locations(active_only=True)] == ["Mom", "Work"]

    db.update_location(work, {"active": 0})
    db.delete_location(mom)

    assert db.list_locations(active_only=True) == []


def test_settings(db):
    assert db.get_setting("missing") == ""
    db.set_setting("k", "one")
    db.set_setting("k", "two")
    assert db.get_setting("k") == "two"


def test_adds_new_columns_to_an_existing_database(tmp_path):
    path = tmp_path / "old.db"
    with sqlite3.connect(path) as conn:  # a database from before neighborhood_rating
        conn.execute(
            "CREATE TABLE properties (id INTEGER PRIMARY KEY, address TEXT NOT NULL,"
            " zillow_url TEXT, zillow_id TEXT UNIQUE, status TEXT NOT NULL DEFAULT 'new',"
            " error TEXT, listing_json TEXT, price INTEGER, beds REAL, baths REAL, sqft INTEGER,"
            " lot_acres REAL, year_built INTEGER, property_type TEXT, latitude REAL,"
            " longitude REAL, enrichment TEXT NOT NULL DEFAULT '{}', enriched_at TEXT,"
            " notes TEXT NOT NULL DEFAULT '', rating INTEGER,"
            " visited INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL)"
        )
        conn.execute("INSERT INTO properties (address, created_at) VALUES ('1 Main', 'x')")

    db = Database(path)
    db.update_property(1, {"neighborhood_rating": 4, "garage_spaces": 2})

    assert db.get_property(1)["neighborhood_rating"] == 4
    assert db.get_property(1)["garage_spaces"] == 2
    assert db.get_property(1)["address"] == "1 Main"
    Database(path)  # running the migration again is a no-op


def test_sort_by_neighborhood(db):
    db.create_property({"address": "Plain", "neighborhood_rating": 2})
    db.create_property({"address": "Unrated"})
    db.create_property({"address": "Lovely", "neighborhood_rating": 5})

    assert [p["address"] for p in db.list_properties("neighborhood")] == [
        "Lovely",
        "Plain",
        "Unrated",
    ]


def test_stored_walk_scores_are_removed_on_open(tmp_path):
    """Earlier versions saved them; Walk Score's terms don't allow that."""
    path = tmp_path / "db.sqlite"
    db = Database(path)
    property_id = db.create_property(
        {
            "address": "1 Main",
            "enrichment": {"walk_score_provider": {"walk_score": 72}, "flood_zone_provider": {"flood_zone": "X"}},
            "enrichment_meta": {"walk_score_provider": {"ok": True}, "flood_zone_provider": {"ok": True}},
        }
    )  # fmt: skip
    untouched = db.create_property({"address": "2 Main"})

    reopened = Database(path)

    prop = reopened.get_property(property_id)
    assert prop["enrichment"] == {"flood_zone_provider": {"flood_zone": "X"}}
    assert prop["enrichment_meta"] == {"flood_zone_provider": {"ok": True}}
    assert reopened.get_property(untouched)["enrichment"] == {}
