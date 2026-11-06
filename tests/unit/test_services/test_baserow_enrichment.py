"""Tests for the Baserow ingest and enrichment service."""

from unittest.mock import AsyncMock, Mock

import pytest

from app.core.config import settings
from app.integrations.baserow_schema import LocationFields, PropertyFields, SettingsFields, Status
from app.services.baserow_enrichment import (
    BaserowEnrichmentService,
    ImageUpload,
    RowNotFoundError,
    needs_enrichment,
)
from tests.fakes import STATUS_OPTION_IDS, FakeBaserowAPI

PROPS = settings.baserow_properties_table_id
LOCATIONS = settings.baserow_locations_table_id
SETTINGS = settings.baserow_settings_table_id
URL = "https://www.zillow.com/homedetails/111-White-Pl-Port-Orange-FL-32127/46284123_zpid/"
LISTING_JSON = {
    "property": {
        "zpid": 46284123,
        "price": 425000,
        "bedrooms": 3,
        "address": {
            "streetAddress": "111 White Pl",
            "city": "Port Orange",
            "state": "FL",
            "zipcode": "32127",
        },
    }
}
ENRICHMENT = {
    "enrichment_data": {
        "walk_score_provider": {"success": True, "data": {"walk_score": 45}},
    }
}


def _status(value):
    return {"id": STATUS_OPTION_IDS[value], "value": value}


@pytest.fixture
def baserow():
    return FakeBaserowAPI()


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
    orchestrator.enrich = AsyncMock(return_value=ENRICHMENT)
    return orchestrator


@pytest.fixture
def service(baserow, geocoder, orchestrator):
    return BaserowEnrichmentService(client=baserow, geocoder=geocoder, orchestrator=orchestrator)


class TestCreateListing:
    @pytest.mark.asyncio
    async def test_creates_row_with_listing_facts(self, service, baserow):
        row_id, created = await service.create_listing(URL, LISTING_JSON)

        row = baserow.row(PROPS, row_id)
        assert created is True
        assert row[PropertyFields.ADDRESS] == "111 White Pl, Port Orange, FL 32127"
        assert row[PropertyFields.ZILLOW_ID] == "46284123"
        assert row[PropertyFields.ZILLOW_URL] == URL
        assert row[PropertyFields.PRICE] == 425000
        assert row[PropertyFields.STATUS]["value"] == Status.NEW
        assert '"zpid": 46284123' in row[PropertyFields.LISTING_JSON]

    @pytest.mark.asyncio
    async def test_falls_back_to_url_slug_address(self, service, baserow):
        row_id, _ = await service.create_listing(URL)

        row = baserow.row(PROPS, row_id)
        assert row[PropertyFields.ADDRESS] == "111 White Pl Port Orange, FL 32127"
        assert PropertyFields.LISTING_JSON not in row

    @pytest.mark.asyncio
    async def test_resharing_returns_existing_row(self, service, baserow):
        first_id, _ = await service.create_listing(URL, LISTING_JSON)
        second_id, created = await service.create_listing(URL + "?utm=share")

        assert (second_id, created) == (first_id, False)
        assert len(baserow.tables[PROPS]) == 1


class TestAddImages:
    @pytest.mark.asyncio
    async def test_appends_to_existing_photos(self, service, baserow):
        row = baserow.add_row(PROPS, {PropertyFields.PHOTOS: [{"name": "old.jpg", "url": "x"}]})

        count = await service.add_images(
            row["id"],
            [ImageUpload(b"a", "1.jpg", "image/jpeg"), ImageUpload(b"b", "2.png", "image/png")],
        )

        assert count == 3
        assert baserow.row(PROPS, row["id"])[PropertyFields.PHOTOS] == [
            {"name": "old.jpg"},
            {"name": "stored_0_1.jpg"},
            {"name": "stored_1_2.png"},
        ]

    @pytest.mark.asyncio
    async def test_missing_row(self, service):
        with pytest.raises(RowNotFoundError):
            await service.add_images(999, [ImageUpload(b"a", "1.jpg", "image/jpeg")])


class TestEnrichRow:
    @pytest.mark.asyncio
    async def test_enriches_new_row(self, service, baserow, orchestrator, geocoder):
        row = baserow.add_row(
            PROPS, {PropertyFields.ADDRESS: "111 White Pl", PropertyFields.STATUS: _status("New")}
        )

        assert await service.enrich_row(row["id"]) is True

        stored = baserow.row(PROPS, row["id"])
        assert stored[PropertyFields.STATUS]["value"] == Status.ENRICHED
        assert stored[PropertyFields.WALK_SCORE] == 45
        assert stored[PropertyFields.LATITUDE] == 29.1
        assert stored[PropertyFields.ERROR] == ""
        assert [u[1][PropertyFields.STATUS] for u in baserow.updates] == [
            STATUS_OPTION_IDS[Status.ENRICHING],
            STATUS_OPTION_IDS[Status.ENRICHED],
        ]
        geocoder.geocode_address.assert_awaited_once_with("111 White Pl")
        assert orchestrator.enrich.call_args.kwargs["use_cached"] is True

    @pytest.mark.asyncio
    async def test_uses_listing_coordinates_and_facts(self, service, baserow, geocoder):
        listing = {"property": {**LISTING_JSON["property"], "latitude": 29.5, "longitude": -81.5}}
        row_id, _ = await service.create_listing(URL, listing)

        await service.enrich_row(row_id)

        geocoder.geocode_address.assert_not_called()
        assert baserow.row(PROPS, row_id)[PropertyFields.LATITUDE] == 29.5

    @pytest.mark.asyncio
    async def test_re_enrich_bypasses_cache(self, service, baserow, orchestrator):
        row = baserow.add_row(
            PROPS, {PropertyFields.ADDRESS: "1 Main", PropertyFields.STATUS: _status("Re-enrich")}
        )

        await service.enrich_row(row["id"])

        assert orchestrator.enrich.call_args.kwargs["use_cached"] is False

    @pytest.mark.asyncio
    async def test_row_without_status_is_enriched(self, service, baserow):
        row = baserow.add_row(
            PROPS, {PropertyFields.ADDRESS: "1 Main", PropertyFields.STATUS: None}
        )

        assert await service.enrich_row(row["id"]) is True

    @pytest.mark.parametrize("status", [Status.ENRICHING, Status.ENRICHED, Status.ERROR])
    @pytest.mark.asyncio
    async def test_skips_rows_not_asking_for_enrichment(self, service, baserow, status):
        row = baserow.add_row(
            PROPS, {PropertyFields.ADDRESS: "1 Main", PropertyFields.STATUS: _status(status)}
        )

        assert await service.enrich_row(row["id"]) is False
        assert baserow.updates == []

    @pytest.mark.asyncio
    async def test_failure_sets_error_status(self, service, baserow, orchestrator):
        orchestrator.enrich.side_effect = RuntimeError("walkscore down")
        row = baserow.add_row(
            PROPS, {PropertyFields.ADDRESS: "1 Main", PropertyFields.STATUS: _status("New")}
        )

        assert await service.enrich_row(row["id"]) is True

        stored = baserow.row(PROPS, row["id"])
        assert stored[PropertyFields.STATUS]["value"] == Status.ERROR
        assert stored[PropertyFields.ERROR] == "walkscore down"

    @pytest.mark.asyncio
    async def test_missing_address_sets_error(self, service, baserow):
        row = baserow.add_row(PROPS, {PropertyFields.STATUS: _status("New")})

        await service.enrich_row(row["id"])

        assert baserow.row(PROPS, row["id"])[PropertyFields.STATUS]["value"] == Status.ERROR

    @pytest.mark.asyncio
    async def test_concurrent_run_is_skipped(self, service, baserow):
        row = baserow.add_row(
            PROPS, {PropertyFields.ADDRESS: "1 Main", PropertyFields.STATUS: _status("New")}
        )
        service._in_progress.add(row["id"])

        assert await service.enrich_row(row["id"]) is False


class TestSweep:
    @pytest.mark.asyncio
    async def test_enriches_only_actionable_rows(self, service, baserow):
        for status in (_status("New"), _status("Enriched"), _status("Re-enrich"), None):
            baserow.add_row(
                PROPS, {PropertyFields.ADDRESS: "1 Main", PropertyFields.STATUS: status}
            )

        assert await service.sweep() == 3


class TestLoadPreferences:
    @pytest.mark.asyncio
    async def test_reads_settings_and_active_locations(self, service, baserow, geocoder):
        baserow.add_row(
            SETTINGS,
            {
                SettingsFields.AMENITY_TYPES: "grocery_store\n\n park \n",
                SettingsFields.PREFERRED_PLACES: "Costco",
            },
        )
        baserow.add_row(
            LOCATIONS,
            {
                LocationFields.NAME: "Work",
                LocationFields.ADDRESS: "1 Office Rd",
                LocationFields.ACTIVE: True,
                LocationFields.PRIORITY: 1,
            },
        )
        baserow.add_row(
            LOCATIONS,
            {
                LocationFields.NAME: "Mom",
                LocationFields.ADDRESS: "2 Home St",
                LocationFields.TYPE: {"id": 1, "value": "Family"},
                LocationFields.ACTIVE: True,
                LocationFields.PRIORITY: 5,
            },
        )
        baserow.add_row(
            LOCATIONS,
            {
                LocationFields.NAME: "Old",
                LocationFields.ADDRESS: "3 Rd",
                LocationFields.ACTIVE: False,
            },
        )

        preferences = await service.load_preferences()

        assert preferences["preferred_amenities"] == ["grocery_store", "park"]
        assert preferences["preferred_places"] == ["Costco"]
        locations = preferences["custom_locations"]
        assert [loc.name for loc in locations] == ["Mom", "Work"]
        assert locations[0].location_type == "Family"
        assert locations[0].latitude == 29.1
        assert geocoder.geocode_address.await_count == 2

    @pytest.mark.asyncio
    async def test_skips_locations_that_fail_to_geocode(self, service, baserow, geocoder):
        geocoder.geocode_address.side_effect = ValueError("bad address")
        baserow.add_row(
            LOCATIONS,
            {LocationFields.NAME: "Mom", LocationFields.ADDRESS: "??", LocationFields.ACTIVE: True},
        )

        preferences = await service.load_preferences()

        assert preferences["custom_locations"] == []


@pytest.mark.parametrize(
    "status,expected",
    [(None, True), ("New", True), ("Re-enrich", True), ("Enriched", False), ("Error", False)],
)
def test_needs_enrichment(status, expected):
    assert needs_enrichment(status) is expected
