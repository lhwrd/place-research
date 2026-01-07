import pytest
from datetime import datetime, timezone
from unittest.mock import Mock, MagicMock
from app.services.user_preference_service import UserPreferenceService
from app.models.user_preference import UserPreference

"""Tests for user preference service."""


@pytest.fixture
def mock_db():
    """Create a mock database session."""
    return Mock()


@pytest.fixture
def service(mock_db):
    """Create a UserPreferenceService instance."""
    return UserPreferenceService(mock_db)


class TestGetPreferences:
    def test_get_preferences_exists(self, service, mock_db):
        """Test getting existing preferences."""
        expected_pref = UserPreference(user_id=1, max_grocery_distance=2.0)
        mock_db.query.return_value.filter.return_value.first.return_value = expected_pref

        result = service.get_preferences(1)

        assert result == expected_pref
        mock_db.query.assert_called_once_with(UserPreference)

    def test_get_preferences_not_exists(self, service, mock_db):
        """Test getting non-existent preferences."""
        mock_db.query.return_value.filter.return_value.first.return_value = None

        result = service.get_preferences(1)

        assert result is None


class TestGetOrCreatePreferences:
    def test_get_or_create_existing(self, service, mock_db):
        """Test get_or_create with existing preferences."""
        existing_pref = UserPreference(user_id=1, max_grocery_distance=2.0)
        mock_db.query.return_value.filter.return_value.first.return_value = existing_pref

        result = service.get_or_create_preferences(1)

        assert result == existing_pref
        mock_db.add.assert_not_called()

    def test_get_or_create_new(self, service, mock_db):
        """Test get_or_create creating new preferences."""
        mock_db.query.return_value.filter.return_value.first.return_value = None

        result = service.get_or_create_preferences(1)

        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()
        mock_db.refresh.assert_called_once()


class TestCreatePreferences:
    def test_create_with_defaults(self, service, mock_db):
        """Test creating preferences with default values."""
        result = service.create_preferences(1)

        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()
        mock_db.refresh.assert_called_once()

        call_args = mock_db.add.call_args[0][0]
        assert call_args.user_id == 1
        assert call_args.max_grocery_distance == 2.0
        assert call_args.max_park_distance == 1.0

    def test_create_with_custom_data(self, service, mock_db):
        """Test creating preferences with custom values."""
        custom_data = {"max_grocery_distance": 5.0, "notify_new_listings": True}

        result = service.create_preferences(1, custom_data)

        call_args = mock_db.add.call_args[0][0]
        assert call_args.max_grocery_distance == 5.0
        assert call_args.notify_new_listings is True
        assert call_args.max_park_distance == 1.0  # Default value


class TestUpdatePreferences:
    def test_update_existing_preferences(self, service, mock_db):
        """Test updating existing preferences."""
        existing_pref = UserPreference(user_id=1, max_grocery_distance=2.0)
        mock_db.query.return_value.filter.return_value.first.return_value = existing_pref

        updates = {"max_grocery_distance": 5.0, "notify_new_listings": True}
        result = service.update_preferences(1, updates)

        assert result.max_grocery_distance == 5.0
        assert result.notify_new_listings is True
        assert isinstance(result.updated_at, datetime)
        mock_db.commit.assert_called_once()

    def test_update_creates_if_not_exists(self, service, mock_db):
        """Test update creates preferences if they don't exist."""
        mock_db.query.return_value.filter.return_value.first.return_value = None

        updates = {"max_grocery_distance": 5.0}
        result = service.update_preferences(1, updates)

        mock_db.add.assert_called_once()

    def test_update_ignores_invalid_fields(self, service, mock_db):
        """Test update ignores fields that don't exist on model."""
        existing_pref = UserPreference(user_id=1)
        mock_db.query.return_value.filter.return_value.first.return_value = existing_pref

        updates = {"invalid_field": "value", "max_grocery_distance": 3.0}
        result = service.update_preferences(1, updates)

        assert not hasattr(result, "invalid_field")
        assert result.max_grocery_distance == 3.0


class TestResetToDefaults:
    def test_reset_to_defaults(self, service, mock_db):
        """Test resetting preferences to defaults."""
        existing_pref = UserPreference(
            user_id=1,
            max_grocery_distance=10.0,
            min_walk_score=50,
            min_bedrooms=3,
            min_price=100000,
        )
        mock_db.query.return_value.filter.return_value.first.return_value = existing_pref

        result = service.reset_to_defaults(1)

        # Check defaults are restored
        assert result.max_grocery_distance == 2.0
        assert result.max_park_distance == 1.0
        assert result.notify_new_listings is False

        # Check optional fields are cleared
        assert result.min_walk_score is None
        assert result.min_bedrooms is None
        assert result.min_price is None

        assert isinstance(result.updated_at, datetime)
        mock_db.commit.assert_called_once()
