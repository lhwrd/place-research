from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import status

from app.schemas.custom_location import CustomLocationResponse, LocationTypeEnum

"""Tests for custom locations endpoints."""


@pytest.fixture
def mock_location_service():
    """Mock CustomLocationService."""
    with patch("app.api.v1.endpoints.locations.CustomLocationService") as mock:
        yield mock


@pytest.fixture
def mock_geocoding_service():
    """Mock GeocodingService."""
    with patch("app.api.v1.endpoints.locations.GeocodingService") as mock:
        yield mock


@pytest.fixture
def mock_distance_service():
    """Mock DistanceService."""
    with patch("app.api.v1.endpoints.locations.DistanceService") as mock:
        yield mock


@pytest.fixture
def mock_property_service():
    """Mock PropertyService."""
    with patch("app.api.v1.endpoints.locations.PropertyService") as mock:
        yield mock


@pytest.fixture
def sample_location():
    """Sample custom location data."""
    import datetime

    return CustomLocationResponse(
        id=1,
        user_id=1,
        name="Mom's House",
        description="Family home",
        address="123 Main St, City, State 12345",
        latitude=40.7128,
        longitude=-74.0060,
        city="City",
        state="State",
        zip_code="12345",
        location_type=LocationTypeEnum.FAMILY,
        priority=80,
        is_active=True,
        created_at=datetime.datetime.now(datetime.timezone.utc),
        updated_at=datetime.datetime.now(datetime.timezone.utc),
    )


class TestGetCustomLocations:
    """Tests for GET /api/v1/locations endpoint."""

    def test_get_custom_locations_success(
        self, client, test_user, auth_headers, mock_location_service, sample_location
    ):
        """Test successful retrieval of custom locations."""
        mock_service_instance = mock_location_service.return_value
        mock_service_instance.get_user_locations.return_value = ([sample_location], 1)

        response = client.get("/api/v1/locations", headers=auth_headers)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["total"] == 1
        assert len(data["items"]) == 1
        assert data["items"][0]["name"] == "Mom's House"

    def test_get_custom_locations_with_filters(
        self, client, test_user, auth_headers, mock_location_service
    ):
        """Test filtering locations by status and type."""
        mock_service_instance = mock_location_service.return_value
        mock_service_instance.get_user_locations.return_value = ([], 0)

        response = client.get(
            "/api/v1/locations",
            params={"is_active": True, "location_type": "family", "sort_by": "name"},
            headers=auth_headers,
        )

        assert response.status_code == status.HTTP_200_OK
        mock_service_instance.get_user_locations.assert_called_once()


class TestCreateCustomLocation:
    """Tests for POST /api/v1/locations endpoint."""

    def test_create_location_with_address(
        self,
        client,
        test_user,
        auth_headers,
        mock_location_service,
        mock_geocoding_service,
        sample_location,
    ):
        """Test creating location with address (geocoding)."""
        mock_geocoding_instance = mock_geocoding_service.return_value
        mock_geocoding_instance.geocode_address = AsyncMock(
            return_value={
                "formatted_address": "123 Main St, City, State 12345",
                "latitude": 40.7128,
                "longitude": -74.0060,
                "city": "City",
                "state": "State",
                "zip_code": "12345",
            }
        )

        mock_service_instance = mock_location_service.return_value
        mock_service_instance.create_location.return_value = sample_location

        location_data = {
            "name": "Mom's House",
            "address": "123 Main St, City, State",
            "location_type": "family",
        }

        response = client.post("/api/v1/locations", json=location_data, headers=auth_headers)

        assert response.status_code == status.HTTP_201_CREATED
        assert response.json()["name"] == "Mom's House"

    def test_create_location_with_coordinates(
        self, client, test_user, auth_headers, mock_location_service, sample_location
    ):
        """Test creating location with direct coordinates."""
        mock_service_instance = mock_location_service.return_value
        mock_service_instance.create_location.return_value = sample_location

        location_data = {
            "name": "Friend's Place",
            "latitude": 40.7128,
            "longitude": -74.0060,
        }

        response = client.post("/api/v1/locations", json=location_data, headers=auth_headers)

        assert response.status_code == status.HTTP_201_CREATED

    def test_create_location_without_address_or_coords(
        self, client, test_user, auth_headers, mock_location_service
    ):
        """Test error when neither address nor coordinates provided."""
        location_data = {"name": "Invalid Location"}

        response = client.post("/api/v1/locations", json=location_data, headers=auth_headers)

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "address or latitude/longitude" in response.json()["detail"]

    def test_create_location_geocoding_failure(
        self, client, test_user, auth_headers, mock_geocoding_service
    ):
        """Test handling of geocoding failure."""
        mock_geocoding_instance = mock_geocoding_service.return_value
        mock_geocoding_instance.geocode_address = AsyncMock(
            side_effect=Exception("Geocoding failed")
        )

        location_data = {"name": "Test", "address": "Invalid Address"}

        response = client.post("/api/v1/locations", json=location_data, headers=auth_headers)

        assert response.status_code == status.HTTP_400_BAD_REQUEST


class TestGetCustomLocation:
    """Tests for GET /api/v1/locations/{location_id} endpoint."""

    def test_get_location_by_id_success(
        self, client, test_user, auth_headers, mock_location_service, sample_location
    ):
        """Test successful retrieval of location by ID."""
        mock_service_instance = mock_location_service.return_value
        mock_service_instance.get_location_by_id.return_value = sample_location

        response = client.get("/api/v1/locations/1", headers=auth_headers)

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["id"] == 1

    def test_get_location_not_found(self, client, test_user, auth_headers, mock_location_service):
        """Test error when location not found."""
        mock_service_instance = mock_location_service.return_value
        mock_service_instance.get_location_by_id.return_value = None

        response = client.get("/api/v1/locations/999", headers=auth_headers)

        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestUpdateCustomLocation:
    """Tests for PUT /api/v1/locations/{location_id} endpoint."""

    def test_update_location_success(
        self, client, test_user, auth_headers, mock_location_service, sample_location
    ):
        """Test successful location update."""
        mock_service_instance = mock_location_service.return_value
        mock_service_instance.update_location.return_value = sample_location

        update_data = {"name": "Updated Name", "priority": 90}

        response = client.put("/api/v1/locations/1", json=update_data, headers=auth_headers)

        assert response.status_code == status.HTTP_200_OK

    def test_update_location_with_address(
        self,
        client,
        test_user,
        auth_headers,
        mock_location_service,
        mock_geocoding_service,
        sample_location,
    ):
        """Test updating location with new address."""
        mock_geocoding_instance = mock_geocoding_service.return_value
        mock_geocoding_instance.geocode_address = AsyncMock(
            return_value={
                "formatted_address": "456 New St",
                "latitude": 41.0,
                "longitude": -75.0,
            }
        )

        mock_service_instance = mock_location_service.return_value
        mock_service_instance.update_location.return_value = sample_location

        response = client.put(
            "/api/v1/locations/1", json={"address": "456 New St"}, headers=auth_headers
        )

        assert response.status_code == status.HTTP_200_OK


class TestDeleteCustomLocation:
    """Tests for DELETE /api/v1/locations/{location_id} endpoint."""

    def test_delete_location_success(self, client, test_user, auth_headers, mock_location_service):
        """Test successful location deletion."""
        mock_service_instance = mock_location_service.return_value
        mock_service_instance.delete_location.return_value = True

        response = client.delete("/api/v1/locations/1", headers=auth_headers)

        assert response.status_code == status.HTTP_204_NO_CONTENT

    def test_delete_location_not_found(
        self, client, test_user, auth_headers, mock_location_service
    ):
        """Test error when deleting non-existent location."""
        mock_service_instance = mock_location_service.return_value
        mock_service_instance.delete_location.return_value = False

        response = client.delete("/api/v1/locations/999", headers=auth_headers)

        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestToggleLocationActive:
    """Tests for PATCH /api/v1/locations/{location_id}/activate endpoint."""

    def test_toggle_active_success(
        self, client, test_user, auth_headers, mock_location_service, sample_location
    ):
        """Test toggling location active status."""
        mock_service_instance = mock_location_service.return_value
        mock_service_instance.update_location.return_value = sample_location

        response = client.patch(
            "/api/v1/locations/1/activate?is_active=false", headers=auth_headers
        )

        assert response.status_code == status.HTTP_200_OK


class TestCalculateDistanceFromLocation:
    """Tests for GET /api/v1/locations/distance-from/{location_id} endpoint."""

    def test_calculate_distance_success(
        self,
        client,
        test_user,
        auth_headers,
        mock_location_service,
        mock_geocoding_service,
        mock_distance_service,
        sample_location,
    ):
        """Test successful distance calculation."""
        mock_service_instance = mock_location_service.return_value
        mock_service_instance.get_location_by_id.return_value = sample_location

        mock_geocoding_instance = mock_geocoding_service.return_value
        mock_geocoding_instance.geocode_address = AsyncMock(
            return_value={
                "formatted_address": "789 Dest St",
                "latitude": 41.0,
                "longitude": -75.0,
            }
        )

        mock_distance_instance = mock_distance_service.return_value
        mock_distance_instance.calculate_distances = AsyncMock(
            return_value=[
                {
                    "distance_miles": 10.5,
                    "driving_time_minutes": 20,
                }
            ]
        )

        response = client.get(
            "/api/v1/locations/distance-from/1?address=789 Dest St",
            headers=auth_headers,
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["distance_miles"] == 10.5


class TestGetDistancesToProperty:
    """Tests for GET /api/v1/locations/distances-to-property/{property_id} endpoint."""

    def test_get_distances_to_property_success(
        self,
        client,
        test_user,
        auth_headers,
        mock_location_service,
        mock_property_service,
        mock_distance_service,
        sample_location,
    ):
        """Test getting distances to property."""
        mock_property_instance = mock_property_service.return_value
        mock_property_instance.get_property_by_id = AsyncMock(
            return_value=MagicMock(
                id=1,
                latitude=40.0,
                longitude=-74.0,
            )
        )

        mock_service_instance = mock_location_service.return_value
        mock_service_instance.get_user_locations.return_value = ([sample_location], 1)

        mock_distance_instance = mock_distance_service.return_value
        mock_distance_instance.calculate_distances = AsyncMock(
            return_value=[
                {
                    "location_id": 1,
                    "distance_miles": 5.0,
                    "driving_time_minutes": 10,
                }
            ]
        )

        response = client.get("/api/v1/locations/distances-to-property/1", headers=auth_headers)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 1


class TestBulkOperations:
    """Tests for bulk operations endpoints."""

    def test_bulk_activate_locations(self, client, test_user, auth_headers, mock_location_service):
        """Test bulk activation of locations."""
        mock_service_instance = mock_location_service.return_value
        mock_service_instance.bulk_update.return_value = 3

        response = client.post(
            "/api/v1/locations/bulk/activate?is_active=true",
            json=[1, 2, 3],
            headers=auth_headers,
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["count"] == 3

    def test_bulk_delete_locations(self, client, test_user, auth_headers, mock_location_service):
        """Test bulk deletion of locations."""
        mock_service_instance = mock_location_service.return_value
        mock_service_instance.bulk_delete.return_value = 2

        response = client.post("/api/v1/locations/bulk/delete", json=[1, 2], headers=auth_headers)

        assert response.status_code == status.HTTP_204_NO_CONTENT


class TestImportLocations:
    """Tests for POST /api/v1/locations/import endpoint."""

    def test_import_locations_success(
        self,
        client,
        test_user,
        auth_headers,
        mock_location_service,
        mock_geocoding_service,
        sample_location,
    ):
        """Test successful import of multiple locations."""
        mock_geocoding_instance = mock_geocoding_service.return_value
        mock_geocoding_instance.geocode_address = AsyncMock(
            return_value={
                "formatted_address": "123 Main St",
                "latitude": 40.7128,
                "longitude": -74.0060,
            }
        )

        mock_service_instance = mock_location_service.return_value
        mock_service_instance.create_location.return_value = sample_location

        locations_data = [
            {"name": "Location 1", "address": "123 Main St"},
            {"name": "Location 2", "latitude": 40.0, "longitude": -74.0},
        ]

        response = client.post(
            "/api/v1/locations/import", json=locations_data, headers=auth_headers
        )

        assert response.status_code == status.HTTP_200_OK
