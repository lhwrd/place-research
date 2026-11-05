from unittest.mock import AsyncMock, patch

import pytest

from app.services.enrichment.base_provider import ProviderCategory
from app.services.enrichment.providers.places_nearby import PlacesNearbyProvider


class TestPlacesNearbyProvider:
    @pytest.fixture
    def provider(self):
        with patch("app.services.enrichment.providers.places_nearby.GooglePlacesAPI"):
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
    async def test_validate_config(self, provider):
        provider.places_api.validate_api_key = AsyncMock(return_value=True)

        result = await provider.validate_config()

        assert result is True
        provider.places_api.validate_api_key.assert_called_once()
