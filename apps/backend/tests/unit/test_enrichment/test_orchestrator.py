from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from app.exceptions import EnrichmentRateLimitError, PropertyNotFoundError
from app.models.property import Property
from app.models.property_enrichment import PropertyEnrichment
from app.models.user_preference import UserPreference
from app.services.enrichment.base_provider import (
    ProviderCategory,
    ProviderMetadata,
    ProviderResult,
)
from app.services.enrichment.orchestrator import EnrichmentOrchestrator

"""Tests for the EnrichmentOrchestrator."""


@pytest.fixture
def mock_db():
    """Create a mock database session."""
    return MagicMock()


@pytest.fixture
def mock_property():
    """Create a mock property."""
    property_obj = Mock(spec=Property)
    property_obj.id = 1
    property_obj.user_id = 1
    property_obj.latitude = 40.7128
    property_obj.longitude = -74.0060
    property_obj.address = "123 Main St"
    property_obj.bedrooms = 3
    property_obj.bathrooms = 2
    property_obj.square_feet = 1500
    property_obj.year_built = 2000
    property_obj.property_type = "house"
    return property_obj


@pytest.fixture
def mock_user_preference():
    """Create a mock user preference."""
    pref = Mock(spec=UserPreference)
    pref.user_id = 1
    pref.min_walk_score = 70
    pref.min_bike_score = 60
    pref.max_grocery_distance = 1.0
    pref.max_park_distance = 0.5
    pref.preferred_amenities = ["grocery", "park"]
    return pref


@pytest.fixture
def mock_provider():
    """Create a mock provider."""
    provider = Mock()
    provider.metadata = ProviderMetadata(
        name="test_provider",
        category=ProviderCategory.WALKABILITY,
        description="Test provider for walkability",
        version="1.0.0",
        cache_duration_days=30,
        enabled=True,
    )
    provider.should_run = Mock(return_value=True)
    provider.get_cache_key = Mock(return_value="test_cache_key")
    provider.enrich = AsyncMock(
        return_value=ProviderResult(
            provider_name="test_provider",
            data={"score": 85},
            success=True,
            cached=False,
            api_calls_made=1,
        )
    )
    return provider


@pytest.fixture
def orchestrator(mock_db):
    """Create an EnrichmentOrchestrator instance."""
    with patch("app.services.enrichment.orchestrator.CacheService"):
        return EnrichmentOrchestrator(mock_db)


@pytest.mark.asyncio
async def test_enrich_property_success(
    orchestrator, mock_db, mock_property, mock_user_preference, mock_provider
):
    """Test successful property enrichment."""
    # Setup mocks
    mock_db.query.return_value.filter.return_value.first.side_effect = [
        mock_property,  # _get_property
        None,  # _save_enrichment_results (no existing enrichment)
        mock_user_preference,  # _get_user_preferences
    ]
    mock_db.query.return_value.filter.return_value.count.return_value = 0  # Rate limit check

    orchestrator.provider_registry.get_enabled_providers = Mock(return_value=[mock_provider])
    orchestrator.cache_service.get = AsyncMock(return_value=None)
    orchestrator.cache_service.set = AsyncMock()

    # Execute
    result = await orchestrator.enrich_property(property_id=1, user_id=1)

    # Assert
    assert result["success"] is True
    assert result["metadata"]["total_providers"] == 1
    assert result["metadata"]["successful_providers"] == 1
    assert "test_provider" in result["enrichment_data"]
    assert result["enrichment_data"]["test_provider"]["data"]["score"] == 85


@pytest.mark.asyncio
async def test_enrich_property_not_found(orchestrator, mock_db):
    """Test enrichment with non-existent property."""
    mock_db.query.return_value.filter.return_value.first.return_value = None

    with pytest.raises(PropertyNotFoundError):
        await orchestrator.enrich_property(property_id=999, user_id=1)


@pytest.mark.asyncio
async def test_enrich_property_wrong_user(orchestrator, mock_db, mock_property):
    """Test enrichment with wrong user ID."""
    mock_property.user_id = 2
    mock_db.query.return_value.filter.return_value.first.return_value = mock_property

    with pytest.raises(PropertyNotFoundError):
        await orchestrator.enrich_property(property_id=1, user_id=1)


@pytest.mark.asyncio
async def test_enrich_property_rate_limit(orchestrator, mock_db, mock_property):
    """Test rate limit enforcement."""
    mock_db.query.return_value.filter.return_value.first.return_value = mock_property
    mock_db.query.return_value.filter.return_value.count.return_value = 15  # Over limit

    with pytest.raises(EnrichmentRateLimitError):
        await orchestrator.enrich_property(property_id=1, user_id=1, use_cached=False)


@pytest.mark.asyncio
async def test_enrich_property_with_cache(
    orchestrator, mock_db, mock_property, mock_user_preference, mock_provider
):
    """Test enrichment using cached data."""
    cached_data = {"score": 90}

    mock_db.query.return_value.filter.return_value.first.side_effect = [
        mock_property,
        None,
        mock_user_preference,
    ]
    mock_db.query.return_value.filter.return_value.count.return_value = 0

    orchestrator.provider_registry.get_enabled_providers = Mock(return_value=[mock_provider])
    orchestrator.cache_service.get = AsyncMock(return_value=cached_data)

    result = await orchestrator.enrich_property(property_id=1, user_id=1, use_cached=True)

    assert result["enrichment_data"]["test_provider"]["cached"] is True
    assert result["enrichment_data"]["test_provider"]["data"] == cached_data
    assert result["metadata"]["cached_providers"] == 1


@pytest.mark.asyncio
async def test_enrich_property_provider_filter(
    orchestrator, mock_db, mock_property, mock_user_preference
):
    """Test enrichment with provider filter."""
    provider1 = Mock()
    provider1.metadata = ProviderMetadata(
        name="provider1",
        category=ProviderCategory.WALKABILITY,
        description="Test provider 1",
        version="1.0.0",
        enabled=True,
    )
    provider1.should_run = Mock(return_value=True)

    provider2 = Mock()
    provider2.metadata = ProviderMetadata(
        name="provider2",
        category=ProviderCategory.NEARBY_PLACES,
        description="Test provider 2",
        version="1.0.0",
        enabled=True,
    )
    provider2.should_run = Mock(return_value=True)

    orchestrator.provider_registry.get_enabled_providers = Mock(return_value=[provider1, provider2])

    providers = orchestrator._get_applicable_providers(provider_filter=["provider1"])

    assert len(providers) == 1
    assert providers[0].metadata.name == "provider1"


@pytest.mark.asyncio
async def test_enrich_property_category_filter(orchestrator):
    """Test enrichment with category filter."""
    provider1 = Mock()
    provider1.metadata = ProviderMetadata(
        name="provider1",
        category=ProviderCategory.WALKABILITY,
        description="Test provider 1",
        version="1.0.0",
        enabled=True,
    )
    provider1.should_run = Mock(return_value=True)

    provider2 = Mock()
    provider2.metadata = ProviderMetadata(
        name="provider2",
        category=ProviderCategory.NEARBY_PLACES,
        description="Test provider 2",
        version="1.0.0",
        enabled=True,
    )
    provider2.should_run = Mock(return_value=True)

    orchestrator.provider_registry.get_enabled_providers = Mock(return_value=[provider1, provider2])

    providers = orchestrator._get_applicable_providers(
        category_filter=[ProviderCategory.WALKABILITY]
    )

    assert len(providers) == 1
    assert providers[0].metadata.category == ProviderCategory.WALKABILITY


def test_preferences_to_dict(orchestrator, mock_user_preference):
    """Test converting preferences to dictionary."""
    result = orchestrator._preferences_to_dict(mock_user_preference)

    assert result["user_id"] == 1
    assert result["min_walk_score"] == 70
    assert result["min_bike_score"] == 60
    assert result["max_grocery_distance"] == 1.0
    assert result["preferred_amenities"] == ["grocery", "park"]


def test_preferences_to_dict_none(orchestrator):
    """Test converting None preferences to dictionary."""
    result = orchestrator._preferences_to_dict(None)
    assert result == {}


@pytest.mark.asyncio
async def test_execute_providers_with_failure(orchestrator, mock_property):
    """Test provider execution with one provider failing."""
    success_provider = Mock()
    success_provider.metadata = ProviderMetadata(
        name="success",
        category=ProviderCategory.WALKABILITY,
        description="Success test provider",
        version="1.0.0",
        enabled=True,
    )
    success_provider.enrich = AsyncMock(
        return_value=ProviderResult(
            provider_name="success",
            data={"score": 85},
            success=True,
            api_calls_made=1,
        )
    )
    success_provider.get_cache_key = Mock(return_value="success_key")

    fail_provider = Mock()
    fail_provider.metadata = ProviderMetadata(
        name="failure",
        category=ProviderCategory.NEARBY_PLACES,
        description="Failure test provider",
        version="1.0.0",
        enabled=True,
    )
    fail_provider.enrich = AsyncMock(side_effect=Exception("API Error"))
    fail_provider.get_cache_key = Mock(return_value="fail_key")

    orchestrator.cache_service.get = AsyncMock(return_value=None)
    orchestrator.cache_service.set = AsyncMock()

    results = await orchestrator._execute_providers(
        providers=[success_provider, fail_provider],
        property_record=mock_property,
        user_preferences={},
        use_cached=False,
    )

    assert len(results) == 2
    assert results[0].provider_name == "success"
    assert results[0].success is True
    assert results[1].provider_name == "failure"
    assert results[1].success is False
    assert results[1].error_message == "API Error"


def test_map_result_to_enrichment_walk_score(orchestrator):
    """Test mapping walk score results to enrichment."""
    enrichment = PropertyEnrichment(property_id=1)
    enrichment.dynamic_enrichment_data = {}

    data = {
        "walk_score": 85,
        "bike_score": 75,
        "transit_score": 65,
        "description": "Very Walkable",
    }

    orchestrator._map_result_to_enrichment(enrichment, "walk_score", data)

    assert enrichment.walk_score == 85
    assert enrichment.bike_score == 75
    assert enrichment.transit_score == 65
    assert enrichment.walk_score_description == "Very Walkable"
    assert enrichment.dynamic_enrichment_data["walk_score"] == data


def test_map_result_to_enrichment_nearby_places(orchestrator):
    """Test mapping nearby places results to enrichment."""
    enrichment = PropertyEnrichment(property_id=1)
    enrichment.dynamic_enrichment_data = {}

    data = {
        "grocery_store": [{"name": "Store 1"}],
        "park": [{"name": "Park 1"}],
        "restaurant": [{"name": "Restaurant 1"}],
    }

    orchestrator._map_result_to_enrichment(enrichment, "nearby_places", data)

    assert enrichment.nearby_grocery_stores == [{"name": "Store 1"}]
    assert enrichment.nearby_parks == [{"name": "Park 1"}]
    assert enrichment.nearby_restaurants == [{"name": "Restaurant 1"}]


def test_format_response(orchestrator):
    """Test response formatting."""
    results = [
        ProviderResult(
            provider_name="provider1",
            data={"score": 85},
            success=True,
            cached=False,
            api_calls_made=1,
            enriched_at=datetime.now(timezone.utc),
        ),
        ProviderResult(
            provider_name="provider2",
            data={},
            success=False,
            error_message="API Error",
            api_calls_made=0,
        ),
    ]

    response = orchestrator._format_response(results)

    assert response["success"] is True
    assert response["metadata"]["total_providers"] == 2
    assert response["metadata"]["successful_providers"] == 1
    assert response["metadata"]["failed_providers"] == 1
    assert response["metadata"]["total_api_calls"] == 1
    assert "provider1" in response["enrichment_data"]
    assert "provider2" in response["enrichment_data"]
    assert response["enrichment_data"]["provider2"]["error"] == "API Error"


@pytest.mark.asyncio
async def test_track_api_usage(orchestrator, mock_db):
    """Test API usage tracking."""
    results = [
        ProviderResult(
            provider_name="provider1",
            data={"score": 85},
            success=True,
            api_calls_made=2,
        ),
        ProviderResult(
            provider_name="provider2",
            data={},
            success=False,
            api_calls_made=0,
        ),
    ]

    with patch("app.models.api_usage.APIUsage") as mock_usage:
        await orchestrator._track_api_usage(user_id=1, results=results)

        assert mock_db.add.call_count == 1
        mock_db.commit.assert_called_once()
