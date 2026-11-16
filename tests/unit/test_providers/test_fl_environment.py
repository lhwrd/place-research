"""Tests for the Florida hazard and environment providers (ArcGIS calls mocked)."""

from unittest.mock import AsyncMock

import httpx
import pytest
from shapely.geometry import Point, box

from app.services.enrichment.providers.contamination import ContaminationProvider
from app.services.enrichment.providers.elevation import ElevationProvider, compare, ring
from app.services.enrichment.providers.evacuation_zone import EvacuationZoneProvider
from app.services.enrichment.providers.impaired_waters import (
    ImpairedWatersProvider,
    group_by_waterbody,
)
from app.services.enrichment.providers.local_noise_sources import LocalNoiseSourcesProvider
from app.services.enrichment.providers.sinkholes import (
    SinkholeProvider,
    favorability_class,
    summarize_incidents,
)
from app.services.enrichment.providers.wetlands import WetlandsProvider
from app.utils.distance_calculator import geometry_distance_m, haversine_distance

LAT, LON = 28.55, -81.77
# ~1 m of latitude, in degrees
M = 1 / 110_950


def _with_client(provider, **methods):
    for name, mock in methods.items():
        setattr(provider.api_client, name, mock)
    return provider


class TestGeometryDistance:
    def test_matches_haversine_for_points(self):
        other = (LAT + 0.004, LON + 0.003)
        assert geometry_distance_m(LAT, LON, Point(other[1], other[0])) == pytest.approx(
            haversine_distance(LAT, LON, *other), rel=0.005
        )

    def test_inside_polygon_is_zero(self):
        assert (
            geometry_distance_m(LAT, LON, box(LON - 0.01, LAT - 0.01, LON + 0.01, LAT + 0.01)) == 0
        )


class TestSinkholes:
    @pytest.mark.parametrize(
        "value,expected",
        [(1, "Least favorable"), (7, "Least favorable"), (8, "Favorable"), (11, "More favorable"),
         (14, "Most favorable"), (None, None)],
    )  # fmt: skip
    def test_favorability_classes(self, value, expected):
        assert favorability_class(value) == expected

    def test_summarize_incidents(self):
        incidents = [
            {"LATDD": LAT + 1200 * M, "LONGDD": LON, "TRUE_SINK": "Y", "EVENT_DATE": 0},
            {"LATDD": LAT + 300 * M, "LONGDD": LON, "TRUE_SINK": "U",
             "EVENT_DATE": 1_230_768_000_000},  # 2009-01-01
            {"LATDD": None, "LONGDD": None},
        ]  # fmt: skip

        summary = summarize_incidents(LAT, LON, incidents)

        assert summary["incidents_within_1mi"] == 2
        assert summary["incidents_within_half_mi"] == 1
        assert summary["verified_within_1mi"] == 1
        assert summary["nearest_incident_m"] == pytest.approx(300, abs=3)
        assert summary["nearest_incident_year"] == 2009

    def test_pre_1970_event_year(self):
        incidents = [{"LATDD": LAT, "LONGDD": LON, "EVENT_DATE": -69_465_600_000}]
        assert summarize_incidents(LAT, LON, incidents)["nearest_incident_year"] == 1967

    @pytest.mark.asyncio
    async def test_enrich(self):
        provider = _with_client(
            SinkholeProvider(),
            sample=AsyncMock(return_value=13.0),
            query_near=AsyncMock(return_value=[]),
        )

        result = await provider.enrich(LAT, LON, "x")

        assert result.success
        assert result.data["favorability"] == "Most favorable"
        assert result.data["favorability_value"] == 13
        assert result.data["incidents_within_1mi"] == 0
        assert result.data["nearest_incident_m"] is None

    @pytest.mark.asyncio
    async def test_service_error(self):
        provider = _with_client(
            SinkholeProvider(),
            sample=AsyncMock(side_effect=httpx.ConnectError("down")),
            query_near=AsyncMock(return_value=[]),
        )

        result = await provider.enrich(LAT, LON, "x")

        assert not result.success
        assert "down" in result.error_message


class TestContamination:
    @pytest.mark.asyncio
    async def test_nearest_first_with_counts(self):
        features = [
            {"BUSINESS_NAME": "Far Gas ", "CLCC_CLEANUP_CATEGORY_KEY": "PETRO",
             "RSC2_REMEDIATION_STATUS_KEY": "ACTIVE", "geometry": Point(LON, LAT + 700 * M)},
            {"BUSINESS_NAME": "Near Cleaners", "CLCC_CLEANUP_CATEGORY_KEY": "OTHCU",
             "RSC2_REMEDIATION_STATUS_KEY": "OPEN", "geometry": Point(LON, LAT + 150 * M)},
            {"BUSINESS_NAME": "Old Plant", "CLCC_CLEANUP_CATEGORY_KEY": "SUPER",
             "geometry": Point(LON, LAT + 500 * M)},
            {"BUSINESS_NAME": "No location", "geometry": None},
        ]  # fmt: skip
        provider = _with_client(
            ContaminationProvider(), query_near=AsyncMock(return_value=features)
        )

        data = (await provider.enrich(LAT, LON, "x")).data

        assert data["sites_within_half_mi"] == 3
        assert data["sites_within_quarter_mi"] == 1
        assert data["superfund_within_half_mi"] == 1
        assert [s["name"] for s in data["sites"]] == ["Near Cleaners", "Old Plant", "Far Gas"]
        assert data["sites"][0]["category"] == "Hazardous waste / dry cleaner"
        assert data["sites"][0]["status"] == "Open"
        assert data["sites"][0]["distance_m"] == pytest.approx(150, abs=2)


class TestWetlands:
    @pytest.mark.asyncio
    async def test_wetland_and_water_reported_separately(self):
        features = [
            {"WETLAND_TYPE": "Freshwater Pond", "geometry": box(LON, LAT + 50 * M, LON + 0.001, LAT + 0.001)},
            {"WETLAND_TYPE": "Freshwater Emergent Wetland",
             "geometry": box(LON, LAT + 200 * M, LON + 0.001, LAT + 0.01)},
            {"WETLAND_TYPE": "Freshwater Forested/Shrub Wetland",
             "geometry": box(LON, LAT + 400 * M, LON + 0.001, LAT + 0.01)},
        ]  # fmt: skip
        provider = _with_client(WetlandsProvider(), query_near=AsyncMock(return_value=features))

        data = (await provider.enrich(LAT, LON, "x")).data

        assert data["in_wetland"] is False
        assert data["nearest_wetland_type"] == "Freshwater Emergent Wetland"
        assert data["nearest_wetland_m"] == pytest.approx(200, abs=2)
        assert data["nearest_water_type"] == "Freshwater Pond"
        assert data["nearest_water_m"] == pytest.approx(50, abs=1)

    @pytest.mark.asyncio
    async def test_on_a_wetland(self):
        swamp = {"WETLAND_TYPE": "Freshwater Forested/Shrub Wetland",
                 "geometry": box(LON - 0.01, LAT - 0.01, LON + 0.01, LAT + 0.01)}  # fmt: skip
        provider = _with_client(WetlandsProvider(), query_near=AsyncMock(return_value=[swamp]))

        data = (await provider.enrich(LAT, LON, "x")).data

        assert data["in_wetland"] is True
        assert data["nearest_water_m"] is None

    @pytest.mark.asyncio
    async def test_none_nearby(self):
        provider = _with_client(WetlandsProvider(), query_near=AsyncMock(return_value=[]))

        data = (await provider.enrich(LAT, LON, "x")).data

        assert data == {
            "in_wetland": False,
            "nearest_wetland_m": None,
            "nearest_wetland_type": None,
            "nearest_water_m": None,
            "nearest_water_type": None,
        }


class TestImpairedWaters:
    def test_groups_parameters_by_waterbody(self):
        features = [
            {"WATERBODY_NAME": "LAKE EOLA", "WATERBODY_TYPE": "LAKE",
             "PARAMETER_IWR": "Nutrients (Chlorophyll-a)", "ASSESSMENT_STATUS": "Impaired"},
            {"WATERBODY_NAME": "LAKE EOLA", "WATERBODY_TYPE": "LAKE",
             "PARAMETER_IWR": "Nutrients (Total Phosphorus)", "ASSESSMENT_STATUS": "Impaired"},
            {"WATERBODY_NAME": "LAKE EOLA", "WATERBODY_TYPE": "LAKE",
             "PARAMETER_IWR": "Nutrients (Total Phosphorus)", "ASSESSMENT_STATUS": "Impaired"},
            {"WATERBODY_NAME": "LAKE CLEAR", "PARAMETER_IWR": "Mercury",
             "ASSESSMENT_STATUS": "Not impaired"},
        ]  # fmt: skip

        assert group_by_waterbody(features) == [
            {
                "name": "Lake Eola",
                "type": "Lake",
                "parameters": ["Nutrients (Chlorophyll-a)", "Nutrients (Total Phosphorus)"],
            }
        ]

    @pytest.mark.asyncio
    async def test_enrich(self):
        provider = _with_client(ImpairedWatersProvider(), query_near=AsyncMock(return_value=[]))
        result = await provider.enrich(LAT, LON, "x")
        assert result.success
        assert result.data == {"impaired_waters": []}


class TestEvacuationZone:
    @pytest.mark.asyncio
    async def test_earliest_zone_wins_on_overlap(self):
        zones = [
            {"EZone": "B", "County_Nam": "BREVARD", "Edit_Date": "7/17/2013"},
            {"EZone": "A", "County_Nam": "BREVARD", "Edit_Date": "7/17/2013"},
        ]
        provider = _with_client(EvacuationZoneProvider(), query_near=AsyncMock(return_value=zones))

        data = (await provider.enrich(LAT, LON, "x")).data

        assert data == {"evacuation_zone": "A", "county": "Brevard", "zone_edit_date": "7/17/2013"}

    @pytest.mark.asyncio
    async def test_inland(self):
        provider = _with_client(EvacuationZoneProvider(), query_near=AsyncMock(return_value=[]))

        data = (await provider.enrich(LAT, LON, "x")).data

        assert data["evacuation_zone"] is None


class TestElevation:
    def test_ring_is_evenly_spaced_at_radius(self):
        points = ring(LAT, LON)
        assert len(points) == 8
        for lat, lon in points:
            assert haversine_distance(LAT, LON, lat, lon) == pytest.approx(250, rel=0.01)

    def test_compare(self):
        assert compare(80.0, [84.0, 86.0, None, 78.0]) == {
            "elevation_ft": 80.0,
            "surrounding_mean_ft": 82.7,
            "relative_ft": -2.7,
            "lower_than_pct": 67,
        }

    def test_no_elevation(self):
        assert compare(None, [1.0]) == {"elevation_ft": None}

    @pytest.mark.asyncio
    async def test_enrich_converts_meters_to_feet(self):
        provider = _with_client(
            ElevationProvider(), sample_many=AsyncMock(return_value=[10.0] + [11.0] * 8)
        )

        result = await provider.enrich(LAT, LON, "x")

        assert result.success
        assert result.api_calls_made == 1
        assert result.data["elevation_ft"] == pytest.approx(32.8, abs=0.1)
        assert result.data["relative_ft"] == pytest.approx(-3.3, abs=0.1)
        assert result.data["lower_than_pct"] == 100
        points = provider.api_client.sample_many.call_args.args[1]
        assert points[0] == (LAT, LON) and len(points) == 9


class TestLocalNoiseSources:
    @pytest.mark.asyncio
    async def test_near_disney(self):
        data = (await LocalNoiseSourcesProvider().enrich(28.3253, -81.5334, "Celebration")).data

        names = [v["name"] for v in data["fireworks"]]
        assert names[0] == "Disney's Hollywood Studios"
        assert all(v["distance_m"] <= 10 * 1609.344 for v in data["fireworks"])
        # ~60 mi from the Cape: launches heard, but not inside the sonic boom area
        assert data["launch_site"]["name"] == "Kennedy Space Center LC-39A"

    @pytest.mark.asyncio
    async def test_far_away(self):
        data = (await LocalNoiseSourcesProvider().enrich(30.44, -84.28, "Tallahassee")).data
        assert data == {"fireworks": [], "launch_site": None}
