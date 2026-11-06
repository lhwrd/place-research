"""Tests for the EnrichmentOrchestrator."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, Mock, patch

import pytest

from app.services.enrichment.base_provider import (
    ProviderCategory,
    ProviderMetadata,
    ProviderResult,
)
from app.services.enrichment.orchestrator import EnrichmentOrchestrator

LOCATION = {"latitude": 40.7128, "longitude": -74.0060, "address": "123 Main St"}


def _provider(name, category=ProviderCategory.WALKABILITY):
    provider = Mock()
    provider.metadata = ProviderMetadata(
        name=name,
        category=category,
        description=f"Test provider {name}",
        version="1.0.0",
        enabled=True,
    )
    provider.should_run = Mock(return_value=True)
    provider.get_cache_key = Mock(return_value=f"{name}_key")
    return provider


@pytest.fixture
def mock_provider():
    """Create a mock provider."""
    provider = _provider("test_provider")
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
def orchestrator():
    """Create an EnrichmentOrchestrator instance."""
    with patch("app.services.enrichment.orchestrator.CacheService"):
        return EnrichmentOrchestrator()


@pytest.mark.asyncio
async def test_enrich_success(orchestrator, mock_provider):
    """Test successful enrichment."""
    orchestrator.provider_registry.get_enabled_providers = Mock(return_value=[mock_provider])
    orchestrator.cache_service.get = AsyncMock(return_value=None)
    orchestrator.cache_service.set = AsyncMock()

    result = await orchestrator.enrich(**LOCATION, property_data={"bedrooms": 3})

    assert result["success"] is True
    assert result["metadata"]["total_providers"] == 1
    assert result["metadata"]["successful_providers"] == 1
    assert result["enrichment_data"]["test_provider"]["data"]["score"] == 85
    mock_provider.enrich.assert_awaited_once_with(
        latitude=40.7128,
        longitude=-74.0060,
        address="123 Main St",
        property_data={"bedrooms": 3},
        user_preferences={},
    )
    orchestrator.cache_service.set.assert_awaited_once()


@pytest.mark.asyncio
async def test_enrich_passes_preferences_to_providers(orchestrator, mock_provider):
    """User preferences reach both should_run and enrich."""
    orchestrator.provider_registry.get_enabled_providers = Mock(return_value=[mock_provider])
    orchestrator.cache_service.get = AsyncMock(return_value=None)
    orchestrator.cache_service.set = AsyncMock()
    preferences = {"preferred_amenities": ["park"], "custom_locations": []}

    await orchestrator.enrich(**LOCATION, user_preferences=preferences)

    mock_provider.should_run.assert_called_once_with(user_preferences=preferences)
    assert mock_provider.enrich.call_args.kwargs["user_preferences"] == preferences


@pytest.mark.asyncio
async def test_enrich_with_cache(orchestrator, mock_provider):
    """Test enrichment using cached data."""
    cached_data = {"score": 90}
    orchestrator.provider_registry.get_enabled_providers = Mock(return_value=[mock_provider])
    orchestrator.cache_service.get = AsyncMock(return_value=cached_data)

    result = await orchestrator.enrich(**LOCATION, use_cached=True)

    assert result["enrichment_data"]["test_provider"]["cached"] is True
    assert result["enrichment_data"]["test_provider"]["data"] == cached_data
    assert result["metadata"]["cached_providers"] == 1
    mock_provider.enrich.assert_not_called()


@pytest.mark.asyncio
async def test_enrich_bypasses_cache(orchestrator, mock_provider):
    """use_cached=False always calls the provider."""
    orchestrator.provider_registry.get_enabled_providers = Mock(return_value=[mock_provider])
    orchestrator.cache_service.get = AsyncMock(return_value={"score": 90})
    orchestrator.cache_service.set = AsyncMock()

    result = await orchestrator.enrich(**LOCATION, use_cached=False)

    orchestrator.cache_service.get.assert_not_called()
    assert result["enrichment_data"]["test_provider"]["data"]["score"] == 85


def test_provider_filter(orchestrator):
    """Test enrichment with provider filter."""
    orchestrator.provider_registry.get_enabled_providers = Mock(
        return_value=[
            _provider("provider1"),
            _provider("provider2", ProviderCategory.NEARBY_PLACES),
        ]
    )

    providers = orchestrator._get_applicable_providers(provider_filter=["provider1"])

    assert [p.metadata.name for p in providers] == ["provider1"]


def test_category_filter(orchestrator):
    """Test enrichment with category filter."""
    orchestrator.provider_registry.get_enabled_providers = Mock(
        return_value=[
            _provider("provider1"),
            _provider("provider2", ProviderCategory.NEARBY_PLACES),
        ]
    )

    providers = orchestrator._get_applicable_providers(
        category_filter=[ProviderCategory.WALKABILITY]
    )

    assert [p.metadata.category for p in providers] == [ProviderCategory.WALKABILITY]


@pytest.mark.asyncio
async def test_execute_providers_with_failure(orchestrator):
    """Test provider execution with one provider failing."""
    success_provider = _provider("success")
    success_provider.enrich = AsyncMock(
        return_value=ProviderResult(
            provider_name="success",
            data={"score": 85},
            success=True,
            api_calls_made=1,
        )
    )
    fail_provider = _provider("failure", ProviderCategory.NEARBY_PLACES)
    fail_provider.enrich = AsyncMock(side_effect=Exception("API Error"))

    orchestrator.cache_service.get = AsyncMock(return_value=None)
    orchestrator.cache_service.set = AsyncMock()

    results = await orchestrator._execute_providers(
        providers=[success_provider, fail_provider],
        **LOCATION,
        property_data={},
        user_preferences={},
        use_cached=False,
    )

    assert len(results) == 2
    assert results[0].provider_name == "success"
    assert results[0].success is True
    assert results[1].provider_name == "failure"
    assert results[1].success is False
    assert results[1].error_message == "API Error"


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
    assert response["enrichment_data"]["provider2"]["error"] == "API Error"
