import pytest
from datetime import datetime, timezone
from unittest.mock import Mock, MagicMock, patch
from sqlalchemy.orm import Session
from app.services.saved_property_service import SavedPropertyService
from app.models.saved_property import SavedProperty

"""Tests for saved property service."""


@pytest.fixture
def mock_db():
    """Create a mock database session."""
    return Mock(spec=Session)


@pytest.fixture
def service(mock_db):
    """Create a SavedPropertyService instance."""
    return SavedPropertyService(mock_db)


@pytest.fixture
def sample_saved_property():
    """Create a sample saved property."""
    return SavedProperty(
        id=1,
        user_id=1,
        property_id=100,
        notes="Test notes",
        rating=5,
        tags="downtown,modern",
        is_favorite=True,
        is_archived=False,
        viewed_in_person=False,
        saved_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


class TestGetSavedProperty:
    def test_get_saved_property_found(self, service, mock_db, sample_saved_property):
        mock_db.query.return_value.filter.return_value.first.return_value = sample_saved_property

        result = service.get_saved_property(user_id=1, property_id=100)

        assert result == sample_saved_property
        mock_db.query.assert_called_once_with(SavedProperty)

    def test_get_saved_property_not_found(self, service, mock_db):
        mock_db.query.return_value.filter.return_value.first.return_value = None

        result = service.get_saved_property(user_id=1, property_id=100)

        assert result is None


class TestGetSavedPropertyById:
    def test_get_saved_property_by_id_found(self, service, mock_db, sample_saved_property):
        mock_db.query.return_value.filter.return_value.first.return_value = sample_saved_property

        result = service.get_saved_property_by_id(saved_property_id=1, user_id=1)

        assert result == sample_saved_property

    def test_get_saved_property_by_id_not_found(self, service, mock_db):
        mock_db.query.return_value.filter.return_value.first.return_value = None

        result = service.get_saved_property_by_id(saved_property_id=1, user_id=1)

        assert result is None


class TestGetUserSavedProperties:
    def test_get_user_saved_properties_default(self, service, mock_db, sample_saved_property):
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.count.return_value = 1
        mock_query.order_by.return_value = mock_query
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = [sample_saved_property]

        result, total = service.get_user_saved_properties(user_id=1)

        assert result == [sample_saved_property]
        assert total == 1

    def test_get_user_saved_properties_with_filters(self, service, mock_db):
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.count.return_value = 0
        mock_query.order_by.return_value = mock_query
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = []

        result, total = service.get_user_saved_properties(
            user_id=1,
            is_favorite=True,
            is_archived=False,
            tags=["downtown"],
            sort_by="rating",
            sort_order="asc",
        )

        assert result == []
        assert total == 0


class TestSaveProperty:
    def test_save_property_success(self, service, mock_db):
        result = service.save_property(
            user_id=1,
            property_id=100,
            notes="Great location",
            rating=5,
            tags="downtown",
            is_favorite=True,
        )

        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()
        mock_db.refresh.assert_called_once()
        assert result.user_id == 1
        assert result.property_id == 100


class TestUpdateSavedProperty:
    def test_update_saved_property_success(self, service, mock_db, sample_saved_property):
        mock_db.query.return_value.filter.return_value.first.return_value = sample_saved_property

        updates = {"notes": "Updated notes", "rating": 4}
        result = service.update_saved_property(saved_property_id=1, user_id=1, updates=updates)

        assert result.notes == "Updated notes"
        assert result.rating == 4
        mock_db.commit.assert_called_once()

    def test_update_saved_property_not_found(self, service, mock_db):
        mock_db.query.return_value.filter.return_value.first.return_value = None

        result = service.update_saved_property(saved_property_id=1, user_id=1, updates={})

        assert result is None
        mock_db.commit.assert_not_called()


class TestDeleteSavedProperty:
    def test_delete_saved_property_success(self, service, mock_db, sample_saved_property):
        mock_db.query.return_value.filter.return_value.first.return_value = sample_saved_property

        result = service.delete_saved_property(saved_property_id=1, user_id=1)

        assert result is True
        mock_db.delete.assert_called_once_with(sample_saved_property)
        mock_db.commit.assert_called_once()

    def test_delete_saved_property_not_found(self, service, mock_db):
        mock_db.query.return_value.filter.return_value.first.return_value = None

        result = service.delete_saved_property(saved_property_id=1, user_id=1)

        assert result is False
        mock_db.delete.assert_not_called()


class TestGetUserStats:
    def test_get_user_stats(self, service, mock_db, sample_saved_property):
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.count.return_value = 5
        mock_query.scalar.return_value = 4.5
        mock_query.order_by.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = [sample_saved_property]

        with patch.object(service, "get_tag_usage", return_value=[{"tag": "downtown", "count": 3}]):
            result = service.get_user_stats(user_id=1)

        assert "total_saved" in result
        assert "total_favorites" in result
        assert "average_rating" in result
        assert "most_used_tags" in result


class TestGetAllTags:
    def test_get_all_tags(self, service, mock_db, sample_saved_property):
        mock_db.query.return_value.filter.return_value.all.return_value = [sample_saved_property]

        result = service.get_all_tags(user_id=1)

        assert len(result) == 2
        assert result[0]["tag"] in ["downtown", "modern"]


class TestBulkOperations:
    def test_bulk_update(self, service, mock_db):
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.update.return_value = 3

        result = service.bulk_update(
            user_id=1, saved_property_ids=[1, 2, 3], updates={"is_archived": True}
        )

        assert result == 3
        mock_db.commit.assert_called_once()

    def test_bulk_delete(self, service, mock_db):
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.delete.return_value = 2

        result = service.bulk_delete(user_id=1, saved_property_ids=[1, 2])

        assert result == 2
        mock_db.commit.assert_called_once()


class TestExtractTagsFromProperties:
    def test_extract_tags_from_properties(self, service, sample_saved_property):
        properties = [sample_saved_property]

        result = service._extract_tags_from_properties(properties)

        assert len(result) == 2
        assert all("tag" in item and "count" in item for item in result)
        assert result[0]["count"] == 1

    def test_extract_tags_empty_list(self, service):
        result = service._extract_tags_from_properties([])

        assert result == []
