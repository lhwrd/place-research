"""Tests for user preferences endpoints."""

from datetime import datetime, timezone
from unittest.mock import Mock, patch

import pytest
from fastapi import HTTPException, status

from app.api.v1.endpoints.user_preferences import (
    create_preferences,
    get_preferences,
    get_preferences_summary,
    reset_preferences,
    set_preferred_amenities,
    update_amenity_distances,
    update_preferences,
    update_walkability_preferences,
)
from app.models.user import User
from app.schemas.user_preference import (
    AmenityPreferencesUpdate,
    UserPreferenceCreate,
    UserPreferenceUpdate,
)


@pytest.fixture
def mock_user():
    """Mock current user."""
    user = Mock(spec=User)
    user.id = 1
    user.email = "test@example.com"
    return user


@pytest.fixture
def mock_preferences():
    """Mock user preferences object with all required fields."""
    return Mock(
        id=1,
        user_id=1,
        min_walk_score=70,
        min_bike_score=60,
        min_transit_score=50,
        max_grocery_distance=2.0,
        max_park_distance=1.0,
        max_school_distance=3.0,
        max_hospital_distance=5.0,
        max_commute_time=30,
        min_bedrooms=2,
        min_bathrooms=1.0,
        min_square_feet=1000,
        max_year_built=2020,
        min_price=200000,
        max_price=500000,
        preferred_amenities=["grocery_store", "park"],
        preferred_places=["Downtown"],
        preferred_property_types=["Single Family"],
        notify_new_listings=True,
        notify_price_changes=True,
        created_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        updated_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
    )


@pytest.fixture
def mock_preference_service(mock_preferences):
    """Mock UserPreferenceService."""
    with patch("app.api.v1.endpoints.user_preferences.UserPreferenceService") as mock:
        service = Mock()
        service.get_or_create_preferences.return_value = mock_preferences
        service.get_preferences.return_value = mock_preferences
        service.create_preferences.return_value = mock_preferences
        service.update_preferences.return_value = mock_preferences
        service.reset_to_defaults.return_value = None
        mock.return_value = service
        yield service


class TestGetPreferences:
    """Tests for GET /api/v1/user-preferences endpoint."""

    async def test_get_preferences_success(
        self, mock_user, mock_preference_service, mock_preferences
    ):
        """Test successfully getting user preferences."""

        mock_db = Mock()

        result = await get_preferences(current_user=mock_user, db=mock_db)

        assert result is not None
        mock_preference_service.get_or_create_preferences.assert_called_once_with(mock_user.id)


class TestCreatePreferences:
    """Tests for POST /api/v1/user-preferences endpoint."""

    async def test_create_preferences_success(
        self, mock_user, mock_preference_service, mock_preferences
    ):
        """Test successfully creating user preferences."""

        mock_db = Mock()
        mock_preference_service.get_preferences.return_value = None

        preference_data = UserPreferenceCreate(min_walk_score=80)

        result = await create_preferences(preference_data, mock_user, mock_db)

        assert result is not None
        mock_preference_service.create_preferences.assert_called_once()

    async def test_create_preferences_already_exist(
        self, mock_user, mock_preference_service, mock_preferences
    ):
        """Test creating preferences when they already exist."""

        mock_db = Mock()
        mock_preference_service.get_preferences.return_value = mock_preferences

        preference_data = UserPreferenceCreate(min_walk_score=80)

        with pytest.raises(HTTPException) as exc_info:
            await create_preferences(preference_data, mock_user, mock_db)

        assert exc_info.value.status_code == status.HTTP_409_CONFLICT


class TestUpdatePreferences:
    """Tests for PUT /api/v1/user-preferences endpoint."""

    async def test_update_preferences_success(
        self, mock_user, mock_preference_service, mock_preferences
    ):
        """Test successfully updating user preferences."""

        mock_db = Mock()

        preference_data = UserPreferenceUpdate(min_walk_score=90)

        result = await update_preferences(preference_data, mock_user, mock_db)

        assert result is not None
        mock_preference_service.update_preferences.assert_called_once()


class TestUpdateWalkabilityPreferences:
    """Tests for PATCH /api/v1/user-preferences/walkability endpoint."""

    async def test_update_walkability_valid_scores(
        self, mock_user, mock_preference_service, mock_preferences
    ):
        """Test updating walkability with valid scores."""

        mock_db = Mock()

        result = await update_walkability_preferences(
            min_walk_score=80,
            min_bike_score=70,
            min_transit_score=60,
            current_user=mock_user,
            db=mock_db,
        )

        assert result is not None
        mock_preference_service.update_preferences.assert_called_once()

    async def test_update_walkability_invalid_walk_score(self, mock_user):
        """Test updating walkability with invalid walk score."""

        mock_db = Mock()

        with pytest.raises(HTTPException) as exc_info:
            await update_walkability_preferences(
                min_walk_score=150, current_user=mock_user, db=mock_db
            )

        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST

    async def test_update_walkability_invalid_bike_score(self, mock_user):
        """Test updating walkability with invalid bike score."""

        mock_db = Mock()

        with pytest.raises(HTTPException) as exc_info:
            await update_walkability_preferences(
                min_bike_score=-10, current_user=mock_user, db=mock_db
            )

        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST


class TestUpdateAmenityDistances:
    """Tests for PATCH /api/v1/user-preferences/amenity-distances endpoint."""

    async def test_update_amenity_distances_success(
        self, mock_user, mock_preference_service, mock_preferences
    ):
        """Test successfully updating amenity distances."""

        mock_db = Mock()

        amenity_prefs = AmenityPreferencesUpdate(max_grocery_distance=2.5)

        result = await update_amenity_distances(amenity_prefs, mock_user, mock_db)

        assert result is not None
        mock_preference_service.update_preferences.assert_called_once()

    async def test_update_amenity_distances_negative_value(self, mock_user):
        """Test updating amenity distances with negative value raises validation error."""

        # Pydantic validation should catch this at schema level
        with pytest.raises(Exception):  # Will be a pydantic ValidationError
            AmenityPreferencesUpdate(max_grocery_distance=-1.0)


class TestSetPreferredAmenities:
    """Tests for PUT /api/v1/user-preferences/preferred-amenities endpoint."""

    async def test_set_preferred_amenities_valid(
        self, mock_user, mock_preference_service, mock_preferences
    ):
        """Test setting valid preferred amenities."""

        mock_db = Mock()

        amenities = ["grocery_store", "park", "school"]

        result = await set_preferred_amenities(amenities, mock_user, mock_db)

        assert result is not None
        mock_preference_service.update_preferences.assert_called_once()

    async def test_set_preferred_amenities_invalid(self, mock_user):
        """Test setting invalid preferred amenities."""

        mock_db = Mock()

        amenities = ["grocery_store", "invalid_amenity"]

        with pytest.raises(HTTPException) as exc_info:
            await set_preferred_amenities(amenities, mock_user, mock_db)

        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST


class TestResetPreferences:
    """Tests for DELETE /api/v1/user-preferences endpoint."""

    async def test_reset_preferences_success(self, mock_user, mock_preference_service):
        """Test successfully resetting preferences."""

        mock_db = Mock()

        result = await reset_preferences(mock_user, mock_db)

        assert result is None
        mock_preference_service.reset_to_defaults.assert_called_once_with(mock_user.id)


class TestGetPreferencesSummary:
    """Tests for GET /api/v1/user-preferences/summary endpoint."""

    async def test_get_preferences_summary_success(
        self, mock_user, mock_preference_service, mock_preferences
    ):
        """Test successfully getting preferences summary."""

        mock_db = Mock()

        result = await get_preferences_summary(mock_user, mock_db)

        assert result is not None
        assert "walkability" in result
        assert "amenity_distances" in result
        assert "property_criteria" in result
        assert "preferred_amenities" in result
        assert "notifications" in result
