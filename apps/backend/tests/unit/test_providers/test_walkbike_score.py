import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.services.enrichment.providers.walkbike_score import WalkScoreProvider
from app.services.enrichment.base_provider import ProviderCategory

"""Tests for Walk Score enrichment provider."""


@pytest.fixture
def provider():
    """Create a WalkScoreProvider instance."""
    with patch("app.services.enrichment.providers.walkbike_score.WalkScoreAPI"):
        return WalkScoreProvider()


@pytest.fixture
def mock_api_response():
    """Mock successful API response."""
    return {
        "walkscore": 85,
        "bike": {"score": 75},
        "transit": {"score": 65},
        "description": "Very Walkable",
    }


class TestWalkScoreProviderMetadata:
    """Test provider metadata."""

    def test_metadata_properties(self, provider):
        """Test metadata returns correct values."""
        metadata = provider.metadata
        assert metadata.name == "walk_score"
        assert metadata.category == ProviderCategory.WALKABILITY
        assert metadata.version == "1.0.0"
        assert metadata.enabled is True
        assert metadata.requires_api_key is True
        assert metadata.cost_per_call == 0.01
        assert metadata.cache_duration_days == 90
        assert metadata.rate_limit_per_hour == 100


class TestWalkScoreProviderEnrich:
    """Test enrichment functionality."""

    @pytest.mark.asyncio
    async def test_enrich_success(self, provider, mock_api_response):
        """Test successful enrichment."""
        provider.api_client.get_score = AsyncMock(return_value=mock_api_response)

        result = await provider.enrich(
            latitude=40.7128, longitude=-74.0060, address="123 Main St, New York, NY"
        )

        assert result.success is True
        assert result.provider_name == "walk_score"
        assert result.data["walk_score"] == 85
        assert result.data["bike_score"] == 75
        assert result.data["transit_score"] == 65
        assert result.data["description"] == "Very Walkable"
        assert result.api_calls_made == 1
        assert result.error_message is None

    @pytest.mark.asyncio
    async def test_enrich_missing_bike_score(self, provider):
        """Test enrichment when bike score is missing."""
        response = {"walkscore": 85, "description": "Very Walkable"}
        provider.api_client.get_score = AsyncMock(return_value=response)

        result = await provider.enrich(40.7128, -74.0060, "123 Main St")

        assert result.success is True
        assert result.data["walk_score"] == 85
        assert result.data["bike_score"] is None
        assert result.data["transit_score"] is None

    @pytest.mark.asyncio
    async def test_enrich_api_error(self, provider):
        """Test enrichment when API raises an error."""
        provider.api_client.get_score = AsyncMock(side_effect=Exception("API Error"))

        result = await provider.enrich(40.7128, -74.0060, "123 Main St")

        assert result.success is False
        assert result.provider_name == "walk_score"
        assert result.data == {}
        assert result.error_message == "API Error"
        assert result.api_calls_made == 0


class TestWalkScoreProviderValidateConfig:
    """Test configuration validation."""

    @pytest.mark.asyncio
    async def test_validate_config_success(self, provider):
        """Test successful config validation."""
        provider.api_client.validate_api_key = AsyncMock(return_value=True)

        result = await provider.validate_config()

        assert result is True
        provider.api_client.validate_api_key.assert_called_once()

    @pytest.mark.asyncio
    async def test_validate_config_failure(self, provider):
        """Test failed config validation."""
        provider.api_client.validate_api_key = AsyncMock(return_value=False)

        result = await provider.validate_config()

        assert result is False


class TestWalkScoreProviderShouldRun:
    """Test should_run logic."""

    def test_should_run_with_walk_score_preference(self, provider):
        """Test should run when walk score preference is set."""
        user_prefs = {"min_walk_score": 80}

        result = provider.should_run(user_prefs)

        assert result is True

    def test_should_run_with_bike_score_preference(self, provider):
        """Test should run when bike score preference is set."""
        user_prefs = {"min_bike_score": 70}

        result = provider.should_run(user_prefs)

        assert result is True

    def test_should_run_with_transit_score_preference(self, provider):
        """Test should run when transit score preference is set."""
        user_prefs = {"min_transit_score": 60}

        result = provider.should_run(user_prefs)

        assert result is True

    def test_should_run_with_no_preferences(self, provider):
        """Test should run by default when no preferences."""
        result = provider.should_run({})

        assert result is True

    def test_should_run_with_none_preferences(self, provider):
        """Test should run by default when preferences is None."""
        result = provider.should_run(None)

        assert result is True

    def test_should_run_when_disabled(self, provider):
        """Test should not run when provider is disabled."""
        # Patch the metadata property to return metadata with enabled=False
        disabled_metadata = provider.metadata
        disabled_metadata.enabled = False
        with patch.object(type(provider), "metadata", property(lambda self: disabled_metadata)):
            result = provider.should_run({"min_walk_score": 80})

            assert result is False
