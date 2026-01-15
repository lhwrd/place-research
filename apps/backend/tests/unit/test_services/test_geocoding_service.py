from unittest.mock import AsyncMock, MagicMock

import pytest

from app.exceptions import GeocodingFailedError, InvalidAddressError
from app.services.geocoding_service import GeocodingService

"""Tests for geocoding service."""


@pytest.fixture
def mock_cache_service():
    """Mock cache service."""
    mock = AsyncMock()
    mock.get = AsyncMock(return_value=None)
    mock.set = AsyncMock()
    return mock


@pytest.fixture
def mock_google_maps_api():
    """Mock Google Maps API."""
    mock = AsyncMock()
    mock.geocode = AsyncMock()
    mock.reverse_geocode = AsyncMock()
    mock._calculate_distance = MagicMock(return_value=10.5)
    return mock


@pytest.fixture
def geocoding_service(mock_cache_service, mock_google_maps_api):
    """Create geocoding service with mocked dependencies."""
    service = GeocodingService()
    service._cache_service = mock_cache_service
    service.maps_api = mock_google_maps_api
    return service


@pytest.fixture
def sample_geocode_result():
    """Sample geocoding result."""
    return {
        "formatted_address": "1600 Amphitheatre Pkwy, Mountain View, CA 94043, USA",
        "latitude": 37.4224764,
        "longitude": -122.0842499,
        "place_id": "ChIJ2eUgeAK6j4ARbn5u_wAGqWA",
        "city": "Mountain View",
        "state": "CA",
        "zip_code": "94043",
        "county": "Santa Clara County",
        "country": "United States",
    }


class TestGeocodeAddress:
    """Tests for geocode_address method."""

    @pytest.mark.asyncio
    async def test_geocode_address_success(
        self, geocoding_service, mock_google_maps_api, sample_geocode_result
    ):
        """Test successful address geocoding."""
        mock_google_maps_api.geocode.return_value = sample_geocode_result

        result = await geocoding_service.geocode_address(
            "1600 Amphitheatre Parkway, Mountain View, CA"
        )

        assert result == sample_geocode_result
        assert result["latitude"] == 37.4224764
        assert result["longitude"] == -122.0842499

    @pytest.mark.asyncio
    async def test_geocode_address_with_cache_hit(
        self, geocoding_service, mock_cache_service, sample_geocode_result
    ):
        """Test geocoding returns cached result."""
        mock_cache_service.get.return_value = sample_geocode_result

        result = await geocoding_service.geocode_address("1600 Amphitheatre Parkway")

        assert result == sample_geocode_result
        mock_cache_service.get.assert_called_once()

    @pytest.mark.asyncio
    async def test_geocode_address_caches_result(
        self,
        geocoding_service,
        mock_cache_service,
        mock_google_maps_api,
        sample_geocode_result,
    ):
        """Test geocoding caches API result."""
        mock_google_maps_api.geocode.return_value = sample_geocode_result

        await geocoding_service.geocode_address("1600 Amphitheatre Parkway")

        mock_cache_service.set.assert_called_once()

    @pytest.mark.asyncio
    async def test_geocode_address_skip_cache(
        self,
        geocoding_service,
        mock_cache_service,
        mock_google_maps_api,
        sample_geocode_result,
    ):
        """Test geocoding with cache disabled."""
        mock_google_maps_api.geocode.return_value = sample_geocode_result

        result = await geocoding_service.geocode_address("123 Main St", use_cache=False)

        assert result == sample_geocode_result
        mock_cache_service.get.assert_not_called()
        mock_cache_service.set.assert_not_called()

    @pytest.mark.asyncio
    async def test_geocode_address_with_components(
        self, geocoding_service, mock_google_maps_api, sample_geocode_result
    ):
        """Test geocoding with component filters."""
        mock_google_maps_api.geocode.return_value = sample_geocode_result
        components = {"country": "US"}

        result = await geocoding_service.geocode_address("123 Main St", components=components)

        mock_google_maps_api.geocode.assert_called_once()
        assert result == sample_geocode_result

    @pytest.mark.asyncio
    async def test_geocode_address_too_short(self, geocoding_service):
        """Test geocoding fails with short address."""
        with pytest.raises(InvalidAddressError):
            await geocoding_service.geocode_address("123")

    @pytest.mark.asyncio
    async def test_geocode_address_empty(self, geocoding_service):
        """Test geocoding fails with empty address."""
        with pytest.raises(InvalidAddressError):
            await geocoding_service.geocode_address("")

    @pytest.mark.asyncio
    async def test_geocode_address_api_returns_none(self, geocoding_service, mock_google_maps_api):
        """Test geocoding fails when API returns None."""
        mock_google_maps_api.geocode.return_value = None

        with pytest.raises(GeocodingFailedError):
            await geocoding_service.geocode_address("123 Main Street")

    @pytest.mark.asyncio
    async def test_geocode_address_api_exception(self, geocoding_service, mock_google_maps_api):
        """Test geocoding handles API exceptions."""
        mock_google_maps_api.geocode.side_effect = Exception("API Error")

        with pytest.raises(GeocodingFailedError):
            await geocoding_service.geocode_address("123 Main Street")


class TestReverseGeocode:
    """Tests for reverse_geocode method."""

    @pytest.mark.asyncio
    async def test_reverse_geocode_success(
        self, geocoding_service, mock_google_maps_api, sample_geocode_result
    ):
        """Test successful reverse geocoding."""
        mock_google_maps_api.reverse_geocode.return_value = sample_geocode_result

        result = await geocoding_service.reverse_geocode(37.4224764, -122.0842499)

        assert result == sample_geocode_result

    @pytest.mark.asyncio
    async def test_reverse_geocode_with_cache_hit(
        self, geocoding_service, mock_cache_service, sample_geocode_result
    ):
        """Test reverse geocoding returns cached result."""
        mock_cache_service.get.return_value = sample_geocode_result

        result = await geocoding_service.reverse_geocode(37.4224764, -122.0842499)

        assert result == sample_geocode_result
        mock_cache_service.get.assert_called_once()

    @pytest.mark.asyncio
    async def test_reverse_geocode_invalid_latitude(self, geocoding_service):
        """Test reverse geocoding fails with invalid latitude."""
        result = await geocoding_service.reverse_geocode(91.0, -122.0)

        assert result is None

    @pytest.mark.asyncio
    async def test_reverse_geocode_invalid_longitude(self, geocoding_service):
        """Test reverse geocoding fails with invalid longitude."""
        result = await geocoding_service.reverse_geocode(37.0, -181.0)

        assert result is None

    @pytest.mark.asyncio
    async def test_reverse_geocode_api_exception(self, geocoding_service, mock_google_maps_api):
        """Test reverse geocoding handles API exceptions."""
        mock_google_maps_api.reverse_geocode.side_effect = Exception("API Error")

        result = await geocoding_service.reverse_geocode(37.4224764, -122.0842499)

        assert result is None


class TestGeocodeBatch:
    """Tests for geocode_batch method."""

    @pytest.mark.asyncio
    async def test_geocode_batch_success(
        self, geocoding_service, mock_google_maps_api, sample_geocode_result
    ):
        """Test batch geocoding success."""
        mock_google_maps_api.geocode.return_value = sample_geocode_result
        addresses = ["123 Main St", "456 Oak Ave"]

        results = await geocoding_service.geocode_batch(addresses)

        assert len(results) == 2
        assert all(r == sample_geocode_result for r in results)

    @pytest.mark.asyncio
    async def test_geocode_batch_partial_failure(
        self, geocoding_service, mock_google_maps_api, sample_geocode_result
    ):
        """Test batch geocoding with partial failures."""
        mock_google_maps_api.geocode.side_effect = [
            sample_geocode_result,
            Exception("API Error"),
        ]
        addresses = ["123 Main St", "Invalid"]

        results = await geocoding_service.geocode_batch(addresses)

        assert len(results) == 2
        assert results[0] == sample_geocode_result
        assert results[1] is None


class TestValidateAddress:
    """Tests for validate_address method."""

    @pytest.mark.asyncio
    async def test_validate_address_valid(
        self, geocoding_service, mock_google_maps_api, sample_geocode_result
    ):
        """Test address validation for valid address."""
        mock_google_maps_api.geocode.return_value = sample_geocode_result

        result = await geocoding_service.validate_address(
            "1600 Amphitheatre Parkway, Mountain View, CA"
        )

        assert result["valid"] is True
        assert result["formatted_address"] == sample_geocode_result["formatted_address"]
        assert result["components_complete"] is True

    @pytest.mark.asyncio
    async def test_validate_address_strict_mode(
        self, geocoding_service, mock_google_maps_api, sample_geocode_result
    ):
        """Test strict address validation."""
        mock_google_maps_api.geocode.return_value = sample_geocode_result

        result = await geocoding_service.validate_address("1600 Amphitheatre Parkway", strict=True)

        assert "valid" in result

    @pytest.mark.asyncio
    async def test_validate_address_exception(self, geocoding_service, mock_google_maps_api):
        """Test address validation handles exceptions."""
        mock_google_maps_api.geocode.side_effect = Exception("API Error")

        result = await geocoding_service.validate_address("123 Main St")

        assert result["valid"] is False
        assert "error" in result


class TestGeocodeComponents:
    """Tests for geocode_components method."""

    @pytest.mark.asyncio
    async def test_geocode_components_success(
        self, geocoding_service, mock_google_maps_api, sample_geocode_result
    ):
        """Test geocoding with components."""
        mock_google_maps_api.geocode.return_value = sample_geocode_result

        result = await geocoding_service.geocode_components(
            street="1600 Amphitheatre Parkway",
            city="Mountain View",
            state="CA",
            zip_code="94043",
        )

        assert result == sample_geocode_result

    @pytest.mark.asyncio
    async def test_geocode_components_no_components(self, geocoding_service):
        """Test geocoding fails with no components."""
        result = await geocoding_service.geocode_components()

        assert result is None


class TestGetDistanceBetweenAddresses:
    """Tests for get_distance_between_addresses method."""

    @pytest.mark.asyncio
    async def test_get_distance_success(
        self, geocoding_service, mock_google_maps_api, sample_geocode_result
    ):
        """Test distance calculation between addresses."""
        mock_google_maps_api.geocode.return_value = sample_geocode_result

        result = await geocoding_service.get_distance_between_addresses("Address 1", "Address 2")

        assert result is not None
        assert "distance_miles" in result
        assert result["distance_miles"] == 10.5

    @pytest.mark.asyncio
    async def test_get_distance_exception(self, geocoding_service, mock_google_maps_api):
        """Test distance calculation handles exceptions."""
        mock_google_maps_api.geocode.side_effect = Exception("API Error")

        result = await geocoding_service.get_distance_between_addresses("Address 1", "Address 2")

        assert result is None


class TestHelperMethods:
    """Tests for helper methods."""

    def test_normalize_address(self, geocoding_service):
        """Test address normalization."""
        address = "123 Main Street  North   Apartment 4"
        normalized = geocoding_service._normalize_address(address)

        assert "  " not in normalized
        assert normalized == "123 main st n apt 4"

    def test_validate_coordinates_valid(self, geocoding_service):
        """Test coordinate validation for valid coordinates."""
        assert geocoding_service._validate_coordinates(37.4224764, -122.0842499) is True

    def test_validate_coordinates_invalid_lat(self, geocoding_service):
        """Test coordinate validation for invalid latitude."""
        assert geocoding_service._validate_coordinates(91.0, -122.0) is False

    def test_validate_coordinates_invalid_lon(self, geocoding_service):
        """Test coordinate validation for invalid longitude."""
        assert geocoding_service._validate_coordinates(37.0, -181.0) is False

    def test_generate_geocode_cache_key(self, geocoding_service):
        """Test cache key generation for geocoding."""
        key = geocoding_service._generate_geocode_cache_key("123 main st")

        assert key.startswith("geocode:")

    def test_generate_geocode_cache_key_with_components(self, geocoding_service):
        """Test cache key generation with components."""
        key = geocoding_service._generate_geocode_cache_key("123 main st", {"country": "US"})

        assert "country=US" in key

    def test_generate_reverse_geocode_cache_key(self, geocoding_service):
        """Test cache key generation for reverse geocoding."""
        key = geocoding_service._generate_reverse_geocode_cache_key(37.4224764, -122.0842499)

        assert key == "reverse_geocode:37.4224764:-122.0842499"

    def test_normalize_address_string(self, geocoding_service):
        """Test public normalize address string method."""
        result = geocoding_service.normalize_address_string("123 Main Street")

        assert result == "123 main st"
