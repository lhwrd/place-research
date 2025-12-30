"""Tests for error handling and validation.

This module tests the custom exceptions, validation functions, and error handling
in the API and service layers.
"""

import pytest
from fastapi.testclient import TestClient

from place_research.exceptions import (
    PlaceResearchError,
    ValidationError,
    InvalidGeolocationError,
    InvalidCoordinatesError,
    MissingConfigError,
    ProviderAPIError,
    ProviderTimeoutError,
    PlaceNotFoundError,
    EnrichmentError,
    RateLimitError,
)
from place_research.validation import (
    validate_geolocation,
    validate_coordinates,
    validate_address,
    validate_provider_name,
    sanitize_error_message,
)
from place_research.api import create_app


class TestExceptions:
    """Test custom exception classes."""

    def test_base_exception(self):
        """Test PlaceResearchError base class."""
        exc = PlaceResearchError(
            message="Test error", error_code="TEST_ERROR", details={"key": "value"}
        )

        assert exc.message == "Test error"
        assert exc.error_code == "TEST_ERROR"
        assert exc.details == {"key": "value"}

        # Test to_dict
        error_dict = exc.to_dict()
        assert error_dict["error"] == "TEST_ERROR"
        assert error_dict["message"] == "Test error"
        assert error_dict["details"]["key"] == "value"

    def test_validation_error(self):
        """Test ValidationError."""
        exc = ValidationError("Invalid input", field="test_field", value="bad_value")

        assert exc.error_code == "VALIDATION_ERROR"
        assert "test_field" in exc.details["field"]
        assert "bad_value" in exc.details["value"]

    def test_invalid_geolocation_error(self):
        """Test InvalidGeolocationError."""
        exc = InvalidGeolocationError("not-valid")

        assert exc.error_code == "VALIDATION_ERROR"
        assert "geolocation" in exc.details["field"]
        assert "not-valid" in exc.details["value"]

    def test_invalid_coordinates_error(self):
        """Test InvalidCoordinatesError."""
        exc = InvalidCoordinatesError(100, -74)

        assert exc.error_code == "VALIDATION_ERROR"
        assert "100;-74" in exc.details["value"]

    def test_missing_config_error(self):
        """Test MissingConfigError."""
        exc = MissingConfigError("API_KEY", provider="TestProvider")

        assert exc.error_code == "CONFIGURATION_ERROR"
        assert exc.details["missing_key"] == "API_KEY"
        assert exc.details["provider"] == "TestProvider"

    def test_provider_api_error(self):
        """Test ProviderAPIError."""
        exc = ProviderAPIError(
            provider_name="TestProvider",
            api_name="Test API",
            status_code=500,
            original_error="Server error",
        )

        assert exc.error_code == "PROVIDER_API_ERROR"
        assert exc.provider_name == "TestProvider"
        assert exc.details["api"] == "Test API"
        assert exc.details["status_code"] == 500

    def test_provider_timeout_error(self):
        """Test ProviderTimeoutError."""
        exc = ProviderTimeoutError("TestProvider", timeout_seconds=30.0)

        assert exc.error_code == "PROVIDER_TIMEOUT"
        assert exc.details["timeout_seconds"] == 30.0

    def test_place_not_found_error(self):
        """Test PlaceNotFoundError."""
        exc = PlaceNotFoundError("abc-123")

        assert exc.error_code == "PLACE_NOT_FOUND"
        assert exc.details["place_id"] == "abc-123"

    def test_enrichment_error(self):
        """Test EnrichmentError."""
        exc = EnrichmentError("All failed", place_id="abc-123")

        assert exc.error_code == "ENRICHMENT_ERROR"
        assert exc.details["reason"] == "All failed"
        assert exc.details["place_id"] == "abc-123"

    def test_rate_limit_error(self):
        """Test RateLimitError."""
        exc = RateLimitError(limit=100, window_seconds=3600, retry_after=1800)

        assert exc.error_code == "RATE_LIMIT_EXCEEDED"
        assert exc.details["limit"] == 100
        assert exc.details["window_seconds"] == 3600
        assert exc.details["retry_after_seconds"] == 1800


class TestValidation:
    """Test validation functions."""

    def test_validate_geolocation_valid(self):
        """Test valid geolocation strings."""
        lat, lng = validate_geolocation("40.7128;-74.0060")
        assert lat == 40.7128
        assert lng == -74.0060

        # With spaces
        lat, lng = validate_geolocation(" 37.7749 ; -122.4194 ")
        assert lat == 37.7749
        assert lng == -122.4194

    def test_validate_geolocation_invalid_format(self):
        """Test invalid geolocation formats."""
        with pytest.raises(InvalidGeolocationError):
            validate_geolocation("40.7128,-74.0060")  # Comma instead of semicolon

        with pytest.raises(InvalidGeolocationError):
            validate_geolocation("40.7128")  # Missing longitude

        with pytest.raises(InvalidGeolocationError):
            validate_geolocation("40.7128;-74.0060;100")  # Too many parts

        with pytest.raises(InvalidGeolocationError):
            validate_geolocation("forty;-seventy")  # Non-numeric

    def test_validate_geolocation_invalid_range(self):
        """Test geolocation with out-of-range coordinates."""
        with pytest.raises(InvalidCoordinatesError):
            validate_geolocation("100;-74")  # Latitude > 90

        with pytest.raises(InvalidCoordinatesError):
            validate_geolocation("40;200")  # Longitude > 180

    def test_validate_coordinates_valid(self):
        """Test valid coordinates."""
        lat, lng = validate_coordinates(40.7128, -74.0060)
        assert lat == 40.7128
        assert lng == -74.0060

        # Edge cases
        lat, lng = validate_coordinates(90, 180)
        assert lat == 90
        assert lng == 180

        lat, lng = validate_coordinates(-90, -180)
        assert lat == -90
        assert lng == -180

    def test_validate_coordinates_invalid(self):
        """Test invalid coordinates."""
        with pytest.raises(InvalidCoordinatesError):
            validate_coordinates(91, -74)  # Latitude too high

        with pytest.raises(InvalidCoordinatesError):
            validate_coordinates(-91, -74)  # Latitude too low

        with pytest.raises(InvalidCoordinatesError):
            validate_coordinates(40, 181)  # Longitude too high

        with pytest.raises(InvalidCoordinatesError):
            validate_coordinates(40, -181)  # Longitude too low

    def test_validate_address_valid(self):
        """Test valid addresses."""
        address = validate_address("1600 Amphitheatre Parkway, Mountain View, CA")
        assert address == "1600 Amphitheatre Parkway, Mountain View, CA"

        # With extra whitespace
        address = validate_address("  123   Main   St  ")
        assert address == "123 Main St"

        # None is allowed
        assert validate_address(None) is None

    def test_validate_address_invalid(self):
        """Test invalid addresses."""
        with pytest.raises(ValidationError) as exc:
            validate_address("AB")  # Too short
        assert "too short" in exc.value.message.lower()

        with pytest.raises(ValidationError) as exc:
            validate_address("x" * 501)  # Too long
        assert "too long" in exc.value.message.lower()

    def test_validate_provider_name_valid(self):
        """Test valid provider names."""
        assert validate_provider_name("walkbikescore") == "walkbikescore"
        assert validate_provider_name("WalkBikeScore") == "walkbikescore"  # Normalized
        assert validate_provider_name("air_quality") == "air_quality"

    def test_validate_provider_name_invalid(self):
        """Test invalid provider names."""
        with pytest.raises(ValidationError):
            validate_provider_name("")  # Empty

        with pytest.raises(ValidationError):
            validate_provider_name("walk-score")  # Hyphen not allowed

        with pytest.raises(ValidationError):
            validate_provider_name("walk.score")  # Dot not allowed

    def test_sanitize_error_message(self):
        """Test error message sanitization."""
        # Remove API keys
        msg = sanitize_error_message("Error: api_key=sk_abc123")
        assert "api_key=***" in msg
        assert "sk_abc123" not in msg

        # Remove tokens
        msg = sanitize_error_message("Failed: token='bearer_xyz789'")
        assert "token=***" in msg
        assert "bearer_xyz789" not in msg

        # Remove passwords
        msg = sanitize_error_message("Auth failed: password=secret123")
        assert "password=***" in msg
        assert "secret123" not in msg

        # Truncate long messages
        long_msg = "x" * 1000
        msg = sanitize_error_message(long_msg, max_length=100)
        assert len(msg) <= 100
        assert msg.endswith("...")


class TestAPIErrorHandling:
    """Test error handling in API endpoints."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        app = create_app()
        return TestClient(app)

    def test_enrich_missing_data(self, client):
        """Test enrichment with missing data."""
        response = client.post("/enrich", json={})

        assert response.status_code == 400
        data = response.json()
        # Response has either 'error' or 'detail' field
        assert "error" in data or "detail" in data

    def test_enrich_invalid_coordinates(self, client):
        """Test enrichment with invalid coordinates."""
        response = client.post(
            "/enrich", json={"latitude": 100, "longitude": -74}  # Invalid
        )

        assert response.status_code == 422
        data = response.json()
        assert data["error"] == "VALIDATION_ERROR"

    def test_enrich_partial_coordinates(self, client):
        """Test enrichment with only latitude or only longitude."""
        # Only latitude
        response = client.post("/enrich", json={"latitude": 40.7128})
        assert response.status_code == 400

        # Only longitude
        response = client.post("/enrich", json={"longitude": -74.0060})
        assert response.status_code == 400

    def test_pydantic_validation_error_format(self, client):
        """Test that Pydantic validation errors are formatted correctly."""
        response = client.post(
            "/enrich", json={"latitude": "not-a-number", "longitude": -74}
        )

        assert response.status_code == 422
        data = response.json()
        assert data["error"] == "VALIDATION_ERROR"
        assert "errors" in data["details"]
        assert isinstance(data["details"]["errors"], list)

    def test_health_endpoint_no_errors(self, client):
        """Test that health endpoint doesn't raise errors."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"

    def test_providers_endpoint_no_errors(self, client):
        """Test that providers endpoint doesn't raise errors."""
        response = client.get("/providers")
        assert response.status_code == 200
        data = response.json()
        assert "enabled_providers" in data
        assert "provider_details" in data


class TestServiceErrorHandling:
    """Test error handling in service layer."""

    async def test_enrich_with_no_providers(self, monkeypatch):
        """Test enrichment when no providers are available."""
        from place_research.config import Settings
        from place_research.service import PlaceEnrichmentService
        from place_research.models.place import Place

        # Mock Google Maps to avoid API calls in tests
        def mock_geocode(_address):
            return [
                {
                    "geometry": {"location": {"lat": 40.0, "lng": -74.0}},
                    "address_components": [],
                }
            ]

        # Create service with no enabled providers (empty settings)
        settings = Settings()
        service = PlaceEnrichmentService(settings, providers=[])

        # Mock the Google Maps client
        import googlemaps

        monkeypatch.setattr(
            googlemaps.Client, "geocode", lambda self, addr: mock_geocode(addr)
        )

        place = Place(address="1600 Amphitheatre Parkway, Mountain View, CA")

        # With no providers, enrichment should succeed but return empty result
        result = await service.enrich_place(place)

        # Result should have no provider data
        assert result.walk_bike_score is None
        assert result.air_quality is None
        assert len(result.errors) == 0  # No errors if no providers run

    def test_enrich_without_location_data(self):
        """Test enrichment without location data."""
        # Place model requires address field, so this will fail during Place creation
        # This is working as expected - Pydantic validates required fields
        from pydantic_core import ValidationError as PydanticValidationError

        with pytest.raises(PydanticValidationError):
            from place_research.models.place import Place

            Place()  # Missing required address field


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
