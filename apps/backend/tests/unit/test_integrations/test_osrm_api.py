from unittest.mock import AsyncMock, patch

import pytest

from app.exceptions import OSRMAPIError
from app.integrations.osrm_api import OSRMAPIClient


@pytest.fixture
def osrm_client():
    """Fixture for OSRM API client."""
    return OSRMAPIClient()


@pytest.mark.asyncio
async def test_get_driving_distance_duration_success(osrm_client):
    """Test successful route calculation."""
    mock_response = {
        "routes": [
            {
                "distance": 5432.1,
                "duration": 678.9,
            }
        ]
    }

    with patch.object(osrm_client, "_make_request", new_callable=AsyncMock) as mock_request:
        mock_request.return_value = mock_response

        result = await osrm_client.get_driving_distance_duration(
            start_lat=40.7128, start_lon=-74.0060, end_lat=40.7580, end_lon=-73.9855
        )

        assert result["distance_meters"] == 5432.1
        assert result["duration_seconds"] == 678.9

        mock_request.assert_called_once()
        call_args = mock_request.call_args
        assert call_args[0][0] == "GET"
        assert "route/v1/driving/" in call_args[0][1]
        assert call_args[1]["params"]["overview"] == "false"


@pytest.mark.asyncio
async def test_get_driving_distance_duration_no_routes(osrm_client):
    """Test error handling when no routes returned."""
    mock_response = {}

    with patch.object(osrm_client, "_make_request", new_callable=AsyncMock) as mock_request:
        mock_request.return_value = mock_response

        with pytest.raises(OSRMAPIError, match="Failed to fetch route data from OSRM API"):
            await osrm_client.get_driving_distance_duration(
                start_lat=40.7128, start_lon=-74.0060, end_lat=40.7580, end_lon=-73.9855
            )


@pytest.mark.asyncio
async def test_get_driving_distance_duration_none_response(osrm_client):
    """Test error handling when response is None."""
    with patch.object(osrm_client, "_make_request", new_callable=AsyncMock) as mock_request:
        mock_request.return_value = None

        with pytest.raises(OSRMAPIError, match="Failed to fetch route data from OSRM API"):
            await osrm_client.get_driving_distance_duration(
                start_lat=40.7128, start_lon=-74.0060, end_lat=40.7580, end_lon=-73.9855
            )


def test_get_service_name(osrm_client):
    """Test service name is correctly returned."""
    assert osrm_client._get_service_name() == "osrm"


def test_initialization():
    """Test client initialization with correct parameters."""
    client = OSRMAPIClient()
    assert client.base_url == "http://router.project-osrm.org"
    assert client.timeout == 30.0


@pytest.mark.asyncio
async def test_distance_matrix_success(osrm_client):
    """Test successful distance matrix calculation."""
    origin = (40.7128, -74.0060)
    destinations = [
        (40.7580, -73.9855),
        (40.7489, -73.9680),
    ]

    mock_route_info = {
        "distance_meters": 5432.1,
        "duration_seconds": 678.9,
    }

    with patch.object(
        osrm_client, "get_driving_distance_duration", new_callable=AsyncMock
    ) as mock_get_route:
        mock_get_route.return_value = mock_route_info

        result = await osrm_client.distance_matrix(origin, destinations)

        assert len(result) == 2
        assert result[0]["destination_index"] == 0
        assert result[0]["distance_miles"] == pytest.approx(5432.1 / 1609.34)
        assert result[0]["duration_minutes"] == pytest.approx(678.9 / 60)
        assert result[1]["destination_index"] == 1
        assert result[1]["distance_miles"] == pytest.approx(5432.1 / 1609.34)
        assert result[1]["duration_minutes"] == pytest.approx(678.9 / 60)

        assert mock_get_route.call_count == 2


@pytest.mark.asyncio
async def test_distance_matrix_empty_destinations(osrm_client):
    """Test distance matrix with empty destinations list."""
    origin = (40.7128, -74.0060)
    destinations = []

    result = await osrm_client.distance_matrix(origin, destinations)

    assert result == []


@pytest.mark.asyncio
async def test_distance_matrix_single_destination(osrm_client):
    """Test distance matrix with single destination."""
    origin = (40.7128, -74.0060)
    destinations = [(40.7580, -73.9855)]

    mock_route_info = {
        "distance_meters": 3218.68,
        "duration_seconds": 480.0,
    }

    with patch.object(
        osrm_client, "get_driving_distance_duration", new_callable=AsyncMock
    ) as mock_get_route:
        mock_get_route.return_value = mock_route_info

        result = await osrm_client.distance_matrix(origin, destinations)

        assert len(result) == 1
        assert result[0]["destination_index"] == 0
        assert result[0]["distance_miles"] == pytest.approx(3218.68 / 1609.34)
        assert result[0]["duration_minutes"] == pytest.approx(480.0 / 60)

        mock_get_route.assert_called_once_with(
            start_lat=40.7128, start_lon=-74.0060, end_lat=40.7580, end_lon=-73.9855
        )


@pytest.mark.asyncio
async def test_validate_api_key(osrm_client):
    """Test that validate_api_key always returns True."""
    result = await osrm_client.validate_api_key()
    assert result is True
