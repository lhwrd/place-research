import math
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.enrichment.base_provider import ProviderCategory, ProviderResult
from app.services.enrichment.providers.highways import HighwayProvider


@pytest.fixture
def highway_provider():
    """Fixture to create a HighwayProvider instance."""
    return HighwayProvider()


@pytest.fixture
def sample_highway_data():
    """Fixture providing sample highway API response data."""
    return {
        "elements": [
            {
                "type": "way",
                "id": 123456,
                "tags": {"highway": "motorway", "name": "Highway 101"},
                "geometry": [
                    {"lat": 37.7750, "lon": -122.4195},
                    {"lat": 37.7751, "lon": -122.4196},
                    {"lat": 37.7752, "lon": -122.4197},
                ],
            },
            {
                "type": "way",
                "id": 789012,
                "tags": {"highway": "primary", "name": "Main Street"},
                "geometry": [
                    {"lat": 37.7760, "lon": -122.4200},
                    {"lat": 37.7761, "lon": -122.4201},
                ],
            },
        ]
    }


class TestHighwayProviderMetadata:
    """Test cases for HighwayProvider metadata."""

    def test_metadata_properties(self, highway_provider):
        """Test that metadata contains correct properties."""
        metadata = highway_provider.metadata

        assert metadata.name == "highway_provider"
        assert metadata.category == ProviderCategory.ENVIRONMENTAL
        assert metadata.enabled is True
        assert metadata.version == "1.0.0"
        assert metadata.requires_api_key is True
        assert metadata.cost_per_call == 0.001


class TestCalculateMinDistanceToHighways:
    """Test cases for _calculate_min_distance_to_highways method."""

    def test_calculate_min_distance_with_highways(self, highway_provider):
        """Test distance calculation with valid highway data."""
        highways = [
            {
                "type": "way",
                "geometry": [
                    {"lat": 37.7750, "lon": -122.4195},
                    {"lat": 37.7760, "lon": -122.4200},
                ],
            }
        ]

        distance = highway_provider._calculate_min_distance_to_highways(
            37.7749, -122.4194, highways
        )

        assert distance is not None
        assert distance > 0

    def test_calculate_min_distance_empty_highways(self, highway_provider):
        """Test distance calculation with no highways."""
        distance = highway_provider._calculate_min_distance_to_highways(37.7749, -122.4194, [])

        assert distance is None

    def test_calculate_min_distance_missing_geometry(self, highway_provider):
        """Test distance calculation with highways missing geometry."""
        highways = [{"type": "way", "id": 123}]

        distance = highway_provider._calculate_min_distance_to_highways(
            37.7749, -122.4194, highways
        )

        assert distance is None

    def test_calculate_min_distance_invalid_coordinates(self, highway_provider):
        """Test distance calculation with invalid coordinates in geometry."""
        highways = [
            {
                "type": "way",
                "geometry": [
                    {"lat": None, "lon": -122.4195},
                    {"lat": 37.7750, "lon": None},
                ],
            }
        ]

        distance = highway_provider._calculate_min_distance_to_highways(
            37.7749, -122.4194, highways
        )

        assert distance is None


class TestEstimateRoadNoiseLevel:
    """Test cases for _estimate_road_noise_level method."""

    def test_noise_estimation_none_distance(self, highway_provider):
        """Test noise estimation with None distance."""
        result = highway_provider._estimate_road_noise_level(None, ["motorway"])

        assert result["noise_level_db"] is None
        assert result["noise_category"] == "Unknown"

    def test_noise_estimation_very_close_motorway(self, highway_provider):
        """Test noise estimation very close to motorway."""
        result = highway_provider._estimate_road_noise_level(20, ["motorway"])

        assert result["noise_level_db"] == 75
        assert result["noise_category"] == "Very High"

    def test_noise_estimation_at_reference_distance(self, highway_provider):
        """Test noise estimation at reference distance (30m)."""
        result = highway_provider._estimate_road_noise_level(30, ["trunk"])

        assert result["noise_level_db"] == 70
        assert result["noise_category"] == "Very High"

    def test_noise_estimation_far_distance(self, highway_provider):
        """Test noise estimation at far distance."""
        result = highway_provider._estimate_road_noise_level(500, ["motorway"])

        assert result["noise_level_db"] < 75
        assert result["noise_category"] in ["Low", "Very Low", "Moderate"]

    def test_noise_estimation_primary_road(self, highway_provider):
        """Test noise estimation for primary road."""
        result = highway_provider._estimate_road_noise_level(30, ["primary"])

        assert result["noise_level_db"] == 65
        assert result["noise_category"] == "High"

    def test_noise_estimation_empty_highway_types(self, highway_provider):
        """Test noise estimation with no highway types."""
        result = highway_provider._estimate_road_noise_level(30, [])

        assert result["noise_level_db"] == 60
        assert result["noise_category"] == "High"

    def test_noise_categories(self, highway_provider):
        """Test all noise categories are assigned correctly."""
        # Very High: >= 70
        assert (
            highway_provider._estimate_road_noise_level(30, ["motorway"])["noise_category"]
            == "Very High"
        )

        # High: >= 60
        assert (
            highway_provider._estimate_road_noise_level(60, ["motorway"])["noise_category"]
            == "High"
        )

        # Moderate: >= 50
        assert (
            highway_provider._estimate_road_noise_level(200, ["motorway"])["noise_category"]
            == "Moderate"
        )

        # Low: >= 40
        assert (
            highway_provider._estimate_road_noise_level(1000, ["motorway"])["noise_category"]
            == "Low"
        )

        # Very Low: < 40
        assert (
            highway_provider._estimate_road_noise_level(2000, ["motorway"])["noise_category"]
            == "Very Low"
        )


class TestEnrich:
    """Test cases for enrich method."""

    @pytest.mark.asyncio
    async def test_enrich_with_highways(self, highway_provider, sample_highway_data):
        """Test enrichment with valid highway data."""
        with patch.object(
            highway_provider.api_client,
            "fetch_nearby_highways",
            new_callable=AsyncMock,
            return_value=sample_highway_data,
        ):
            result = await highway_provider.enrich(37.7749, -122.4194, "123 Test St")

            assert isinstance(result, ProviderResult)
            assert result.success is True
            assert result.provider_name == "highway_provider"
            assert result.api_calls_made == 1
            assert "highway_distance_m" in result.data
            assert "nearest_highway_type" in result.data
            assert "road_noise_level_db" in result.data
            assert "road_noise_category" in result.data
            assert result.data["highway_distance_m"] is not None
            assert result.data["nearest_highway_type"] in ["motorway", "primary"]

    @pytest.mark.asyncio
    async def test_enrich_no_highways_found(self, highway_provider):
        """Test enrichment when no highways are found."""
        with patch.object(
            highway_provider.api_client,
            "fetch_nearby_highways",
            new_callable=AsyncMock,
            return_value={"elements": []},
        ):
            result = await highway_provider.enrich(37.7749, -122.4194, "123 Test St")

            assert result.success is True
            assert result.data == {}
            assert result.api_calls_made == 1

    @pytest.mark.asyncio
    async def test_enrich_with_property_data_and_preferences(
        self, highway_provider, sample_highway_data
    ):
        """Test enrichment with optional property data and user preferences."""
        with patch.object(
            highway_provider.api_client,
            "fetch_nearby_highways",
            new_callable=AsyncMock,
            return_value=sample_highway_data,
        ):
            property_data = {"bedrooms": 3, "bathrooms": 2}
            user_preferences = {"max_noise": 60}

            result = await highway_provider.enrich(
                37.7749,
                -122.4194,
                "123 Test St",
                property_data=property_data,
                user_preferences=user_preferences,
            )

            assert result.success is True
            assert result.data["highway_distance_m"] is not None


class TestValidateConfig:
    """Test cases for validate_config method."""

    @pytest.mark.asyncio
    async def test_validate_config_success(self, highway_provider):
        """Test successful configuration validation."""
        with patch.object(
            highway_provider.api_client,
            "validate_api_key",
            new_callable=AsyncMock,
            return_value=True,
        ):
            result = await highway_provider.validate_config()
            assert result is True

    @pytest.mark.asyncio
    async def test_validate_config_failure(self, highway_provider):
        """Test failed configuration validation."""
        with patch.object(
            highway_provider.api_client,
            "validate_api_key",
            new_callable=AsyncMock,
            return_value=False,
        ):
            result = await highway_provider.validate_config()
            assert result is False
