"""Tests for the electric utility, road traffic, event traffic and food & drink providers."""

from unittest.mock import AsyncMock, patch

import httpx
import pytest
from shapely.geometry import LineString

from app.services.enrichment.providers.electric_utility import ElectricUtilityProvider
from app.services.enrichment.providers.event_traffic import EventTrafficProvider
from app.services.enrichment.providers.food_drink import MAX_RESULTS, FoodDrinkProvider
from app.services.enrichment.providers.road_traffic import RoadTrafficProvider

LAT, LON = 28.55, -81.37
# ~1 m of latitude, in degrees
M = 1 / 110_950
MILE = 1609.344


def _arcgis(provider, features):
    provider.api_client.query_near = (
        AsyncMock(side_effect=features)
        if isinstance(features, Exception)
        else AsyncMock(return_value=features)
    )
    return provider


class TestElectricUtility:
    @pytest.mark.asyncio
    async def test_smallest_territory_first_and_paper_territories_dropped(self):
        features = [
            {"NAME": "DUKE ENERGY FLORIDA, LLC", "TYPE": "INVESTOR OWNED", "Shape__Area": 9e10,
             "Res_Electricity_Rate_Nom_2025": 18.3638, "Res_Customer_Count_2025": 1_800_000},
            # Covers the region on the map, serves nine homes
            {"NAME": "REEDY CREEK IMPROVEMENT DIST", "TYPE": "MUNICIPAL", "Shape__Area": 8e9,
             "Res_Electricity_Rate_Nom_2025": 11.4, "Res_Customer_Count_2025": 9},
            {"NAME": "CITY OF WINTER PARK - (FL)", "TYPE": "MUNICIPAL", "Shape__Area": 2e7,
             "Res_Electricity_Rate_Nom_2025": None, "Res_Electricity_Rate_Nom_2024": 13.06,
             "Res_Customer_Count_2024": 12_000},
        ]  # fmt: skip
        provider = _arcgis(ElectricUtilityProvider(), features)

        result = await provider.enrich(LAT, LON, "x")

        assert result.success and result.api_calls_made == 1
        assert result.data["utilities"] == [
            {"name": "CITY OF WINTER PARK", "type": "municipal", "residential_cents_per_kwh": 13.1,
             "rate_year": 2024, "residential_customers": 12_000},
            {"name": "DUKE ENERGY FLORIDA, LLC", "type": "investor-owned",
             "residential_cents_per_kwh": 18.4, "rate_year": 2025,
             "residential_customers": 1_800_000},
        ]  # fmt: skip

    @pytest.mark.asyncio
    async def test_nothing_found_and_api_error(self):
        assert (await _arcgis(ElectricUtilityProvider(), []).enrich(LAT, LON, "x")).data == {
            "utilities": []
        }
        failed = await _arcgis(ElectricUtilityProvider(), httpx.ConnectError("down")).enrich(
            LAT, LON, "x"
        )
        assert failed.success is False and failed.data == {}


class TestRoadTraffic:
    @staticmethod
    def _road(site, north_m, aadt, frm="ORLANDO AVE", to="PARK AVE"):
        """An east-west road north_m meters north of the property."""
        y = LAT + north_m * M
        return {"COSITE": site, "DESC_FRM": frm, "DESC_TO": to, "AADT": aadt, "YEAR_": 2025,
                "geometry": LineString([(LON - 0.01, y), (LON + 0.01, y)])}  # fmt: skip

    @pytest.mark.asyncio
    async def test_nearest_first_one_per_count_station(self):
        features = [
            self._road("758037", 150, 41000, "SR-426/FAIRBANKS AVE", "US-17/US-92"),
            self._road("758271", 20, 7800),
            self._road("758271", 22, 7800, "PARK AVE", "LAKEMONT AVE"),  # same station
            self._road("750001", 60, None),  # not counted this year
            {"COSITE": "x", "AADT": 100, "geometry": None},
        ]
        provider = _arcgis(RoadTrafficProvider(), features)

        result = await provider.enrich(LAT, LON, "x")

        assert result.data["roads"] == [
            {"from_street": "Orlando Ave", "to_street": "Park Ave", "vehicles_per_day": 7800,
             "year": 2025, "distance_m": 20},
            {"from_street": "SR-426/Fairbanks Ave", "to_street": "US-17/US-92",
             "vehicles_per_day": 41000, "year": 2025, "distance_m": 150},
        ]  # fmt: skip

    @pytest.mark.asyncio
    async def test_no_counted_road_and_api_error(self):
        assert (await _arcgis(RoadTrafficProvider(), []).enrich(LAT, LON, "x")).data == {
            "roads": []
        }
        failed = await _arcgis(RoadTrafficProvider(), ValueError("bad query")).enrich(LAT, LON, "x")
        assert failed.success is False and failed.error_message == "bad query"


class TestEventTraffic:
    @pytest.mark.asyncio
    async def test_downtown_orlando_has_venues_but_no_attractions(self):
        data = (await EventTrafficProvider().enrich(28.5412, -81.3668, "x")).data

        assert data["attractions"] == []
        names = [v["name"] for v in data["venues"]]
        assert names[:2] == ["Dr. Phillips Center", "Kia Center"]
        assert "Daytona International Speedway" not in names
        assert all(v["distance_m"] <= 3 * MILE for v in data["venues"])

    @pytest.mark.asyncio
    async def test_attractions_area(self):
        # Between Universal and International Drive
        data = (await EventTrafficProvider().enrich(28.458, -81.468, "x")).data

        assert data["attractions"][0]["distance_m"] < 1.5 * MILE
        assert "Magic Kingdom" not in [a["name"] for a in data["attractions"]]

    @pytest.mark.asyncio
    async def test_far_from_everything(self):
        data = (await EventTrafficProvider().enrich(28.55, -81.77, "x")).data
        assert data == {"attractions": [], "venues": []}


class TestFoodDrink:
    @pytest.fixture
    def provider(self):
        with patch("app.services.enrichment.providers.food_drink.GooglePlacesAPI"):
            return FoodDrinkProvider()

    @staticmethod
    def _place(name, miles):
        return {"name": name, "type": "Restaurant", "latitude": LAT + miles * MILE * M,
                "longitude": LON}  # fmt: skip

    @pytest.mark.asyncio
    async def test_counts_walkable_places(self, provider):
        provider.places_api.nearby_search = AsyncMock(
            return_value=[
                self._place("Far Diner", 1.2),
                self._place("Corner Cafe", 0.1),
                self._place("Wine Bar", 0.45),
                {"name": "No location", "latitude": None, "longitude": None},
            ]
        )

        result = await provider.enrich(LAT, LON, "x")

        assert result.success and result.api_calls_made == 1
        assert [p["name"] for p in result.data["places"]] == [
            "Corner Cafe",
            "Wine Bar",
            "Far Diner",
        ]
        assert result.data["places"][0]["distance_m"] == pytest.approx(0.1 * MILE, abs=3)
        assert (result.data["count"], result.data["walkable_count"]) == (3, 2)
        assert result.data["capped"] is False
        assert result.data["radius_m"] == round(1.5 * MILE)
        search = provider.places_api.nearby_search.call_args.kwargs
        assert search["nearest_first"] is True and search["max_results"] == MAX_RESULTS
        assert search["excluded_types"] == ["fast_food_restaurant"]

    @pytest.mark.asyncio
    async def test_full_page_is_capped(self, provider):
        provider.places_api.nearby_search = AsyncMock(
            return_value=[self._place(f"Place {i}", 0.01 * i) for i in range(MAX_RESULTS)]
        )
        data = (await provider.enrich(LAT, LON, "x")).data
        assert data["capped"] is True and data["walkable_count"] == MAX_RESULTS

    @pytest.mark.asyncio
    async def test_api_error_fails(self, provider):
        provider.places_api.nearby_search = AsyncMock(side_effect=RuntimeError("quota"))
        result = await provider.enrich(LAT, LON, "x")
        assert result.success is False and result.error_message == "quota"
