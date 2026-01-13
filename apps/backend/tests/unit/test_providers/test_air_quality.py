from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.enrichment.base_provider import ProviderCategory
from app.services.enrichment.providers.air_quality import AirQualityProvider


@pytest.fixture
def air_quality_provider():
    """Fixture to create an AirQualityProvider instance."""
    with patch("app.services.enrichment.providers.air_quality.AirQualityAPIClient"):
        provider = AirQualityProvider()
        return provider


@pytest.fixture
def mock_api_client():
    """Fixture to create a mock API client."""
    return AsyncMock()


class TestAirQualityProvider:
    def test_metadata(self, air_quality_provider):
        """Test that metadata is correctly defined."""
        metadata = air_quality_provider.metadata

        assert metadata.name == "AirQualityProvider"
        assert metadata.category == ProviderCategory.ENVIRONMENTAL
        assert metadata.enabled is True
        assert metadata.description == "Provides air quality data using the AirNow API."
        assert metadata.version == "1.0.0"
        assert metadata.requires_api_key is True
        assert metadata.cost_per_call == 0.0

    @pytest.mark.asyncio
    async def test_enrich_success(self, air_quality_provider, mock_api_client):
        """Test successful enrichment with valid air quality data."""
        air_quality_provider.api_client = mock_api_client
        mock_response = {"aqi": 50, "category": "Good"}
        mock_api_client.get_air_quality.return_value = mock_response

        result = await air_quality_provider.enrich(
            latitude=37.7749, longitude=-122.4194, address="San Francisco, CA"
        )

        assert result.provider_name == "AirQualityProvider"
        assert result.data == mock_response
        assert result.success is True
        assert result.error_message is None
        assert result.api_calls_made == 1
        assert result.cached is False
        mock_api_client.get_air_quality.assert_called_once_with(
            latitude=37.7749, longitude=-122.4194
        )

    @pytest.mark.asyncio
    async def test_enrich_failure(self, air_quality_provider, mock_api_client):
        """Test enrichment when API returns no data."""
        air_quality_provider.api_client = mock_api_client
        mock_api_client.get_air_quality.return_value = None

        result = await air_quality_provider.enrich(
            latitude=37.7749, longitude=-122.4194, address="San Francisco, CA"
        )

        assert result.provider_name == "AirQualityProvider"
        assert result.data is None
        assert result.success is False
        assert result.error_message == "Failed to fetch air quality data"
        assert result.api_calls_made == 1
        assert result.cached is False

    @pytest.mark.asyncio
    async def test_enrich_with_optional_params(self, air_quality_provider, mock_api_client):
        """Test enrichment with optional property_data and user_preferences."""
        air_quality_provider.api_client = mock_api_client
        mock_response = {"aqi": 75, "category": "Moderate"}
        mock_api_client.get_air_quality.return_value = mock_response

        result = await air_quality_provider.enrich(
            latitude=40.7128,
            longitude=-74.0060,
            address="New York, NY",
            property_data={"type": "residential"},
            user_preferences={"notify": True},
        )

        assert result.success is True
        assert result.data == mock_response

    @pytest.mark.asyncio
    async def test_validate_config_valid(self, air_quality_provider, mock_api_client):
        """Test config validation when API key is valid."""
        air_quality_provider.api_client = mock_api_client
        mock_api_client.validate_api_key.return_value = True

        is_valid = await air_quality_provider.validate_config()

        assert is_valid is True
        mock_api_client.validate_api_key.assert_called_once()

    @pytest.mark.asyncio
    async def test_validate_config_invalid(self, air_quality_provider, mock_api_client):
        """Test config validation when API key is invalid."""
        air_quality_provider.api_client = mock_api_client
        mock_api_client.validate_api_key.return_value = False

        is_valid = await air_quality_provider.validate_config()

        assert is_valid is False
        mock_api_client.validate_api_key.assert_called_once()
