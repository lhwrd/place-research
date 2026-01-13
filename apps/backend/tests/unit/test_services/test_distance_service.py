from unittest.mock import AsyncMock, patch

import pytest

from app.services.distance_service import DistanceService


@pytest.fixture
def distance_service():
    """Fixture for DistanceService instance."""
    return DistanceService()


@pytest.fixture
def mock_osrm_api():
    """Fixture for mocked OSRM API client."""
    with patch("app.services.distance_service.OSRMAPIClient") as mock:
        yield mock


@pytest.mark.asyncio
async def test_calculate_distances_success(distance_service, mock_osrm_api):
    """Test successful distance calculation."""
    # Arrange
    origin_lat = 40.7128
    origin_lon = -74.0060
    destinations = [(34.0522, -118.2437), (41.8781, -87.6298)]
    expected_results = [
        {"distance": 3936.0, "duration": 14129.0},
        {"distance": 1145.0, "duration": 4122.0},
    ]

    mock_instance = AsyncMock()
    mock_instance.distance_matrix.return_value = expected_results
    mock_osrm_api.return_value = mock_instance

    service = DistanceService()

    # Act
    results = await service.calculate_distances(origin_lat, origin_lon, destinations)

    # Assert
    assert results == expected_results
    mock_instance.distance_matrix.assert_called_once_with(
        origin=(origin_lat, origin_lon), destinations=destinations
    )


@pytest.mark.asyncio
async def test_calculate_distances_empty_destinations(distance_service, mock_osrm_api):
    """Test distance calculation with empty destinations list."""
    # Arrange
    origin_lat = 40.7128
    origin_lon = -74.0060
    destinations = []
    expected_results = []

    mock_instance = AsyncMock()
    mock_instance.distance_matrix.return_value = expected_results
    mock_osrm_api.return_value = mock_instance

    service = DistanceService()

    # Act
    results = await service.calculate_distances(origin_lat, origin_lon, destinations)

    # Assert
    assert results == expected_results
    mock_instance.distance_matrix.assert_called_once_with(
        origin=(origin_lat, origin_lon), destinations=destinations
    )


@pytest.mark.asyncio
async def test_calculate_distances_single_destination(distance_service, mock_osrm_api):
    """Test distance calculation with single destination."""
    # Arrange
    origin_lat = 40.7128
    origin_lon = -74.0060
    destinations = [(34.0522, -118.2437)]
    expected_results = [{"distance": 3936.0, "duration": 14129.0}]

    mock_instance = AsyncMock()
    mock_instance.distance_matrix.return_value = expected_results
    mock_osrm_api.return_value = mock_instance

    service = DistanceService()

    # Act
    results = await service.calculate_distances(origin_lat, origin_lon, destinations)

    # Assert
    assert results == expected_results
    assert len(results) == 1
