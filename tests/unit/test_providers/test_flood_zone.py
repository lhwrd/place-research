from unittest.mock import AsyncMock, patch

import pytest

from app.services.enrichment.base_provider import ProviderCategory, ProviderResult
from app.services.enrichment.providers.flood_zone import FloodZoneProvider


@pytest.fixture
def flood_zone_provider():
    """Fixture to create a FloodZoneProvider instance."""
    return FloodZoneProvider()


@pytest.fixture
def mock_api_client():
    """Fixture to create a mock API client."""
    with patch("app.services.enrichment.providers.flood_zone.FloodZoneAPIClient") as mock:
        yield mock.return_value


class TestFloodZoneProvider:
    """Test suite for FloodZoneProvider."""

    def test_metadata(self, flood_zone_provider):
        """Test provider metadata is correctly set."""
        metadata = flood_zone_provider.metadata

        assert metadata.name == "flood_zone_provider"
        assert metadata.category == ProviderCategory.ENVIRONMENTAL
        assert metadata.enabled is True
        assert metadata.version == "1.0.0"
        assert metadata.requires_api_key is True
        assert metadata.cost_per_call == 0.002

    @pytest.mark.asyncio
    async def test_enrich_success(self, flood_zone_provider, mock_api_client):
        """Test successful enrichment with flood zone data."""
        # Arrange
        flood_zone_provider.api_client = mock_api_client
        expected_data = {
            "flood_zone": "X",
            "risk_level": "low",
            "fema_designation": "Area of Minimal Flood Hazard",
        }
        mock_api_client.fetch_flood_zone_data = AsyncMock(return_value=expected_data)

        # Act
        result = await flood_zone_provider.enrich(
            latitude=37.7749,
            longitude=-122.4194,
            address="123 Main St, San Francisco, CA",
        )

        # Assert
        assert isinstance(result, ProviderResult)
        assert result.provider_name == "flood_zone_provider"
        assert result.success is True
        assert result.data == expected_data
        assert result.api_calls_made == 1
        assert result.error_message is None

    @pytest.mark.asyncio
    async def test_enrich_value_error(self, flood_zone_provider, mock_api_client):
        """Test enrichment handles ValueError."""
        # Arrange
        flood_zone_provider.api_client = mock_api_client
        mock_api_client.fetch_flood_zone_data = AsyncMock(
            side_effect=ValueError("Invalid coordinates")
        )

        # Act
        result = await flood_zone_provider.enrich(
            latitude=37.7749,
            longitude=-122.4194,
            address="123 Main St, San Francisco, CA",
        )

        # Assert
        assert result.success is False
        assert result.data == {}
        assert result.error_message == "Invalid coordinates"
        assert result.api_calls_made == 1

    @pytest.mark.asyncio
    async def test_enrich_connection_error(self, flood_zone_provider, mock_api_client):
        """Test enrichment handles ConnectionError."""
        # Arrange
        flood_zone_provider.api_client = mock_api_client
        mock_api_client.fetch_flood_zone_data = AsyncMock(
            side_effect=ConnectionError("API connection failed")
        )

        # Act
        result = await flood_zone_provider.enrich(
            latitude=37.7749,
            longitude=-122.4194,
            address="123 Main St, San Francisco, CA",
        )

        # Assert
        assert result.success is False
        assert result.error_message == "API connection failed"

    @pytest.mark.asyncio
    async def test_enrich_timeout_error(self, flood_zone_provider, mock_api_client):
        """Test enrichment handles TimeoutError."""
        # Arrange
        flood_zone_provider.api_client = mock_api_client
        mock_api_client.fetch_flood_zone_data = AsyncMock(
            side_effect=TimeoutError("Request timed out")
        )

        # Act
        result = await flood_zone_provider.enrich(
            latitude=37.7749,
            longitude=-122.4194,
            address="123 Main St, San Francisco, CA",
        )

        # Assert
        assert result.success is False
        assert result.error_message == "Request timed out"

    @pytest.mark.asyncio
    async def test_enrich_with_optional_params(self, flood_zone_provider, mock_api_client):
        """Test enrichment with optional property_data and user_preferences."""
        # Arrange
        flood_zone_provider.api_client = mock_api_client
        expected_data = {"flood_zone": "AE"}
        mock_api_client.fetch_flood_zone_data = AsyncMock(return_value=expected_data)

        property_data = {"parcel_id": "12345"}
        user_preferences = {"detailed_report": True}

        # Act
        result = await flood_zone_provider.enrich(
            latitude=37.7749,
            longitude=-122.4194,
            address="123 Main St, San Francisco, CA",
            property_data=property_data,
            user_preferences=user_preferences,
        )

        # Assert
        assert result.success is True
        assert result.data == expected_data

    @pytest.mark.asyncio
    async def test_validate_config_success(self, flood_zone_provider, mock_api_client):
        """Test successful config validation."""
        # Arrange
        flood_zone_provider.api_client = mock_api_client
        mock_api_client.validate_api_key = AsyncMock(return_value=True)

        # Act
        is_valid = await flood_zone_provider.validate_config()

        # Assert
        assert is_valid is True

    @pytest.mark.asyncio
    async def test_validate_config_failure(self, flood_zone_provider, mock_api_client):
        """Test failed config validation."""
        # Arrange
        flood_zone_provider.api_client = mock_api_client
        mock_api_client.validate_api_key = AsyncMock(return_value=False)

        # Act
        is_valid = await flood_zone_provider.validate_config()

        # Assert
        assert is_valid is False
