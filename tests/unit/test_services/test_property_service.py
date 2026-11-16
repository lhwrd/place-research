"""Tests for property ingest and enrichment."""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, Mock

import pytest

from app.db import PropertyStatus
from app.services.property_service import (
    AMENITY_TYPES,
    PREFERRED_PLACES,
    ImageUpload,
    PropertyNotFoundError,
    PropertyService,
)

URL = "https://www.zillow.com/homedetails/111-White-Pl-Port-Orange-FL-32127/46284123_zpid/"
LISTING_JSON = {
    "property": {
        "zpid": 46284123,
        "price": 425000,
        "bedrooms": 3,
        "resoFacts": {"garageParkingCapacity": 2},
        "address": {
            "streetAddress": "111 White Pl",
            "city": "Port Orange",
            "state": "FL",
            "zipcode": "32127",
        },
    }
}


def _result(**providers):
    return {"enrichment_data": providers}


def _ok(data):
    return {"success": True, "data": data}


@pytest.fixture
def geocoder():
    geocoder = Mock()
    geocoder.geocode_address = AsyncMock(
        return_value={"latitude": 29.1, "longitude": -81.0, "city": "Port Orange", "state": "FL"}
    )
    return geocoder


@pytest.fixture
def orchestrator():
    orchestrator = Mock()
    orchestrator.enrich = AsyncMock(
        return_value=_result(walk_score_provider=_ok({"walk_score": 45}))
    )
    orchestrator.provider_info = Mock(
        return_value={
            "walk_score_provider": {"max_age_days": 90, "inputs": None},
            "highway_provider": {"max_age_days": 30, "inputs": None},
            "distance_provider": {"max_age_days": 30, "inputs": "locations-v1"},
        }
    )
    return orchestrator


ALL_PROVIDERS = ["walk_score_provider", "highway_provider", "distance_provider"]


def _ran(orchestrator):
    """The providers the latest orchestrator call was asked to run."""
    return orchestrator.enrich.call_args.kwargs["provider_filter"]


@pytest.fixture
def service(db, geocoder, orchestrator):
    return PropertyService(db=db, geocoder=geocoder, orchestrator=orchestrator)


class TestCreateListing:
    def test_creates_property_with_listing_facts(self, service, db):
        property_id, created = service.create_listing(URL, LISTING_JSON)

        prop = db.get_property(property_id)
        assert created is True
        assert prop["address"] == "111 White Pl, Port Orange, FL 32127"
        assert prop["zillow_id"] == "46284123"
        assert prop["zillow_url"] == URL
        assert prop["price"] == 425000
        assert prop["beds"] == 3
        assert prop["garage_spaces"] == 2
        assert prop["status"] == PropertyStatus.NEW
        assert '"zpid": 46284123' in prop["listing_json"]

    def test_falls_back_to_url_slug_address(self, service, db):
        property_id, _ = service.create_listing(URL)

        prop = db.get_property(property_id)
        assert prop["address"] == "111 White Pl Port Orange, FL 32127"
        assert prop["listing_json"] is None

    def test_resharing_returns_existing_property(self, service, db):
        first_id, _ = service.create_listing(URL, LISTING_JSON)
        second_id, created = service.create_listing(URL + "?utm=share")

        assert (second_id, created) == (first_id, False)
        assert len(db.list_properties()) == 1


class TestCreateFromInput:
    def test_address(self, service, db):
        property_id, created = service.create_from_input("  42 Elm St, Denver, CO  ")

        assert created is True
        assert db.get_property(property_id)["address"] == "42 Elm St, Denver, CO"

    def test_same_address_is_deduped(self, service):
        first_id, _ = service.create_from_input("42 Elm St, Denver, CO")
        second_id, created = service.create_from_input("42 elm st, denver, co")

        assert (second_id, created) == (first_id, False)

    def test_zillow_url(self, service, db):
        property_id, _ = service.create_from_input(URL)

        assert db.get_property(property_id)["zillow_id"] == "46284123"


class TestAddImages:
    def test_adds_photos(self, service, db):
        property_id, _ = service.create_from_input("1 Main St")

        count = service.add_images(
            property_id,
            [ImageUpload(b"a", "1.jpg", "image/jpeg"), ImageUpload(b"b", "2.png", "image/png")],
        )

        assert count == 2
        photos = [db.get_photo(i) for i in db.photo_ids(property_id)]
        assert [(p.filename, p.content_type, p.data) for p in photos] == [
            ("1.jpg", "image/jpeg", b"a"),
            ("2.png", "image/png", b"b"),
        ]

    def test_missing_property(self, service):
        with pytest.raises(PropertyNotFoundError):
            service.add_images(999, [ImageUpload(b"a", "1.jpg", "image/jpeg")])


class TestEnrich:
    @pytest.mark.asyncio
    async def test_enriches_property(self, service, db, orchestrator, geocoder):
        property_id, _ = service.create_from_input("111 White Pl")

        assert await service.enrich(property_id) is True

        prop = db.get_property(property_id)
        assert prop["status"] == PropertyStatus.ENRICHED
        assert prop["enrichment"] == {"walk_score_provider": {"walk_score": 45}}
        assert (prop["latitude"], prop["longitude"]) == (29.1, -81.0)
        assert prop["enriched_at"]
        assert prop["error"] is None
        geocoder.geocode_address.assert_awaited_once_with("111 White Pl")
        assert _ran(orchestrator) == ALL_PROVIDERS
        assert prop["enrichment_meta"]["walk_score_provider"]["ok"] is True

    @pytest.mark.asyncio
    async def test_uses_listing_coordinates(self, service, db, geocoder):
        listing = {"property": {**LISTING_JSON["property"], "latitude": 29.5, "longitude": -81.5}}
        property_id, _ = service.create_listing(URL, listing)

        await service.enrich(property_id)

        geocoder.geocode_address.assert_not_called()
        assert db.get_property(property_id)["latitude"] == 29.5

    @pytest.mark.asyncio
    async def test_second_run_only_calls_what_is_missing(self, service, orchestrator, geocoder):
        property_id, _ = service.create_from_input("1 Main")
        await service.enrich(property_id)

        await service.enrich(property_id)

        # Walk Score succeeded and is recent; the other two returned nothing the first time
        assert _ran(orchestrator) == ["highway_provider", "distance_provider"]
        # The coordinates found the first time are reused
        geocoder.geocode_address.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_nothing_to_run_makes_no_calls(self, service, db, orchestrator):
        orchestrator.enrich.return_value = _result(**{n: _ok({"x": 1}) for n in ALL_PROVIDERS})
        property_id, _ = service.create_from_input("1 Main")
        await service.enrich(property_id)

        await service.enrich(property_id)

        orchestrator.enrich.assert_awaited_once()
        assert db.get_property(property_id)["status"] == PropertyStatus.ENRICHED

    @pytest.mark.asyncio
    async def test_reruns_failed_expired_and_changed(self, service, db, orchestrator):
        orchestrator.enrich.return_value = _result(**{n: _ok({"x": 1}) for n in ALL_PROVIDERS})
        property_id, _ = service.create_from_input("1 Main")
        await service.enrich(property_id)
        runs = db.get_property(property_id)["enrichment_meta"]

        # Highway data is older than its 30 days
        old = (datetime.now(timezone.utc) - timedelta(days=31)).isoformat()
        db.update_property(
            property_id, {"enrichment_meta": {**runs, "highway_provider": {**runs["highway_provider"], "at": old}}}
        )  # fmt: skip
        await service.enrich(property_id)
        assert _ran(orchestrator) == ["highway_provider"]

        # A drive-time location was added on the Locations page
        orchestrator.provider_info.return_value["distance_provider"]["inputs"] = "locations-v2"
        await service.enrich(property_id)
        assert _ran(orchestrator) == ["distance_provider"]

        # Walk Score failed on that run, so the next one tries it again
        db.update_property(
            property_id,
            {"enrichment_meta": {**db.get_property(property_id)["enrichment_meta"],
                                 "walk_score_provider": {**runs["walk_score_provider"], "ok": False}}},
        )  # fmt: skip
        await service.enrich(property_id)
        assert _ran(orchestrator) == ["walk_score_provider"]

    @pytest.mark.asyncio
    async def test_bypass_cache_runs_everything(self, service, orchestrator):
        orchestrator.enrich.return_value = _result(**{n: _ok({"x": 1}) for n in ALL_PROVIDERS})
        property_id, _ = service.create_from_input("1 Main")
        await service.enrich(property_id)

        await service.enrich(property_id, use_cached=False)

        assert _ran(orchestrator) == ALL_PROVIDERS
        # The orchestrator's in-process cache is never consulted: it ignores settings
        assert orchestrator.enrich.call_args.kwargs["use_cached"] is False

    @pytest.mark.asyncio
    async def test_property_enriched_before_runs_were_recorded(self, service, db, orchestrator):
        property_id, _ = service.create_from_input("1 Main")
        db.update_property(
            property_id,
            {
                "latitude": 29.1,
                "longitude": -81.0,
                "enriched_at": datetime.now(timezone.utc).isoformat(),
                "error": "highway_provider: timeout",
                "enrichment": {n: {"x": 1} for n in ALL_PROVIDERS},
            },
        )

        await service.enrich(property_id)

        # Highway failed last time; drive times depend on settings nobody recorded
        assert _ran(orchestrator) == ["highway_provider", "distance_provider"]

    @pytest.mark.asyncio
    async def test_failed_provider_keeps_previous_data(self, service, db, orchestrator):
        property_id, _ = service.create_from_input("1 Main")
        await service.enrich(property_id)

        orchestrator.enrich.return_value = _result(
            walk_score_provider={"success": False, "data": None, "error": "quota"},
            highway_provider=_ok({"highway_distance_m": 500}),
        )
        await service.enrich(property_id)

        prop = db.get_property(property_id)
        assert prop["enrichment"] == {
            "walk_score_provider": {"walk_score": 45},
            "highway_provider": {"highway_distance_m": 500},
        }
        assert prop["status"] == PropertyStatus.ENRICHED
        assert prop["error"] == "walk_score_provider: quota"

    @pytest.mark.asyncio
    async def test_failure_sets_error_status(self, service, db, orchestrator):
        orchestrator.enrich.side_effect = RuntimeError("walkscore down")
        property_id, _ = service.create_from_input("1 Main")

        assert await service.enrich(property_id) is True

        prop = db.get_property(property_id)
        assert prop["status"] == PropertyStatus.ERROR
        assert prop["error"] == "walkscore down"

    @pytest.mark.asyncio
    async def test_hand_edited_facts_survive_enrichment(self, service, db):
        property_id, _ = service.create_from_input("1 Main")
        db.update_property(property_id, {"price": 300000, "beds": 2})

        await service.enrich(property_id)

        prop = db.get_property(property_id)
        assert (prop["price"], prop["beds"]) == (300000, 2)

    @pytest.mark.asyncio
    async def test_missing_property(self, service):
        assert await service.enrich(999) is False

    @pytest.mark.asyncio
    async def test_concurrent_run_is_skipped(self, service):
        property_id, _ = service.create_from_input("1 Main")
        service._in_progress.add(property_id)

        assert await service.enrich(property_id) is False

    @pytest.mark.asyncio
    async def test_enrich_safely_swallows_errors(self, service):
        service.enrich = AsyncMock(side_effect=RuntimeError("boom"))

        await service.enrich_safely(1)


class TestEnrichPending:
    @pytest.mark.asyncio
    async def test_enriches_new_and_interrupted(self, service, db):
        new, _ = service.create_from_input("1 Main")
        interrupted, _ = service.create_from_input("2 Main")
        done, _ = service.create_from_input("3 Main")
        db.update_property(interrupted, {"status": PropertyStatus.ENRICHING})
        db.update_property(done, {"status": PropertyStatus.ENRICHED})

        assert await service.enrich_pending() == 2
        assert db.get_property(new)["status"] == PropertyStatus.ENRICHED
        assert db.get_property(interrupted)["status"] == PropertyStatus.ENRICHED


class TestLoadPreferences:
    @pytest.mark.asyncio
    async def test_reads_settings_and_active_locations(self, service, db, geocoder):
        db.set_setting(AMENITY_TYPES, "grocery_store\n\n park \n")
        db.set_setting(PREFERRED_PLACES, "Costco")
        db.create_location({"name": "Work", "address": "1 Office Rd", "priority": 1})
        db.create_location({"name": "Mom", "address": "2 Home St", "type": "Family", "priority": 5})
        db.create_location({"name": "Old", "address": "3 Rd", "active": 0})

        preferences = await service.load_preferences()

        assert preferences["preferred_amenities"] == ["grocery_store", "park"]
        assert preferences["preferred_places"] == ["Costco"]
        locations = preferences["custom_locations"]
        assert [loc.name for loc in locations] == ["Mom", "Work"]
        assert locations[0].location_type == "Family"
        assert locations[0].latitude == 29.1
        assert geocoder.geocode_address.await_count == 2

    @pytest.mark.asyncio
    async def test_locations_are_geocoded_once(self, service, db, geocoder):
        location_id = db.create_location({"name": "Mom", "address": "2 Home St"})

        await service.load_preferences()
        preferences = await service.load_preferences()

        geocoder.geocode_address.assert_awaited_once_with("2 Home St")
        [mom] = preferences["custom_locations"]
        assert (mom.latitude, mom.longitude, mom.city, mom.state) == (
            29.1,
            -81.0,
            "Port Orange",
            "FL",
        )

        # A new address is looked up again; other edits aren't
        db.update_location(location_id, {"name": "Mum", "address": "2 Home St"})
        await service.load_preferences()
        assert geocoder.geocode_address.await_count == 1
        db.update_location(location_id, {"address": "5 New Rd"})
        await service.load_preferences()
        assert geocoder.geocode_address.await_count == 2

    @pytest.mark.asyncio
    async def test_skips_locations_that_fail_to_geocode(self, service, db, geocoder):
        geocoder.geocode_address.side_effect = ValueError("bad address")
        db.create_location({"name": "Mom", "address": "??"})

        preferences = await service.load_preferences()

        assert preferences["custom_locations"] == []
