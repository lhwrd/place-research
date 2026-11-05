from unittest.mock import AsyncMock, patch

import pytest

from app.services.enrichment.base_provider import ProviderCategory
from app.services.enrichment.providers.driving_distance import CustomLocation, DistanceProvider


@pytest.fixture
def distance_provider():
    """Create a DistanceProvider instance with mocked API client."""
    provider = DistanceProvider()
    provider.api_client = AsyncMock()
    return provider


@pytest.fixture
def mock_custom_locations():
    """Create mock custom locations."""
    return [
        CustomLocation(
            id=i + 1,
            name=f"Location {i + 1}",
            location_type="Work" if i == 0 else "Family",
            address=f"{100 + i} Test St",
            city="Test City",
            state="TS",
            latitude=40.0 + i * 0.1,
            longitude=-74.0 + i * 0.1,
            priority=10 - i,
        )
        for i in range(3)
    ]


class TestDistanceProviderMetadata:
    def test_metadata_properties(self, distance_provider):
        """Test provider metadata."""
        metadata = distance_provider.metadata

        assert metadata.name == "distance_provider"
        assert metadata.category == ProviderCategory.DISTANCES
        assert metadata.enabled is True
        assert metadata.requires_api_key is True
        assert metadata.cost_per_call == 0.005
        assert metadata.version == "1.0.0"


class TestDistanceProviderEnrich:
    @pytest.mark.asyncio
    async def test_enrich_without_locations(self, distance_provider):
        """No custom_locations in preferences means nothing to calculate."""
        result = await distance_provider.enrich(
            latitude=40.7128,
            longitude=-74.0060,
            address="123 Test St",
            user_preferences={},
        )

        assert result.success is True
        assert result.data["distances"] == []
        assert result.data["total_locations"] == 0
        assert result.api_calls_made == 0
        distance_provider.api_client.distance_matrix.assert_not_called()

    @pytest.mark.asyncio
    async def test_enrich_with_custom_locations(self, distance_provider, mock_custom_locations):
        """Test successful enrichment with custom locations."""
        distance_provider.api_client.distance_matrix = AsyncMock(
            return_value=[
                {
                    "status": "OK",
                    "distance_miles": 5.2,
                    "distance_meters": 8369,
                    "duration_minutes": 12,
                    "duration_seconds": 720,
                    "duration_in_traffic_minutes": 15,
                },
                {
                    "status": "OK",
                    "distance_miles": 3.1,
                    "distance_meters": 4989,
                    "duration_minutes": 8,
                    "duration_seconds": 480,
                    "duration_in_traffic_minutes": 10,
                },
                {
                    "status": "OK",
                    "distance_miles": 7.8,
                    "distance_meters": 12552,
                    "duration_minutes": 18,
                    "duration_seconds": 1080,
                    "duration_in_traffic_minutes": 22,
                },
            ]
        )

        result = await distance_provider.enrich(
            latitude=40.7128,
            longitude=-74.0060,
            address="123 Test St",
            user_preferences={"custom_locations": mock_custom_locations},
        )

        assert result.success is True
        assert result.data["total_locations"] == 3
        assert len(result.data["distances"]) == 3
        assert result.data["distances"][0]["location_name"] == "Location 1"
        assert result.data["property_location"]["latitude"] == 40.7128
        assert result.data["property_location"]["longitude"] == -74.0060
        assert result.api_calls_made == 1

    @pytest.mark.asyncio
    async def test_enrich_with_api_error(self, distance_provider, mock_custom_locations):
        """Test enrichment handles API errors."""
        with patch.object(
            distance_provider,
            "_calculate_distances_batched",
            side_effect=ValueError("API error"),
        ):
            result = await distance_provider.enrich(
                latitude=40.7128,
                longitude=-74.0060,
                address="123 Test St",
                user_preferences={"custom_locations": mock_custom_locations},
            )

        assert result.success is False
        assert "API error" in result.error_message
        assert result.api_calls_made == 0


class TestCalculateDistancesBatched:
    @pytest.mark.asyncio
    async def test_calculate_distances_single_batch(self, distance_provider, mock_custom_locations):
        """Test distance calculation with locations fitting in one batch."""
        distance_provider.api_client.distance_matrix = AsyncMock(
            return_value=[
                {
                    "status": "OK",
                    "distance_miles": 5.2,
                    "distance_meters": 8369,
                    "duration_minutes": 12,
                    "duration_seconds": 720,
                },
                {
                    "status": "OK",
                    "distance_miles": 3.1,
                    "distance_meters": 4989,
                    "duration_minutes": 8,
                    "duration_seconds": 480,
                },
                {
                    "status": "OK",
                    "distance_miles": 7.8,
                    "distance_meters": 12552,
                    "duration_minutes": 18,
                    "duration_seconds": 1080,
                },
            ]
        )

        results = await distance_provider._calculate_distances_batched(
            origin=(40.7128, -74.0060), custom_locations=mock_custom_locations
        )

        assert len(results) == 3
        assert results[0]["location_id"] == 1
        assert results[0]["distance_miles"] == 5.2
        assert results[0]["status"] == "OK"
        distance_provider.api_client.distance_matrix.assert_called_once()

    @pytest.mark.asyncio
    async def test_calculate_distances_multiple_batches(self, distance_provider):
        """Test distance calculation with multiple batches."""
        locations = [
            CustomLocation(
                id=i + 1,
                name=f"Location {i + 1}",
                location_type="Family",
                address=f"{i} Test St",
                latitude=40.0 + i * 0.01,
                longitude=-74.0 + i * 0.01,
                priority=1,
            )
            for i in range(25)
        ]

        distance_provider.api_client.distance_matrix = AsyncMock(
            return_value=[{"status": "OK", "distance_miles": i * 1.0} for i in range(10)]
        )

        results = await distance_provider._calculate_distances_batched(
            origin=(40.7128, -74.0060), custom_locations=locations
        )

        assert len(results) == 25
        assert distance_provider.api_client.distance_matrix.call_count == 3

    @pytest.mark.asyncio
    async def test_calculate_distances_with_failed_status(
        self, distance_provider, mock_custom_locations
    ):
        """Test handling of failed distance calculations."""
        distance_provider.api_client.distance_matrix = AsyncMock(
            return_value=[
                {"status": "ZERO_RESULTS"},
                {"status": "NOT_FOUND", "error": "Address not found"},
                {
                    "status": "OK",
                    "distance_miles": 7.8,
                    "distance_meters": 12552,
                    "duration_minutes": 18,
                    "duration_seconds": 1080,
                },
            ]
        )

        results = await distance_provider._calculate_distances_batched(
            origin=(40.7128, -74.0060), custom_locations=mock_custom_locations
        )

        assert results[0]["status"] == "ZERO_RESULTS"
        assert results[1]["status"] == "NOT_FOUND"
        assert results[1]["error"] == "Address not found"
        assert results[2]["status"] == "OK"

    @pytest.mark.asyncio
    async def test_calculate_distances_with_exception(
        self, distance_provider, mock_custom_locations
    ):
        """Test handling of exceptions during batch processing."""
        distance_provider.api_client.distance_matrix = AsyncMock(
            side_effect=ConnectionError("Network error")
        )

        results = await distance_provider._calculate_distances_batched(
            origin=(40.7128, -74.0060), custom_locations=mock_custom_locations
        )

        assert len(results) == 3
        for result in results:
            assert result["status"] == "ERROR"
            assert "Network error" in result["error"]


class TestValidateConfig:
    @pytest.mark.asyncio
    async def test_validate_config_success(self, distance_provider):
        """Test successful configuration validation."""
        distance_provider.api_client.validate_api_key = AsyncMock(return_value=True)

        is_valid = await distance_provider.validate_config()

        assert is_valid is True

    @pytest.mark.asyncio
    async def test_validate_config_failure(self, distance_provider):
        """Test failed configuration validation."""
        distance_provider.api_client.validate_api_key = AsyncMock(return_value=False)

        is_valid = await distance_provider.validate_config()

        assert is_valid is False
