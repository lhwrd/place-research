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
    service.cache_service = mock_cache_service
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


class TestHelperMethods:
    """Tests for helper methods."""

    def test_normalize_address(self, geocoding_service):
        """Test address normalization."""
        address = "123 Main Street  North   Apartment 4"
        normalized = geocoding_service._normalize_address(address)

        assert "  " not in normalized
        assert normalized == "123 main st n apt 4"

    def test_generate_geocode_cache_key(self, geocoding_service):
        """Test cache key generation for geocoding."""
        key = geocoding_service._generate_geocode_cache_key("123 main st")

        assert key.startswith("geocode:")

    def test_generate_geocode_cache_key_with_components(self, geocoding_service):
        """Test cache key generation with components."""
        key = geocoding_service._generate_geocode_cache_key("123 main st", {"country": "US"})

        assert "country=US" in key
