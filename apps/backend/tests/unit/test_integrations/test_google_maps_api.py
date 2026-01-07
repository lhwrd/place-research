from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.exceptions import GoogleMapsAPIError

"""Tests for Google Maps API integration."""


@pytest.fixture
def google_maps_api():
    """Create GoogleMapsAPI instance."""
    # Import the real google maps module to patch its settings reference
    from tests.unit.test_integrations import conftest

    real_module = conftest._real_module

    # Patch the settings in the real module
    with patch.object(real_module, "settings") as mock_settings:
        mock_settings.google_maps_api_key = "test_api_key"

        # Import GoogleMapsAPI here to get the unmocked version from the autouse fixture
        from app.integrations.google_maps_api import GoogleMapsAPI

        return GoogleMapsAPI()


@pytest.fixture
def mock_geocode_response():
    """Mock successful geocode response."""
    return {
        "status": "OK",
        "results": [
            {
                "formatted_address": "1600 Amphitheatre Parkway, Mountain View, CA 94043, USA",
                "geometry": {"location": {"lat": 37.4224764, "lng": -122.0842499}},
                "place_id": "ChIJ2eUgeAK6j4ARbn5u_wAGqWA",
                "address_components": [
                    {"types": ["locality"], "long_name": "Mountain View"},
                    {"types": ["administrative_area_level_1"], "short_name": "CA"},
                    {"types": ["postal_code"], "long_name": "94043"},
                    {
                        "types": ["administrative_area_level_2"],
                        "long_name": "Santa Clara County",
                    },
                    {"types": ["country"], "long_name": "United States"},
                ],
            }
        ],
    }


@pytest.fixture
def mock_distance_matrix_response():
    """Mock successful distance matrix response."""
    return {
        "status": "OK",
        "rows": [
            {
                "elements": [
                    {
                        "status": "OK",
                        "distance": {"value": 8369, "text": "5.2 mi"},
                        "duration": {"value": 720, "text": "12 mins"},
                        "duration_in_traffic": {"value": 1080, "text": "18 mins"},
                    },
                    {
                        "status": "OK",
                        "distance": {"value": 16093, "text": "10.0 mi"},
                        "duration": {"value": 1200, "text": "20 mins"},
                    },
                ]
            }
        ],
    }


@pytest.fixture
def mock_directions_response():
    """Mock successful directions response."""
    return {
        "status": "OK",
        "routes": [
            {
                "legs": [
                    {
                        "distance": {"value": 8369, "text": "5.2 mi"},
                        "duration": {"value": 720, "text": "12 mins"},
                        "start_address": "Origin Address",
                        "end_address": "Destination Address",
                        "steps": [
                            {
                                "html_instructions": "Head north on Main St",
                                "distance": {"text": "0.5 mi"},
                                "duration": {"text": "2 mins"},
                            },
                            {
                                "html_instructions": "Turn right onto 1st Ave",
                                "distance": {"text": "1.2 mi"},
                                "duration": {"text": "3 mins"},
                            },
                        ],
                    }
                ],
                "overview_polyline": {"points": "encoded_polyline_string"},
            }
        ],
    }


class TestGoogleMapsAPIInit:
    """Test GoogleMapsAPI initialization."""

    def test_init_with_settings(self, google_maps_api):
        """Test initialization with settings."""
        assert google_maps_api.base_url == "https://maps.googleapis.com/maps/api"
        assert google_maps_api.api_key == "test_api_key"
        assert google_maps_api.timeout == 30.0
        assert google_maps_api.rate_limit_per_second == 50

    def test_get_service_name(self, google_maps_api):
        """Test service name."""
        assert google_maps_api._get_service_name() == "google_maps"

    def test_get_auth_headers(self, google_maps_api):
        """Test auth headers are empty."""
        assert google_maps_api._get_auth_headers() == {}


class TestValidateAPIKey:
    """Test API key validation."""

    @pytest.mark.asyncio
    async def test_validate_api_key_success(self, google_maps_api, mock_geocode_response):
        """Test successful API key validation."""
        google_maps_api._make_request = AsyncMock(return_value=mock_geocode_response)

        result = await google_maps_api.validate_api_key()

        assert result is True

    @pytest.mark.asyncio
    async def test_validate_api_key_failure(self, google_maps_api):
        """Test failed API key validation."""
        google_maps_api._make_request = AsyncMock(
            side_effect=GoogleMapsAPIError("Invalid API key", api_status_code=403)
        )

        result = await google_maps_api.validate_api_key()

        assert result is False


class TestGeocode:
    """Test geocoding functionality."""

    @pytest.mark.asyncio
    async def test_geocode_success(self, google_maps_api, mock_geocode_response):
        """Test successful geocoding."""
        google_maps_api._make_request = AsyncMock(return_value=mock_geocode_response)

        result = await google_maps_api.geocode("1600 Amphitheatre Parkway")

        assert result is not None
        assert (
            result["formatted_address"] == "1600 Amphitheatre Parkway, Mountain View, CA 94043, USA"
        )
        assert result["latitude"] == 37.4224764
        assert result["longitude"] == -122.0842499
        assert result["city"] == "Mountain View"
        assert result["state"] == "CA"
        assert result["zip_code"] == "94043"

    @pytest.mark.asyncio
    async def test_geocode_with_components(self, google_maps_api, mock_geocode_response):
        """Test geocoding with component filters."""
        google_maps_api._make_request = AsyncMock(return_value=mock_geocode_response)

        result = await google_maps_api.geocode(
            "Main Street", components={"country": "US", "postal_code": "98101"}
        )

        google_maps_api._make_request.assert_called_once()
        call_params = google_maps_api._make_request.call_args[1]["params"]
        assert "components" in call_params
        assert "country:US" in call_params["components"]
        assert "postal_code:98101" in call_params["components"]

    @pytest.mark.asyncio
    async def test_geocode_zero_results(self, google_maps_api):
        """Test geocoding with no results."""
        google_maps_api._make_request = AsyncMock(
            return_value={"status": "ZERO_RESULTS", "results": []}
        )

        result = await google_maps_api.geocode("Invalid Address XYZ123")

        assert result is None

    @pytest.mark.asyncio
    async def test_geocode_error(self, google_maps_api):
        """Test geocoding error."""
        google_maps_api._make_request = AsyncMock(
            return_value={
                "status": "REQUEST_DENIED",
                "error_message": "Invalid API key",
            }
        )

        with pytest.raises(GoogleMapsAPIError, match="Geocoding failed"):
            await google_maps_api.geocode("Address")


class TestReverseGeocode:
    """Test reverse geocoding functionality."""

    @pytest.mark.asyncio
    async def test_reverse_geocode_success(self, google_maps_api, mock_geocode_response):
        """Test successful reverse geocoding."""
        google_maps_api._make_request = AsyncMock(return_value=mock_geocode_response)

        result = await google_maps_api.reverse_geocode(37.4224764, -122.0842499)

        assert result is not None
        assert (
            result["formatted_address"] == "1600 Amphitheatre Parkway, Mountain View, CA 94043, USA"
        )
        assert result["latitude"] == 37.4224764
        assert result["longitude"] == -122.0842499

    @pytest.mark.asyncio
    async def test_reverse_geocode_no_results(self, google_maps_api):
        """Test reverse geocoding with no results."""
        google_maps_api._make_request = AsyncMock(
            return_value={"status": "ZERO_RESULTS", "results": []}
        )

        result = await google_maps_api.reverse_geocode(0.0, 0.0)

        assert result is None


class TestDistanceMatrix:
    """Test distance matrix functionality."""

    @pytest.mark.asyncio
    async def test_distance_matrix_success(self, google_maps_api, mock_distance_matrix_response):
        """Test successful distance matrix calculation."""
        google_maps_api._make_request = AsyncMock(return_value=mock_distance_matrix_response)

        origin = (47.6062, -122.3321)
        destinations = [(47.6097, -122.3331), (47.6205, -122.3493)]

        results = await google_maps_api.distance_matrix(origin, destinations)

        assert len(results) == 2
        assert results[0]["destination_index"] == 0
        assert results[0]["distance_miles"] == 5.2
        assert results[0]["duration_minutes"] == 12
        assert results[0]["duration_in_traffic_minutes"] == 18
        assert results[0]["status"] == "OK"

    @pytest.mark.asyncio
    async def test_distance_matrix_with_departure_time(
        self, google_maps_api, mock_distance_matrix_response
    ):
        """Test distance matrix with departure time."""
        google_maps_api._make_request = AsyncMock(return_value=mock_distance_matrix_response)

        origin = (47.6062, -122.3321)
        destinations = [(47.6097, -122.3331)]
        departure_time = datetime(2024, 1, 15, 8, 0, 0)

        await google_maps_api.distance_matrix(origin, destinations, departure_time=departure_time)

        call_params = google_maps_api._make_request.call_args[1]["params"]
        assert "departure_time" in call_params
        assert call_params["departure_time"] == int(departure_time.timestamp())

    @pytest.mark.asyncio
    async def test_distance_matrix_unreachable_destination(self, google_maps_api):
        """Test distance matrix with unreachable destination."""
        response = {
            "status": "OK",
            "rows": [
                {
                    "elements": [
                        {"status": "ZERO_RESULTS"},
                    ]
                }
            ],
        }
        google_maps_api._make_request = AsyncMock(return_value=response)

        origin = (47.6062, -122.3321)
        destinations = [(0.0, 0.0)]

        results = await google_maps_api.distance_matrix(origin, destinations)

        assert len(results) == 1
        assert results[0]["status"] == "ZERO_RESULTS"
        assert "error" in results[0]

    @pytest.mark.asyncio
    async def test_distance_matrix_api_error(self, google_maps_api):
        """Test distance matrix API error."""
        google_maps_api._make_request = AsyncMock(
            return_value={
                "status": "REQUEST_DENIED",
                "error_message": "Invalid request",
            }
        )

        with pytest.raises(GoogleMapsAPIError, match="Distance matrix failed"):
            await google_maps_api.distance_matrix((0, 0), [(1, 1)])


class TestGetDirections:
    """Test directions functionality."""

    @pytest.mark.asyncio
    async def test_get_directions_success(self, google_maps_api, mock_directions_response):
        """Test successful directions retrieval."""
        google_maps_api._make_request = AsyncMock(return_value=mock_directions_response)

        origin = (47.6062, -122.3321)
        destination = (47.6097, -122.3331)

        result = await google_maps_api.get_directions(origin, destination)

        assert result["distance_miles"] == 5.2
        assert result["duration_minutes"] == 12
        assert result["start_address"] == "Origin Address"
        assert result["end_address"] == "Destination Address"
        assert len(result["steps"]) == 2
        assert result["polyline"] == "encoded_polyline_string"

    @pytest.mark.asyncio
    async def test_get_directions_with_alternatives(
        self, google_maps_api, mock_directions_response
    ):
        """Test directions with alternatives enabled."""
        google_maps_api._make_request = AsyncMock(return_value=mock_directions_response)

        origin = (47.6062, -122.3321)
        destination = (47.6097, -122.3331)

        await google_maps_api.get_directions(origin, destination, alternatives=True)

        call_params = google_maps_api._make_request.call_args[1]["params"]
        assert call_params["alternatives"] == "true"

    @pytest.mark.asyncio
    async def test_get_directions_no_routes(self, google_maps_api):
        """Test directions with no routes found."""
        google_maps_api._make_request = AsyncMock(return_value={"status": "OK", "routes": []})

        result = await google_maps_api.get_directions((0, 0), (1, 1))

        assert result == {}

    @pytest.mark.asyncio
    async def test_get_directions_api_error(self, google_maps_api):
        """Test directions API error."""
        google_maps_api._make_request = AsyncMock(
            return_value={"status": "NOT_FOUND", "error_message": "Route not found"}
        )

        with pytest.raises(GoogleMapsAPIError, match="Directions failed"):
            await google_maps_api.get_directions((0, 0), (1, 1))
