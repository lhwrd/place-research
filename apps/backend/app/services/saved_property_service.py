"""Saved property service for managing saved properties."""

import logging
from collections import Counter
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import and_, asc, desc, func, or_
from sqlalchemy.orm import Session

from app.models.saved_property import SavedProperty

logger = logging.getLogger(__name__)


class SavedPropertyService:
    """Service for saved property operations."""

    def __init__(self, db: Session):
        self.db = db

    def get_saved_property(self, user_id: int, property_id: int) -> Optional[SavedProperty]:
        """Check if a property is saved by user."""
        return (
            self.db.query(SavedProperty)
            .filter(
                and_(
                    SavedProperty.user_id == user_id,
                    SavedProperty.property_id == property_id,
                )
            )
            .first()
        )

    def get_saved_property_by_id(
        self, saved_property_id: int, user_id: int
    ) -> Optional[SavedProperty]:
        """Get saved property by ID."""
        return (
            self.db.query(SavedProperty)
            .filter(
                and_(
                    SavedProperty.id == saved_property_id,
                    SavedProperty.user_id == user_id,
                )
            )
            .first()
        )

    def get_user_saved_properties(
        self,
        user_id: int,
        skip: int = 0,
        limit: int = 100,
        is_favorite: Optional[bool] = None,
        is_archived: Optional[bool] = None,
        tags: Optional[List[str]] = None,
        sort_by: str = "saved_at",
        sort_order: str = "desc",
    ) -> Tuple[List[SavedProperty], int]:
        """
        Get all saved properties for a user with filtering and sorting.

        Returns:
            Tuple of (list of saved properties, total count)
        """
        query = self.db.query(SavedProperty).filter(SavedProperty.user_id == user_id)

        # Apply filters
        if is_favorite is not None:
            query = query.filter(SavedProperty.is_favorite == is_favorite)

        if is_archived is not None:
            query = query.filter(SavedProperty.is_archived == is_archived)
        else:
            # By default, exclude archived unless explicitly requested
            query = query.filter(~SavedProperty.is_archived)

        if tags:
            # Filter by any of the provided tags
            tag_filters = [SavedProperty.tags.contains(tag) for tag in tags]
            query = query.filter(or_(*tag_filters))

        # Get total count before pagination
        total = query.count()

        # Apply sorting
        sort_field = getattr(SavedProperty, sort_by, SavedProperty.saved_at)
        if sort_order.lower() == "desc":
            query = query.order_by(desc(sort_field))
        else:
            query = query.order_by(asc(sort_field))

        # Apply pagination
        saved_properties = query.offset(skip).limit(limit).all()

        return saved_properties, total

    def save_property(
        self,
        user_id: int,
        property_id: int,
        notes: Optional[str] = None,
        rating: Optional[int] = None,
        tags: Optional[str] = None,
        is_favorite: bool = False,
    ) -> SavedProperty:
        """Save a property for a user."""
        saved_property = SavedProperty(
            user_id=user_id,
            property_id=property_id,
            notes=notes,
            rating=rating,
            tags=tags,
            is_favorite=is_favorite,
        )

        self.db.add(saved_property)
        self.db.commit()
        self.db.refresh(saved_property)

        logger.info(f"User {user_id} saved property {property_id}")

        return saved_property

    def update_saved_property(
        self, saved_property_id: int, user_id: int, updates: Dict[str, Any]
    ) -> Optional[SavedProperty]:
        """Update a saved property."""
        saved_property = self.get_saved_property_by_id(saved_property_id, user_id)

        if not saved_property:
            return None

        for key, value in updates.items():
            if hasattr(saved_property, key):
                setattr(saved_property, key, value)

        saved_property.updated_at = datetime.now(timezone.utc)

        self.db.commit()
        self.db.refresh(saved_property)

        return saved_property

    def delete_saved_property(self, saved_property_id: int, user_id: int) -> bool:
        """Delete a saved property."""
        saved_property = self.get_saved_property_by_id(saved_property_id, user_id)

        if not saved_property:
            return False

        self.db.delete(saved_property)
        self.db.commit()

        logger.info(f"User {user_id} deleted saved property {saved_property_id}")

        return True

    def get_user_stats(self, user_id: int) -> Dict[str, Any]:
        """Get statistics about user's saved properties."""
        # Total counts
        total_saved = self.db.query(SavedProperty).filter(SavedProperty.user_id == user_id).count()

        total_favorites = (
            self.db.query(SavedProperty)
            .filter(and_(SavedProperty.user_id == user_id, SavedProperty.is_favorite))
            .count()
        )

        total_archived = (
            self.db.query(SavedProperty)
            .filter(and_(SavedProperty.user_id == user_id, SavedProperty.is_archived))
            .count()
        )

        total_viewed = (
            self.db.query(SavedProperty)
            .filter(
                and_(
                    SavedProperty.user_id == user_id,
                    SavedProperty.viewed_in_person,
                )
            )
            .count()
        )

        # Average rating
        avg_rating = (
            self.db.query(func.avg(SavedProperty.rating))
            .filter(and_(SavedProperty.user_id == user_id, SavedProperty.rating.isnot(None)))
            .scalar()
        )

        # Most used tags
        most_used_tags = self.get_tag_usage(user_id)

        # Recently saved (last 5)
        recently_saved = (
            self.db.query(SavedProperty)
            .filter(SavedProperty.user_id == user_id)
            .order_by(desc(SavedProperty.saved_at))
            .limit(5)
            .all()
        )

        return {
            "total_saved": total_saved,
            "total_favorites": total_favorites,
            "total_archived": total_archived,
            "total_viewed": total_viewed,
            "average_rating": round(float(avg_rating), 2) if avg_rating else None,
            "most_used_tags": most_used_tags[:10],  # Top 10 tags
            "recently_saved": recently_saved,
        }

    def get_all_tags(self, user_id: int) -> List[Dict[str, Any]]:
        """Get all unique tags used by user."""
        saved_properties = (
            self.db.query(SavedProperty).filter(SavedProperty.user_id == user_id).all()
        )

        return self._extract_tags_from_properties(saved_properties)

    def get_tag_usage(self, user_id: int) -> List[Dict[str, Any]]:
        """Get tag usage statistics."""
        saved_properties = (
            self.db.query(SavedProperty).filter(SavedProperty.user_id == user_id).all()
        )

        return self._extract_tags_from_properties(saved_properties)

    def bulk_update(
        self, user_id: int, saved_property_ids: List[int], updates: Dict[str, Any]
    ) -> int:
        """Bulk update multiple saved properties."""
        count = (
            self.db.query(SavedProperty)
            .filter(
                and_(
                    SavedProperty.user_id == user_id,
                    SavedProperty.id.in_(saved_property_ids),
                )
            )
            .update(updates, synchronize_session=False)
        )

        self.db.commit()

        return count

    def bulk_delete(self, user_id: int, saved_property_ids: List[int]) -> int:
        """Bulk delete multiple saved properties."""
        count = (
            self.db.query(SavedProperty)
            .filter(
                and_(
                    SavedProperty.user_id == user_id,
                    SavedProperty.id.in_(saved_property_ids),
                )
            )
            .delete(synchronize_session=False)
        )

        self.db.commit()

        logger.info(f"User {user_id} bulk deleted {count} properties")

        return count

    # Private helper methods

    def _extract_tags_from_properties(
        self, saved_properties: List[SavedProperty]
    ) -> List[Dict[str, Any]]:
        """Extract and count tags from saved properties."""
        all_tags = []

        for sp in saved_properties:
            if sp.tags:
                tags = [tag.strip() for tag in sp.tags.split(",")]
                all_tags.extend(tags)

        # Count tag occurrences
        tag_counts = Counter(all_tags)

        # Convert to list of dicts
        return [{"tag": tag, "count": count} for tag, count in tag_counts.most_common()]
