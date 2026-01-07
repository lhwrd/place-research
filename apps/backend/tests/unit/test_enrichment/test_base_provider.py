"""Tests for base provider interface."""

import pytest
from datetime import datetime, timezone
from typing import Dict, Any, Optional

from app.services.enrichment.base_provider import (
    BaseEnrichmentProvider,
    ProviderCategory,
    ProviderMetadata,
    ProviderResult,
)


class MockEnrichmentProvider(BaseEnrichmentProvider):
    """Mock provider for testing."""

    def __init__(self, enabled: bool = True, metadata_override: Optional[Dict[str, Any]] = None):
        self._enabled = enabled
        self._metadata_override = metadata_override or {}

    @property
    def metadata(self) -> ProviderMetadata:
        defaults = {
            "name": "mock_provider",
            "category": ProviderCategory.WALKABILITY,
            "description": "Mock provider for testing",
            "version": "1.0.0",
            "enabled": self._enabled,
            "requires_api_key": True,
            "cost_per_call": 0.01,
            "cache_duration_days": 30,
            "rate_limit_per_hour": 100,
            "dependencies": [],
        }
        defaults.update(self._metadata_override)
        return ProviderMetadata(**defaults)

    async def enrich(
        self,
        latitude: float,
        longitude: float,
        address: str,
        property_data: Optional[Dict[str, Any]] = None,
        user_preferences: Optional[Dict[str, Any]] = None,
    ) -> ProviderResult:
        return ProviderResult(
            provider_name=self.metadata.name,
            data={"latitude": latitude, "longitude": longitude, "address": address},
            success=True,
            api_calls_made=1,
        )

    async def validate_config(self) -> bool:
        return True


class TestProviderMetadata:
    """Test ProviderMetadata dataclass."""

    def test_provider_metadata_creation(self):
        metadata = ProviderMetadata(
            name="test_provider",
            category=ProviderCategory.WALKABILITY,
            description="Test description",
            version="1.0.0",
        )

        assert metadata.name == "test_provider"
        assert metadata.category == ProviderCategory.WALKABILITY
        assert metadata.description == "Test description"
        assert metadata.version == "1.0.0"
        assert metadata.enabled is True
        assert metadata.requires_api_key is True
        assert metadata.cost_per_call == 0.0
        assert metadata.cache_duration_days == 30
        assert metadata.rate_limit_per_hour is None
        assert metadata.dependencies == []


class TestProviderResult:
    """Test ProviderResult dataclass."""

    def test_provider_result_creation(self):
        result = ProviderResult(
            provider_name="test_provider",
            data={"key": "value"},
            success=True,
        )

        assert result.provider_name == "test_provider"
        assert result.data == {"key": "value"}
        assert result.success is True
        assert result.error_message is None
        assert result.api_calls_made == 0
        assert result.cached is False
        assert isinstance(result.enriched_at, datetime)

    def test_provider_result_with_error(self):
        result = ProviderResult(
            provider_name="test_provider",
            data={},
            success=False,
            error_message="API error",
        )

        assert result.success is False
        assert result.error_message == "API error"


class TestBaseEnrichmentProvider:
    """Test BaseEnrichmentProvider abstract class."""

    @pytest.mark.asyncio
    async def test_mock_provider_enrich(self):
        provider = MockEnrichmentProvider()
        result = await provider.enrich(
            latitude=37.7749,
            longitude=-122.4194,
            address="123 Main St",
        )

        assert result.provider_name == "mock_provider"
        assert result.success is True
        assert result.data["latitude"] == 37.7749
        assert result.data["longitude"] == -122.4194
        assert result.data["address"] == "123 Main St"

    @pytest.mark.asyncio
    async def test_mock_provider_validate_config(self):
        provider = MockEnrichmentProvider()
        is_valid = await provider.validate_config()
        assert is_valid is True

    def test_should_run_when_enabled(self):
        provider = MockEnrichmentProvider(enabled=True)
        assert provider.should_run() is True

    def test_should_run_when_disabled(self):
        provider = MockEnrichmentProvider(enabled=False)
        assert provider.should_run() is False

    def test_should_run_with_user_preferences(self):
        provider = MockEnrichmentProvider(enabled=True)
        user_prefs = {"some_preference": "value"}
        assert provider.should_run(user_preferences=user_prefs) is True

    def test_get_cache_key_basic(self):
        provider = MockEnrichmentProvider()
        cache_key = provider.get_cache_key(latitude=37.774929, longitude=-122.419416)

        assert cache_key == "mock_provider:37.7749:-122.4194"

    def test_get_cache_key_with_kwargs(self):
        provider = MockEnrichmentProvider()
        cache_key = provider.get_cache_key(
            latitude=37.774929,
            longitude=-122.419416,
            radius=1000,
            category="restaurant",
        )

        assert "mock_provider:37.7749:-122.4194" in cache_key
        assert "category=restaurant" in cache_key
        assert "radius=1000" in cache_key

    def test_get_cache_key_coordinates_rounded(self):
        provider = MockEnrichmentProvider()
        cache_key1 = provider.get_cache_key(latitude=37.774900, longitude=-122.419400)
        cache_key2 = provider.get_cache_key(latitude=37.774949, longitude=-122.419449)

        # Both should round to same key (4 decimal places)
        assert cache_key1 == cache_key2 == "mock_provider:37.7749:-122.4194"


class TestProviderCategory:
    """Test ProviderCategory enum."""

    def test_all_categories_exist(self):
        assert ProviderCategory.WALKABILITY.value == "walkability"
        assert ProviderCategory.NEARBY_PLACES.value == "nearby_places"
        assert ProviderCategory.DISTANCES.value == "distances"
        assert ProviderCategory.ENVIRONMENTAL.value == "environmental"
        assert ProviderCategory.CLIMATE.value == "climate"
        assert ProviderCategory.NOISE.value == "noise"
        assert ProviderCategory.SAFETY.value == "safety"
        assert ProviderCategory.TRANSIT.value == "transit"
        assert ProviderCategory.DEMOGRAPHICS.value == "demographics"
