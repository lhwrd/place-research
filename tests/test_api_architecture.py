"""Tests for the new API-first architecture.

These tests demonstrate the improved testability of the refactored codebase.
"""

import pytest
from place_research.config import Settings
from place_research.service import PlaceEnrichmentService
from place_research.repositories import InMemoryRepository
from place_research.models import Place
from place_research.models.results import (
    EnrichmentResult,
    WalkBikeScoreResult,
    ProviderError,
)


class TestConfiguration:
    """Test configuration management."""

    def test_settings_creation(self):
        """Test that settings can be created."""
        settings = Settings()
        assert settings is not None
        # log_level is loaded from .env, so just check it exists
        assert settings.log_level in ["DEBUG", "INFO", "WARNING", "ERROR"]

    def test_custom_settings(self):
        """Test custom settings override defaults."""
        settings = Settings(api_host="127.0.0.1", api_port=9000, log_level="DEBUG")
        assert settings.api_host == "127.0.0.1"
        assert settings.api_port == 9000
        assert settings.log_level == "DEBUG"

    def test_provider_config_validation(self):
        """Test provider configuration validation."""
        settings = Settings()

        # Test with missing config
        missing = settings.validate_provider_config("WalkBikeScoreProvider")
        # Will vary based on actual .env - this just tests the method works
        assert isinstance(missing, list)


class TestEnrichmentResult:
    """Test result objects."""

    def test_result_creation(self):
        """Test creating an enrichment result."""
        result = EnrichmentResult(place_id="123")
        assert result.place_id == "123"
        assert result.errors == []
        assert not result.has_errors()

    def test_result_with_data(self):
        """Test result with provider data."""
        result = EnrichmentResult(
            place_id="123",
            walk_bike_score=WalkBikeScoreResult(
                walk_score=85,
                walk_description="Very Walkable",
                bike_score=75,
                bike_description="Very Bikeable",
            ),
        )
        assert result.walk_bike_score.walk_score == 85
        assert not result.has_errors()

    def test_result_with_errors(self):
        """Test result with errors."""
        error = ProviderError(
            provider_name="test", error_message="Test error", error_type="TEST_ERROR"
        )
        result = EnrichmentResult(place_id="123", errors=[error])
        assert result.has_errors()
        assert len(result.errors) == 1

    def test_result_serialization(self):
        """Test converting result to dictionary."""
        result = EnrichmentResult(
            place_id="123",
            walk_bike_score=WalkBikeScoreResult(
                walk_score=85, walk_description="Very Walkable"
            ),
        )
        data = result.to_dict()

        assert data["place_id"] == "123"
        assert "walk_bike_score" in data
        assert data["walk_bike_score"]["walk_score"] == 85


class TestInMemoryRepository:
    """Test in-memory repository."""

    def test_repository_creation(self):
        """Test creating a repository."""
        repo = InMemoryRepository()
        assert repo.get_all() == []

    def test_save_and_retrieve(self):
        """Test saving and retrieving places."""
        repo = InMemoryRepository()

        place = Place(address="Test", geolocation="0;0")
        saved = repo.save(place)

        # Should assign an ID
        assert saved.id is not None

        # Should be retrievable
        retrieved = repo.get_by_id(saved.id)
        assert retrieved is not None
        assert retrieved.address == "Test"

    def test_get_all(self):
        """Test getting all places."""
        repo = InMemoryRepository()

        place1 = Place(address="Place 1", geolocation="0;0")
        place2 = Place(address="Place 2", geolocation="1;1")

        repo.save(place1)
        repo.save(place2)

        all_places = repo.get_all()
        assert len(all_places) == 2

    def test_delete(self):
        """Test deleting a place."""
        repo = InMemoryRepository()

        place = Place(address="Test", geolocation="0;0")
        saved = repo.save(place)

        assert repo.delete(saved.id) is True
        assert repo.get_by_id(saved.id) is None
        assert repo.delete(saved.id) is False  # Already deleted

    def test_query(self):
        """Test querying places."""
        repo = InMemoryRepository()

        place1 = Place(address="Test", geolocation="0;0")
        place2 = Place(address="Other", geolocation="1;1")

        repo.save(place1)
        repo.save(place2)

        results = repo.query({"address": "Test"})
        assert len(results) == 1
        assert results[0].address == "Test"


class TestPlaceEnrichmentService:
    """Test enrichment service."""

    def test_service_creation(self):
        """Test creating an enrichment service."""
        settings = Settings()
        service = PlaceEnrichmentService(settings)

        assert service is not None
        assert len(service.providers) > 0

    def test_service_with_custom_providers(self):
        """Test service with custom provider list."""
        from place_research.providers import HighwayProvider

        settings = Settings()
        providers = [HighwayProvider()]
        service = PlaceEnrichmentService(settings, providers=providers)

        assert len(service.providers) == 1
        assert service.providers[0].name == "highway"

    def test_service_with_repository(self):
        """Test service with repository."""
        settings = Settings()
        repo = InMemoryRepository()
        service = PlaceEnrichmentService(settings, repository=repo)

        assert service.repository is repo

    def test_get_enabled_providers(self):
        """Test getting enabled provider names."""
        settings = Settings()
        service = PlaceEnrichmentService(settings)

        providers = service.get_enabled_providers()
        assert isinstance(providers, list)
        # Highway should always be enabled (no config needed)
        assert "highway" in providers

    def test_get_provider_status(self):
        """Test getting provider status."""
        settings = Settings()
        service = PlaceEnrichmentService(settings)

        status = service.get_provider_status()
        assert isinstance(status, dict)
        assert "highway" in status
        assert status["highway"]["enabled"] is True

    def test_enrich_place_basic(self):
        """Test basic place enrichment."""
        settings = Settings()
        service = PlaceEnrichmentService(settings)

        place = Place(address="Test", geolocation="40.7128;-74.0060")
        result = service.enrich_place(place)

        assert result is not None
        assert isinstance(result, EnrichmentResult)
        # Should have some data or errors
        assert result.highway is not None or len(result.errors) > 0

    def test_enrich_and_save(self):
        """Test enriching and saving a place."""
        settings = Settings()
        repo = InMemoryRepository()
        service = PlaceEnrichmentService(settings, repository=repo)

        place = Place(address="Test", geolocation="40.7128;-74.0060")
        _result = service.enrich_and_save(place)

        # Should have saved to repository
        all_places = repo.get_all()
        assert len(all_places) == 1

    def test_service_without_repository_raises(self):
        """Test that enrich_and_save raises without repository."""
        settings = Settings()
        service = PlaceEnrichmentService(settings)  # No repository

        place = Place(address="Test", geolocation="0;0")

        with pytest.raises(ValueError, match="No repository configured"):
            service.enrich_and_save(place)


class TestAPIRoutes:
    """Test API routes (integration tests)."""

    def test_api_creation(self):
        """Test that the API app can be created."""
        from place_research.api import app

        assert app is not None
        assert app.title == "Place Research API"
        assert app.version == "0.1.0"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
