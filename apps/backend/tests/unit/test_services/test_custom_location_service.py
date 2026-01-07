from datetime import datetime, timezone
from unittest.mock import MagicMock, Mock, patch

import pytest

from app.models.custom_location import CustomLocation
from app.services.custom_location_service import CustomLocationService

"""Tests for custom location service."""


@pytest.fixture
def mock_db():
    """Mock database session."""
    return Mock()


@pytest.fixture
def service(mock_db):
    """Create CustomLocationService instance with mock db."""
    return CustomLocationService(mock_db)


@pytest.fixture
def sample_location():
    """Sample custom location."""
    location = CustomLocation(
        id=1,
        user_id=100,
        name="Home",
        location_type="family",
        latitude=40.7128,
        longitude=-74.0060,
        priority=10,
        is_active=True,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    return location


class TestGetLocationById:
    def test_get_location_by_id_success(self, service, mock_db, sample_location):
        mock_query = Mock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value.first.return_value = sample_location

        result = service.get_location_by_id(1, 100)

        assert result == sample_location
        mock_db.query.assert_called_once_with(CustomLocation)

    def test_get_location_by_id_not_found(self, service, mock_db):
        mock_query = Mock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value.first.return_value = None

        result = service.get_location_by_id(999, 100)

        assert result is None


class TestGetUserLocations:
    def test_get_user_locations_default(self, service, mock_db, sample_location):
        mock_query = Mock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.count.return_value = 1
        mock_query.order_by.return_value = mock_query
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value.all.return_value = [sample_location]

        locations, total = service.get_user_locations(100)

        assert len(locations) == 1
        assert total == 1
        assert locations[0] == sample_location

    def test_get_user_locations_with_filters(self, service, mock_db, sample_location):
        mock_query = Mock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.count.return_value = 1
        mock_query.order_by.return_value = mock_query
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value.all.return_value = [sample_location]

        locations, total = service.get_user_locations(100, is_active=True, location_type="family")

        assert len(locations) == 1
        assert total == 1

    def test_get_user_locations_pagination(self, service, mock_db):
        mock_query = Mock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.count.return_value = 50
        mock_query.order_by.return_value = mock_query
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value.all.return_value = []

        locations, total = service.get_user_locations(100, skip=10, limit=20)

        mock_query.offset.assert_called_once_with(10)
        mock_query.limit.assert_called_once_with(20)
        assert total == 50


class TestCreateLocation:
    def test_create_location_success(self, service, mock_db):
        location_data = {
            "name": "Office",
            "location_type": "work",
            "latitude": 40.7580,
            "longitude": -73.9855,
            "priority": 8,
        }

        with patch.object(CustomLocation, "__init__", return_value=None):
            mock_location = Mock(spec=CustomLocation)
            mock_location.name = "Office"

            with patch(
                "app.services.custom_location_service.CustomLocation",
                return_value=mock_location,
            ):
                result = service.create_location(100, location_data)

                mock_db.add.assert_called_once()
                mock_db.commit.assert_called_once()
                mock_db.refresh.assert_called_once()


class TestUpdateLocation:
    def test_update_location_success(self, service, mock_db, sample_location):
        service.get_location_by_id = Mock(return_value=sample_location)
        updates = {"name": "New Home", "priority": 15}

        result = service.update_location(1, 100, updates)

        assert result.name == "New Home"
        assert result.priority == 15
        mock_db.commit.assert_called_once()
        mock_db.refresh.assert_called_once()

    def test_update_location_not_found(self, service, mock_db):
        service.get_location_by_id = Mock(return_value=None)
        updates = {"name": "New Name"}

        result = service.update_location(999, 100, updates)

        assert result is None
        mock_db.commit.assert_not_called()


class TestDeleteLocation:
    def test_delete_location_success(self, service, mock_db, sample_location):
        service.get_location_by_id = Mock(return_value=sample_location)

        result = service.delete_location(1, 100)

        assert result is True
        mock_db.delete.assert_called_once_with(sample_location)
        mock_db.commit.assert_called_once()

    def test_delete_location_not_found(self, service, mock_db):
        service.get_location_by_id = Mock(return_value=None)

        result = service.delete_location(999, 100)

        assert result is False
        mock_db.delete.assert_not_called()


class TestGetLocationsByType:
    def test_get_locations_by_type(self, service, mock_db):
        locations = [
            Mock(location_type="family", priority=10),
            Mock(location_type="work", priority=8),
            Mock(location_type="friend", priority=5),
            Mock(location_type=None, priority=3),
        ]

        mock_query = Mock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value.all.return_value = locations

        result = service.get_locations_by_type(100)

        assert "family" in result
        assert "work" in result
        assert "friend" in result
        assert "other" in result
        assert len(result["family"]) == 1
        assert len(result["other"]) == 1


class TestGetUserStats:
    def test_get_user_stats(self, service, mock_db, sample_location):
        mock_query = Mock()
        mock_filter = Mock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_filter
        mock_filter.count.side_effect = [10, 8, 2, 3, 1, 4]
        mock_filter.order_by.return_value.limit.return_value.all.return_value = [sample_location]

        result = service.get_user_stats(100)

        assert result["total_locations"] == 10
        assert result["active_locations"] == 8
        assert result["inactive_locations"] == 2
        assert "by_type" in result
        assert "recently_added" in result


class TestBulkUpdate:
    def test_bulk_update(self, service, mock_db):
        mock_query = Mock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value.update.return_value = 3

        count = service.bulk_update(100, [1, 2, 3], {"is_active": False})

        assert count == 3
        mock_db.commit.assert_called_once()


class TestBulkDelete:
    def test_bulk_delete(self, service, mock_db):
        mock_query = Mock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value.delete.return_value = 5

        count = service.bulk_delete(100, [1, 2, 3, 4, 5])

        assert count == 5
        mock_db.commit.assert_called_once()
