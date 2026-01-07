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
