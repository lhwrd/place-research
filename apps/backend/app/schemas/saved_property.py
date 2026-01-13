"""Saved property schemas."""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field

from app.schemas.property import PropertyData


class SavedPropertyBase(BaseModel):
    """Base saved property schema."""

    notes: Optional[str] = None
    rating: Optional[int] = Field(None, ge=1, le=5)
    tags: Optional[str] = None
    is_favorite: bool = False
    is_archived: bool = False
    viewed_in_person: bool = False
    viewing_date: Optional[datetime] = None


class SavedPropertyCreate(BaseModel):
    """Schema for saving a property."""

    property_id: int
    notes: Optional[str] = None
    rating: Optional[int] = Field(None, ge=1, le=5)
    tags: Optional[str] = Field(None, description="Comma-separated tags")
    is_favorite: bool = False


class SavedPropertyUpdate(BaseModel):
    """Schema for updating a saved property."""

    notes: Optional[str] = None
    rating: Optional[int] = Field(None, ge=1, le=5)
    tags: Optional[str] = None
    is_favorite: Optional[bool] = None
    is_archived: Optional[bool] = None
    viewed_in_person: Optional[bool] = None
    viewing_date: Optional[datetime] = None


class SavedPropertyResponse(SavedPropertyBase):
    """Saved property response."""

    id: int
    user_id: int
    property_id: int
    saved_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class SavedPropertyWithDetails(SavedPropertyResponse):
    """Saved property with full property details."""

    property: PropertyData

    @classmethod
    def from_saved_property(cls, saved_property):
        """Create from SavedProperty model."""
        from app.schemas.property import PropertyData

        return cls(
            id=saved_property.id,
            user_id=saved_property.user_id,
            property_id=saved_property.property_id,
            notes=saved_property.notes,
            rating=saved_property.rating,
            tags=saved_property.tags,
            is_favorite=saved_property.is_favorite,
            is_archived=saved_property.is_archived,
            viewed_in_person=saved_property.viewed_in_person,
            viewing_date=saved_property.viewing_date,
            saved_at=saved_property.saved_at,
            updated_at=saved_property.updated_at,
            property=PropertyData.model_validate(saved_property.property),
        )


class SavedPropertyList(BaseModel):
    """List of saved properties with pagination."""

    items: List[SavedPropertyWithDetails]
    total: int
    skip: int
    limit: int


class SavedPropertyStats(BaseModel):
    """Statistics about saved properties."""

    total_saved: int
    total_favorites: int
    total_archived: int
    total_viewed: int
    average_rating: Optional[float] = None
    most_used_tags: List[dict]
    recently_saved: List[SavedPropertyWithDetails]
