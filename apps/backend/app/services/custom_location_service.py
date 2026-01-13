"""Custom location service for managing user's important locations."""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import and_, asc, desc
from sqlalchemy.orm import Session

from app.exceptions.base import ConflictError
from app.models.custom_location import CustomLocation

logger = logging.getLogger(__name__)


class CustomLocationService:
    """Service for custom location operations."""

    def __init__(self, db: Session):
        self.db = db

    def get_location_by_id(self, location_id: int, user_id: int) -> Optional[CustomLocation]:
        """Get custom location by ID."""
        return (
            self.db.query(CustomLocation)
            .filter(and_(CustomLocation.id == location_id, CustomLocation.user_id == user_id))
            .first()
        )

    def get_user_locations(
        self,
        user_id: int,
        skip: int = 0,
        limit: int = 100,
        is_active: Optional[bool] = None,
        location_type: Optional[str] = None,
        sort_by: str = "priority",
        sort_order: str = "desc",
    ) -> Tuple[List[CustomLocation], int]:
        """
        Get all custom locations for a user with filtering and sorting.

        Returns:
            Tuple of (list of locations, total count)
        """
        query = self.db.query(CustomLocation).filter(CustomLocation.user_id == user_id)

        # Apply filters
        if is_active is not None:
            query = query.filter(CustomLocation.is_active == is_active)

        if location_type:
            query = query.filter(CustomLocation.location_type == location_type)

        # Get total count before pagination
        total = query.count()

        # Apply sorting
        sort_field = getattr(CustomLocation, sort_by, CustomLocation.priority)
        if sort_order.lower() == "desc":
            query = query.order_by(desc(sort_field))
        else:
            query = query.order_by(asc(sort_field))

        # Apply pagination
        locations = query.offset(skip).limit(limit).all()

        return locations, total

    def create_location(self, user_id: int, location_data: Dict[str, Any]) -> CustomLocation:
        """Create a new custom location."""
        # Check for duplicate address
        address = location_data.get("address")
        if address:
            existing_location = (
                self.db.query(CustomLocation)
                .filter(
                    and_(
                        CustomLocation.user_id == user_id,
                        CustomLocation.address == address,
                    )
                )
                .first()
            )
            if existing_location:
                raise ConflictError(
                    f"A custom location with address '{address}' already exists",
                    details={"existing_location_id": existing_location.id},
                )

        custom_location = CustomLocation(user_id=user_id, **location_data)

        self.db.add(custom_location)
        self.db.commit()
        self.db.refresh(custom_location)

        logger.info(f"Created custom location for user {user_id}:  {custom_location.name}")

        return custom_location

    def update_location(
        self, location_id: int, user_id: int, updates: Dict[str, Any]
    ) -> Optional[CustomLocation]:
        """Update a custom location."""
        custom_location = self.get_location_by_id(location_id, user_id)

        if not custom_location:
            return None

        for key, value in updates.items():
            if hasattr(custom_location, key):
                setattr(custom_location, key, value)

        custom_location.updated_at = datetime.now(timezone.utc)

        self.db.commit()
        self.db.refresh(custom_location)

        return custom_location

    def delete_location(self, location_id: int, user_id: int) -> bool:
        """Delete a custom location."""
        custom_location = self.get_location_by_id(location_id, user_id)

        if not custom_location:
            return False

        self.db.delete(custom_location)
        self.db.commit()

        logger.info(f"Deleted custom location {location_id} for user {user_id}")

        return True

    def get_locations_by_type(self, user_id: int) -> Dict[str, List[CustomLocation]]:
        """Get locations grouped by type."""
        locations = (
            self.db.query(CustomLocation)
            .filter(CustomLocation.user_id == user_id)
            .order_by(desc(CustomLocation.priority))
            .all()
        )

        grouped = {"family": [], "friend": [], "work": [], "other": []}

        for loc in locations:
            location_type = loc.location_type or "other"
            if location_type in grouped:
                grouped[location_type].append(loc)

        return grouped

    def get_user_stats(self, user_id: int) -> Dict[str, Any]:
        """Get statistics about user's custom locations."""
        total_locations = (
            self.db.query(CustomLocation).filter(CustomLocation.user_id == user_id).count()
        )

        active_locations = (
            self.db.query(CustomLocation)
            .filter(and_(CustomLocation.user_id == user_id, CustomLocation.is_active))
            .count()
        )

        # Count by type
        type_counts = {}
        for location_type in ["family", "friend", "work", "other"]:
            count = (
                self.db.query(CustomLocation)
                .filter(
                    and_(
                        CustomLocation.user_id == user_id,
                        CustomLocation.location_type == location_type,
                    )
                )
                .count()
            )
            type_counts[location_type] = count

        # Recently added
        recent_locations = (
            self.db.query(CustomLocation)
            .filter(CustomLocation.user_id == user_id)
            .order_by(desc(CustomLocation.created_at))
            .limit(5)
            .all()
        )

        return {
            "total_locations": total_locations,
            "active_locations": active_locations,
            "inactive_locations": total_locations - active_locations,
            "by_type": type_counts,
            "recently_added": recent_locations,
        }

    def bulk_update(self, user_id: int, location_ids: List[int], updates: Dict[str, Any]) -> int:
        """Bulk update multiple custom locations."""
        count = (
            self.db.query(CustomLocation)
            .filter(
                and_(
                    CustomLocation.user_id == user_id,
                    CustomLocation.id.in_(location_ids),
                )
            )
            .update(updates, synchronize_session=False)
        )

        self.db.commit()

        return count

    def bulk_delete(self, user_id: int, location_ids: List[int]) -> int:
        """Bulk delete multiple custom locations."""
        count = (
            self.db.query(CustomLocation)
            .filter(
                and_(
                    CustomLocation.user_id == user_id,
                    CustomLocation.id.in_(location_ids),
                )
            )
            .delete(synchronize_session=False)
        )

        self.db.commit()

        logger.info(f"User {user_id} bulk deleted {count} locations")

        return count
