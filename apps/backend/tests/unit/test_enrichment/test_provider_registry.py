from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

from app.services.enrichment.provider_registry import ProviderRegistry

"""Tests for the provider registry module."""

from app.services.enrichment.base_provider import (
    BaseEnrichmentProvider,
    ProviderCategory,
    ProviderMetadata,
)


class MockProvider(BaseEnrichmentProvider):
    """Mock provider for testing."""

    @property
    def metadata(self) -> ProviderMetadata:
        return ProviderMetadata(
            name="mock_provider",
            category=ProviderCategory.DEMOGRAPHICS,
            description="A mock provider for testing",
            version="1.0.0",
            enabled=True,
        )

    async def enrich(
        self,
        latitude: float,
        longitude: float,
        address: str,
        property_data: dict = None,
        user_preferences: dict = None,
    ):
        from app.services.enrichment.base_provider import ProviderResult

        return ProviderResult(
            provider_name="mock_provider",
            data={"mock": "data"},
            success=True,
        )

    async def validate_config(self) -> bool:
        return True


class DisabledMockProvider(BaseEnrichmentProvider):
    """Disabled mock provider for testing."""

    @property
    def metadata(self) -> ProviderMetadata:
        return ProviderMetadata(
            name="disabled_provider",
            category=ProviderCategory.SAFETY,
            description="A disabled provider",
            version="1.0.0",
            enabled=False,
        )

    async def enrich(
        self,
        latitude: float,
        longitude: float,
        address: str,
        property_data: dict = None,
        user_preferences: dict = None,
    ):
        from app.services.enrichment.base_provider import ProviderResult

        return ProviderResult(
            provider_name="disabled_provider",
            data={},
            success=True,
        )

    async def validate_config(self) -> bool:
        return True


@pytest.fixture
def clean_registry():
    """Reset registry state before each test."""
    ProviderRegistry._instance = None
    ProviderRegistry._providers = {}
    ProviderRegistry._initialized = False
    yield
    ProviderRegistry._instance = None
    ProviderRegistry._providers = {}
    ProviderRegistry._initialized = False


def test_singleton_pattern(clean_registry):
    """Test that ProviderRegistry follows singleton pattern."""
    registry1 = ProviderRegistry()
    registry2 = ProviderRegistry()
    assert registry1 is registry2


def test_register_provider(clean_registry):
    """Test registering a provider."""
    registry = ProviderRegistry()
    ProviderRegistry._providers = {}  # Clear any auto-discovered providers

    registry.register_provider(MockProvider)

    assert "mock_provider" in ProviderRegistry._providers
    assert ProviderRegistry._providers["mock_provider"] == MockProvider


def test_register_provider_overwrite(clean_registry):
    """Test overwriting an existing provider."""
    registry = ProviderRegistry()
    ProviderRegistry._providers = {}

    registry.register_provider(MockProvider)
    registry.register_provider(MockProvider)

    assert len(ProviderRegistry._providers) == 1


def test_get_provider(clean_registry):
    """Test retrieving a provider by name."""
    registry = ProviderRegistry()
    ProviderRegistry._providers = {}
    registry.register_provider(MockProvider)

    provider = registry.get_provider("mock_provider")

    assert provider is not None
    assert isinstance(provider, MockProvider)


def test_get_provider_not_found(clean_registry):
    """Test retrieving a non-existent provider."""
    registry = ProviderRegistry()
    ProviderRegistry._providers = {}

    provider = registry.get_provider("nonexistent")

    assert provider is None


def test_get_all_providers(clean_registry):
    """Test getting all registered providers."""
    registry = ProviderRegistry()
    ProviderRegistry._providers = {}
    registry.register_provider(MockProvider)
    registry.register_provider(DisabledMockProvider)

    providers = registry.get_all_providers()

    assert len(providers) == 2
    assert all(isinstance(p, BaseEnrichmentProvider) for p in providers)


def test_get_providers_by_category(clean_registry):
    """Test filtering providers by category."""
    registry = ProviderRegistry()
    ProviderRegistry._providers = {}
    registry.register_provider(MockProvider)
    registry.register_provider(DisabledMockProvider)

    demographics_providers = registry.get_providers_by_category(ProviderCategory.DEMOGRAPHICS)
    safety_providers = registry.get_providers_by_category(ProviderCategory.SAFETY)

    assert len(demographics_providers) == 1
    assert len(safety_providers) == 1
    assert demographics_providers[0].metadata.name == "mock_provider"
    assert safety_providers[0].metadata.name == "disabled_provider"


def test_get_enabled_providers(clean_registry):
    """Test getting only enabled providers."""
    registry = ProviderRegistry()
    ProviderRegistry._providers = {}
    registry.register_provider(MockProvider)
    registry.register_provider(DisabledMockProvider)

    enabled_providers = registry.get_enabled_providers()

    assert len(enabled_providers) == 1
    assert enabled_providers[0].metadata.name == "mock_provider"


def test_list_providers(clean_registry):
    """Test listing provider metadata."""
    registry = ProviderRegistry()
    ProviderRegistry._providers = {}
    registry.register_provider(MockProvider)

    metadata_list = registry.list_providers()

    assert len(metadata_list) == 1
    assert isinstance(metadata_list[0], ProviderMetadata)
    assert metadata_list[0].name == "mock_provider"


@patch("app.services.enrichment.provider_registry.pkgutil.iter_modules")
@patch("app.services.enrichment.provider_registry.importlib.import_module")
def test_discover_providers(mock_import, mock_iter_modules, clean_registry):
    """Test automatic provider discovery."""
    # Mock module discovery
    mock_module_info = MagicMock()
    mock_module_info.name = "test_provider"
    mock_iter_modules.return_value = [mock_module_info]

    # Mock module import
    mock_module = MagicMock()
    mock_module.MockProvider = MockProvider
    mock_import.return_value = mock_module

    with patch("inspect.getmembers", return_value=[("MockProvider", MockProvider)]):
        registry = ProviderRegistry()

    assert "mock_provider" in ProviderRegistry._providers


@patch("app.services.enrichment.provider_registry.Path.exists")
def test_discover_providers_no_directory(mock_exists, clean_registry):
    """Test discovery when providers directory doesn't exist."""
    mock_exists.return_value = False

    registry = ProviderRegistry()

    assert len(ProviderRegistry._providers) == 0


@patch("app.services.enrichment.provider_registry.pkgutil.iter_modules")
@patch("app.services.enrichment.provider_registry.importlib.import_module")
def test_discover_providers_import_error(mock_import, mock_iter_modules, clean_registry):
    """Test handling of import errors during discovery."""
    mock_module_info = MagicMock()
    mock_module_info.name = "failing_provider"
    mock_iter_modules.return_value = [mock_module_info]
    mock_import.side_effect = ImportError("Module not found")

    registry = ProviderRegistry()

    # Should not raise, just log error
    assert len(ProviderRegistry._providers) == 0
