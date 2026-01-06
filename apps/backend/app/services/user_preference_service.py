"""User preference service for managing user preferences."""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from app.models.user_preference import UserPreference

logger = logging.getLogger(__name__)


class UserPreferenceService:
    """Service for user preference operations."""

    # Default preference values
    DEFAULTS = {
        "max_grocery_distance": 2.0,
        "max_park_distance": 1.0,
        "max_school_distance": 3.0,
        "max_hospital_distance": 10.0,
        "notify_new_listings": False,
        "notify_price_changes": False,
    }

    def __init__(self, db: Session):
        self.db = db

    def get_preferences(self, user_id: int) -> Optional[UserPreference]:
        """Get user preferences by user ID."""
        return self.db.query(UserPreference).filter(UserPreference.user_id == user_id).first()

    def get_or_create_preferences(self, user_id: int) -> UserPreference:
        """Get user preferences or create with defaults if not exists."""
        preferences = self.get_preferences(user_id)

        if not preferences:
            preferences = self.create_preferences(user_id, self.DEFAULTS)

        return preferences

    def create_preferences(
        self, user_id: int, preference_data: Optional[Dict[str, Any]] = None
    ) -> UserPreference:
        """
        Create user preferences.

        Args:
            user_id: User ID
            preference_data: Optional initial preference values

        Returns:
            Created UserPreference object
        """
        data = self.DEFAULTS.copy()
        if preference_data:
            data.update(preference_data)

        preferences = UserPreference(user_id=user_id, **data)

        self.db.add(preferences)
        self.db.commit()
        self.db.refresh(preferences)

        logger.info(f"Created preferences for user {user_id}")

        return preferences

    def update_preferences(self, user_id: int, updates: Dict[str, Any]) -> UserPreference:
        """
        Update user preferences.

        Args:
            user_id: User ID
            updates: Dictionary of fields to update

        Returns:
            Updated UserPreference object
        """
        preferences = self.get_or_create_preferences(user_id)

        for key, value in updates.items():
            if hasattr(preferences, key):
                setattr(preferences, key, value)

        preferences.updated_at = datetime.now(timezone.utc)

        self.db.commit()
        self.db.refresh(preferences)

        logger.info(f"Updated preferences for user {user_id}")

        return preferences

    def reset_to_defaults(self, user_id: int) -> UserPreference:
        """
        Reset preferences to default values.

        Args:
            user_id: User ID

        Returns:
            Reset UserPreference object
        """
        preferences = self.get_or_create_preferences(user_id)

        # Reset to defaults
        for key, value in self.DEFAULTS.items():
            setattr(preferences, key, value)

        # Clear other fields
        preferences.min_walk_score = None
        preferences.min_bike_score = None
        preferences.min_transit_score = None
        preferences.max_commute_time = None
        preferences.workplace_address = None
        preferences.workplace_latitude = None
        preferences.workplace_longitude = None
        preferences.preferred_amenities = None
        preferences.preferred_places = None
        preferences.min_bedrooms = None
        preferences.min_bathrooms = None
        preferences.min_square_feet = None
        preferences.max_year_built = None
        preferences.preferred_property_types = None
        preferences.min_price = None
        preferences.max_price = None

        preferences.updated_at = datetime.now(timezone.utc)

        self.db.commit()
        self.db.refresh(preferences)

        logger.info(f"Reset preferences to defaults for user {user_id}")

        return preferences

    def has_workplace_configured(self, user_id: int) -> bool:
        """Check if user has workplace location configured."""
        preferences = self.get_preferences(user_id)

        if not preferences:
            return False

        return (
            preferences.workplace_latitude is not None
            and preferences.workplace_longitude is not None
        )

    def get_workplace_location(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Get workplace location if configured."""
        preferences = self.get_preferences(user_id)

        if not preferences or not self.has_workplace_configured(user_id):
            return None

        return {
            "address": preferences.workplace_address,
            "latitude": preferences.workplace_latitude,
            "longitude": preferences.workplace_longitude,
            "max_commute_time": preferences.max_commute_time,
        }
