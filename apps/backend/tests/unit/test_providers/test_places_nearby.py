from unittest.mock import AsyncMock, patch

import pytest

from app.services.enrichment.base_provider import ProviderCategory
from app.services.enrichment.providers.places_nearby import (
    PlacesNearbyProvider,
    categorize_distance,
    categorize_duration,
)


class TestCategorizeDistance:
    def test_very_close(self):
        assert categorize_distance(1.5) == "Very Close"
        assert categorize_distance(0) == "Very Close"

    def test_close(self):
        assert categorize_distance(2) == "Close"
        assert categorize_distance(4.9) == "Close"

    def test_far(self):
        assert categorize_distance(5) == "Far"
        assert categorize_distance(9.9) == "Far"

    def test_very_far(self):
        assert categorize_distance(10) == "Very Far"
        assert categorize_distance(50) == "Very Far"

    def test_none(self):
        assert categorize_distance(None) == "Unknown"


class TestCategorizeDuration:
    def test_very_quick(self):
        assert categorize_duration(5) == "Very Quick"
        assert categorize_duration(0) == "Very Quick"

    def test_quick(self):
        assert categorize_duration(7) == "Quick"
        assert categorize_duration(14.9) == "Quick"

    def test_slow(self):
        assert categorize_duration(15) == "Slow"
        assert categorize_duration(29.9) == "Slow"

    def test_very_slow(self):
        assert categorize_duration(30) == "Very Slow"
        assert categorize_duration(100) == "Very Slow"

    def test_none(self):
        assert categorize_duration(None) == "Unknown"


class TestPlacesNearbyProvider:
    @pytest.fixture
    def provider(self):
        with patch("app.services.enrichment.providers.places_nearby.GooglePlacesAPI"), patch(
            "app.services.enrichment.providers.places_nearby.DistanceService"
        ):
            return PlacesNearbyProvider()

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
        provider.distance_service.calculate_distances = AsyncMock(return_value=[])

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
        provider.distance_service.calculate_distances = AsyncMock(
            return_value=[{"distance_miles": 1.5, "duration_minutes": 10}]
        )

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
        provider.distance_service.calculate_distances = AsyncMock(return_value=[])

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
    async def test_validate_config(self, provider):
        provider.places_api.validate_api_key = AsyncMock(return_value=True)

        result = await provider.validate_config()

        assert result is True
        provider.places_api.validate_api_key.assert_called_once()
