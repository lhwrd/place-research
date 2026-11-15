from unittest.mock import AsyncMock, patch

import pytest

from app.services.enrichment.base_provider import ProviderCategory
from app.services.enrichment.providers.places_nearby import PlacesNearbyProvider


class TestPlacesNearbyProvider:
    @pytest.fixture
    def provider(self):
        with (
            patch("app.services.enrichment.providers.places_nearby.GooglePlacesAPI"),
            patch("app.services.enrichment.providers.places_nearby.GoogleMapsAPI"),
        ):
            provider = PlacesNearbyProvider()
        provider.maps_api.distance_matrix = AsyncMock(return_value=[])
        return provider

    def test_metadata(self, provider):
        metadata = provider.metadata
        assert metadata.name == "places_nearby_provider"
        assert metadata.category == ProviderCategory.NEARBY_PLACES
        assert metadata.version == "1.0.0"
        assert metadata.enabled is True
        assert metadata.requires_api_key is True

    @pytest.mark.asyncio
    async def test_enrich_without_preferences(self, provider):
        provider.places_api.nearby_search = AsyncMock(return_value=[])

        result = await provider.enrich(latitude=40.7128, longitude=-74.0060, address="123 Test St")

        assert result.success is True
        assert result.provider_name == "places_nearby_provider"
        provider.places_api.nearby_search.assert_called_once()

    @pytest.mark.asyncio
    async def test_enrich_with_preferences(self, provider):
        mock_place = {
            "name": "Test Coffee Shop",
            "place_id": "abc123",
            "latitude": 40.7130,
            "longitude": -74.0062,
            "address": "456 Coffee Ave",
            "type": "cafe",
        }

        provider.places_api.nearby_search = AsyncMock(return_value=[mock_place])
        provider.places_api.text_search = AsyncMock(return_value=[])

        user_preferences = {"preferred_amenities": ["cafe"], "preferred_places": []}

        result = await provider.enrich(
            latitude=40.7128,
            longitude=-74.0060,
            address="123 Test St",
            user_preferences=user_preferences,
        )

        assert result.success is True
        provider.places_api.nearby_search.assert_called_once_with(
            lat=40.7128,
            lon=-74.0060,
            place_types=["cafe"],
            radius_miles=10.0,
            max_results=3,
        )

    @pytest.mark.asyncio
    async def test_enrich_with_text_queries(self, provider):
        provider.places_api.nearby_search = AsyncMock(return_value=[])
        provider.places_api.text_search = AsyncMock(return_value=[])

        user_preferences = {
            "preferred_amenities": [],
            "preferred_places": ["Starbucks", "Whole Foods"],
        }

        await provider.enrich(
            latitude=40.7128,
            longitude=-74.0060,
            address="123 Test St",
            user_preferences=user_preferences,
        )

        assert provider.places_api.text_search.call_count == 2

    @pytest.mark.asyncio
    async def test_adds_drive_times_and_sorts_by_them(self, provider):
        provider.places_api.nearby_search = AsyncMock(
            return_value=[_place("far", 1), _place("near", 2), _place("no coords", 3, lat=None)]
        )
        provider.places_api.text_search = AsyncMock(
            return_value=[_place("unreachable", 4), _place("near", 2)]  # "near" again
        )
        provider.maps_api.distance_matrix = AsyncMock(
            return_value=[
                {"destination_index": 0, "status": "OK", "duration_minutes": 30,
                 "duration_in_traffic_minutes": 41, "distance_miles": 20.5},
                {"destination_index": 1, "status": "OK", "duration_minutes": 6,
                 "distance_miles": 2.1},
                {"destination_index": 2, "status": "ZERO_RESULTS"},
            ]
        )  # fmt: skip

        result = await provider.enrich(
            40.0, -105.0, "x", user_preferences={"preferred_places": ["Costco"]}
        )

        places = result.data["places_nearby"]
        assert [p["name"] for p in places] == ["near", "far", "no coords", "unreachable"]
        assert (places[0]["drive_minutes"], places[0]["drive_miles"]) == (6, 2.1)
        # Traffic-aware time when available, like the drive times to your locations
        assert (places[1]["drive_minutes"], places[1]["drive_miles"]) == (41, 20.5)
        assert "drive_minutes" not in places[3]
        # Places without coordinates aren't sent to Distance Matrix
        destinations = provider.maps_api.distance_matrix.call_args.kwargs["destinations"]
        assert destinations == [(40.001, -105.0), (40.002, -105.0), (40.004, -105.0)]

    @pytest.mark.asyncio
    async def test_drive_time_failure_keeps_places(self, provider):
        provider.places_api.nearby_search = AsyncMock(return_value=[_place("a", 1)])
        provider.maps_api.distance_matrix = AsyncMock(side_effect=RuntimeError("quota"))

        result = await provider.enrich(40.0, -105.0, "x")

        assert result.success
        assert [p["name"] for p in result.data["places_nearby"]] == ["a"]
        assert "drive_minutes" not in result.data["places_nearby"][0]

    @pytest.mark.asyncio
    async def test_drive_times_batched(self, provider):
        places = [_place(f"p{i}", i) for i in range(30)]
        provider.places_api.nearby_search = AsyncMock(return_value=places)

        async def matrix(origin, destinations, mode):
            return [
                {"destination_index": i, "status": "OK", "duration_minutes": 5, "distance_miles": 1}
                for i in range(len(destinations))
            ]

        provider.maps_api.distance_matrix = AsyncMock(side_effect=matrix)

        result = await provider.enrich(40.0, -105.0, "x")

        sizes = [
            len(c.kwargs["destinations"]) for c in provider.maps_api.distance_matrix.call_args_list
        ]
        assert sizes == [25, 5]
        assert all(p["drive_minutes"] == 5 for p in result.data["places_nearby"])

    @pytest.mark.asyncio
    async def test_validate_config(self, provider):
        provider.places_api.validate_api_key = AsyncMock(return_value=True)

        result = await provider.validate_config()

        assert result is True
        provider.places_api.validate_api_key.assert_called_once()


def _place(name, n, lat=0.0):
    return {
        "name": name,
        "place_id": name,
        "latitude": None if lat is None else 40.0 + n / 1000,
        "longitude": None if lat is None else -105.0,
        "type": "Store",
    }
