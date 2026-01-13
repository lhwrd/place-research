"""User preference schemas."""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator


class UserPreferenceBase(BaseModel):
    """Base user preference schema."""

    min_walk_score: Optional[int] = Field(None, ge=0, le=100)
    min_bike_score: Optional[int] = Field(None, ge=0, le=100)
    min_transit_score: Optional[int] = Field(None, ge=0, le=100)

    max_grocery_distance: Optional[float] = Field(None, ge=0)
    max_park_distance: Optional[float] = Field(None, ge=0)
    max_school_distance: Optional[float] = Field(None, ge=0)
    max_hospital_distance: Optional[float] = Field(None, ge=0)

    max_commute_time: Optional[int] = Field(None, ge=0)

    preferred_amenities: Optional[List[str]] = None
    preferred_places: Optional[List[str]] = None

    min_bedrooms: Optional[int] = Field(None, ge=0)
    min_bathrooms: Optional[float] = Field(None, ge=0)
    min_square_feet: Optional[int] = Field(None, ge=0)
    max_year_built: Optional[int] = None
    preferred_property_types: Optional[List[str]] = None

    min_price: Optional[int] = Field(None, ge=0)
    max_price: Optional[int] = Field(None, ge=0)

    notify_new_listings: bool = False
    notify_price_changes: bool = False


class UserPreferenceCreate(UserPreferenceBase):
    """Schema for creating user preferences."""


class UserPreferenceUpdate(UserPreferenceBase):
    """Schema for updating user preferences."""


class AmenityPreferencesUpdate(BaseModel):
    """Schema for updating amenity distance preferences."""

    max_grocery_distance: Optional[float] = Field(
        None, ge=0, description="Maximum distance to grocery stores (miles)"
    )
    max_park_distance: Optional[float] = Field(
        None, ge=0, description="Maximum distance to parks (miles)"
    )
    max_school_distance: Optional[float] = Field(
        None, ge=0, description="Maximum distance to schools (miles)"
    )
    max_hospital_distance: Optional[float] = Field(
        None, ge=0, description="Maximum distance to hospitals (miles)"
    )


class PropertyCriteriaUpdate(BaseModel):
    """Schema for updating property criteria."""

    min_bedrooms: Optional[int] = Field(None, ge=0)
    min_bathrooms: Optional[float] = Field(None, ge=0)
    min_square_feet: Optional[int] = Field(None, ge=0)
    max_year_built: Optional[int] = Field(None, ge=1800, le=2100)
    preferred_property_types: Optional[List[str]] = None
    min_price: Optional[int] = Field(None, ge=0)
    max_price: Optional[int] = Field(None, ge=0)

    @field_validator("max_price")
    @classmethod
    def check_price_range(cls, v, info):
        """Ensure max_price >= min_price."""
        min_price = info.data.get("min_price")
        if v is not None and min_price is not None and v < min_price:
            raise ValueError("max_price must be greater than or equal to min_price")
        return v


class UserPreferenceResponse(UserPreferenceBase):
    """User preference response schema."""

    id: int
    user_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
