"""Tests for the emergency room, sirens and industrial neighbors providers."""

from unittest.mock import AsyncMock, patch

import httpx
import pandas as pd
import pytest
from shapely.geometry import Point, box

from app.services.enrichment.providers.emergency_room import (
    MAX_ERS,
    EmergencyRoomProvider,
    emergency_rooms,
    is_emergency_room,
)
from app.services.enrichment.providers.industrial_neighbors import (
    IndustrialNeighborsProvider,
    industrial_parcels,
)
from app.services.enrichment.providers.sirens import SirensProvider, is_firehouse

LAT, LON = 28.55, -81.37
# ~1 m of latitude, in degrees
M = 1 / 110_950
MILE = 1609.344


def _at(miles):
    return {"latitude": LAT + miles * MILE * M, "longitude": LON}


class TestEmergencyRoom:
    @pytest.fixture
    def provider(self):
        with (
            patch("app.services.enrichment.providers.emergency_room.GooglePlacesAPI"),
            patch("app.services.enrichment.providers.emergency_room.GoogleMapsAPI"),
        ):
            return EmergencyRoomProvider()

    @pytest.mark.parametrize(
        "name, open_24_hours, expected",
        [
            ("Orlando Health Orlando Regional Medical Center", True, True),
            ("HCA Florida Baldwin Park Emergency", True, True),
            ("AdventHealth Millenia ER", None, True),  # no hours, but named an ER
            ("Orlando Health ER & Medical Pavilion", True, True),
            ("Orlando Health Medical Pavilion", None, False),  # no hours, not an ER
            ("CareSpot Urgent Care of Orlando", False, False),
            ("GuideWell Emergency Doctors", False, False),
            ("Emergency Physicians Central Fl", None, False),
            ("Emergency Department Parking Lot - ORMC", True, False),
            ("Orlando Health Children's Arnold Palmer Hospital Emergency", True, False),
            ("VEG ER for Pets", True, False),
            ("Some 24 Hour Gym", True, False),
        ],
    )
    def test_what_counts_as_an_er(self, name, open_24_hours, expected):
        place = {"name": name}
        if open_24_hours is not None:
            place["open_24_hours"] = open_24_hours
        assert is_emergency_room(place) is expected

    def test_one_per_hospital_and_nearest_few(self):
        found = [
            {"name": "ORMC Hospital", "open_24_hours": True, **_at(1)},
            {"name": "ORMC Emergency", "open_24_hours": True, **_at(1.05)},  # same campus
            *({"name": f"Hospital {i}", "open_24_hours": True, **_at(i + 2)} for i in range(5)),
            {"name": "Closed ER", "business_status": "CLOSED_PERMANENTLY", **_at(0.1)},
        ]

        ers = emergency_rooms(LAT, LON, found)

        assert [e["name"] for e in ers] == ["ORMC Hospital", "Hospital 0", "Hospital 1"]
        assert len(ers) == MAX_ERS

    @pytest.mark.asyncio
    async def test_sorts_by_drive_time(self, provider):
        provider.places_api.text_search = AsyncMock(
            return_value=[
                {"name": "Across Town Hospital", "open_24_hours": True, **_at(2)},
                {"name": "Highway ER", "open_24_hours": True, **_at(4)},
            ]
        )
        provider.maps_api.distance_matrix = AsyncMock(
            return_value=[
                {"destination_index": 0, "status": "OK", "duration_minutes": 18},
                {"destination_index": 1, "status": "OK", "duration_minutes": 9},
            ]
        )

        result = await provider.enrich(LAT, LON, "x")

        assert result.success and result.api_calls_made == 2
        assert [e["name"] for e in result.data["ers"]] == ["Highway ER", "Across Town Hospital"]
        search = provider.places_api.text_search.call_args.kwargs
        assert search["opening_hours"] is True and search["nearest_first"] is True

    @pytest.mark.asyncio
    async def test_none_in_range(self, provider):
        provider.places_api.text_search = AsyncMock(return_value=[])
        provider.maps_api.distance_matrix = AsyncMock()

        result = await provider.enrich(LAT, LON, "x")

        assert result.success and result.data["ers"] == []
        provider.maps_api.distance_matrix.assert_not_called()


class TestSirens:
    @pytest.fixture
    def provider(self):
        heliports = pd.DataFrame(
            [
                {"name": "Far Heliport", "category": "other", **_at(1.5)},
                {"name": "ORMC Heliport", "category": "hospital", **_at(0.3)},
            ]
        )
        with patch("app.services.enrichment.providers.sirens.GooglePlacesAPI"):
            return SirensProvider(heliports=heliports)

    @pytest.mark.asyncio
    async def test_fire_stations_and_heliports_within_a_mile(self, provider):
        provider.places_api.nearby_search = AsyncMock(
            return_value=[
                {"name": "Station 7", **_at(0.6)},
                {"name": "Station 1", **_at(0.2)},
                {"name": "Fire Records Office", **_at(0.1)},
            ]
        )

        result = await provider.enrich(LAT, LON, "x")

        assert result.success and result.api_calls_made == 1
        assert [s["name"] for s in result.data["fire_stations"]] == ["Station 1", "Station 7"]
        assert [(h["name"], h["category"]) for h in result.data["heliports"]] == [
            ("ORMC Heliport", "hospital")
        ]
        search = provider.places_api.nearby_search.call_args.kwargs
        assert search["place_types"] == ["fire_station"] and search["nearest_first"] is True

    @pytest.mark.parametrize(
        "name, expected",
        [
            ("Orlando Fire Station 5", True),
            ("Orange County Fire Rescue Station 51", True),
            ("Winter Park Fire-Rescue Department", True),
            ("Orlando Fire Reports/Records", False),
            ("Fire Lawsuits", False),
            ("Orlando Fire Department Headquarters", False),
        ],
    )
    def test_what_counts_as_a_firehouse(self, name, expected):
        assert is_firehouse(name) is expected

    @pytest.mark.asyncio
    async def test_search_failure(self, provider):
        provider.places_api.nearby_search = AsyncMock(side_effect=RuntimeError("quota"))
        result = await provider.enrich(LAT, LON, "x")
        assert not result.success

    def test_bundled_heliports(self):
        with patch("app.services.enrichment.providers.sirens.GooglePlacesAPI"):
            provider = SirensProvider()
        # Orlando Regional Medical Center's pad, from a block away
        names = [h["name"] for h in provider.heliports_near(28.5262, -81.3772)]
        assert "Orlando Regional Medical Center Heliport" in names


class TestIndustrialNeighbors:
    @staticmethod
    def _parcel(code, meters_north, sqft=None, address="1 Industrial Way"):
        lat = LAT + meters_north * M
        return {"DOR_UC": code, "PHY_ADDR1": address, "OWN_NAME": "ACME LLC",
                "TOT_LVG_AR": sqft, "geometry": box(LON - 0.0001, lat, LON + 0.0001,
                                                    lat + 0.0005)}  # fmt: skip

    def test_measures_and_labels(self):
        found = [
            self._parcel("048", 300, sqft=348830),
            self._parcel("042", 80),
            self._parcel("048", 500),  # past a quarter mile: in the square, not the circle
            # The property's own parcel
            {**self._parcel("041", 0), "geometry": Point(LON, LAT).buffer(0.0002)},
            self._parcel("001", 10),  # residential
        ]

        parcels = industrial_parcels(LAT, LON, found)

        assert [(p["use_code"], p["kind"]) for p in parcels] == [
            ("042", "heavy"),
            ("048", "warehouse"),
        ]
        assert parcels[0]["distance_m"] == pytest.approx(80, abs=2)
        assert parcels[1]["building_sqft"] == 348830

    @pytest.mark.asyncio
    async def test_queries_industrial_codes_only(self):
        provider = IndustrialNeighborsProvider()
        provider.api_client.query_box = AsyncMock(return_value=[self._parcel("049", 50)])

        result = await provider.enrich(LAT, LON, "x")

        assert result.success
        assert result.data["parcels"][0]["use"].startswith("Open storage")
        assert result.data["radius_m"] == round(MILE / 4)
        where = provider.api_client.query_box.call_args.kwargs["where"]
        assert where.startswith("DOR_UC IN ('040', '041'") and "'049'" in where

    @pytest.mark.asyncio
    async def test_layer_failure(self):
        provider = IndustrialNeighborsProvider()
        provider.api_client.query_box = AsyncMock(side_effect=httpx.ConnectError("down"))
        result = await provider.enrich(LAT, LON, "x")
        assert not result.success
