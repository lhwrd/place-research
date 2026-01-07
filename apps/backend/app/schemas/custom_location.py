"""Custom location schemas."""

from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator


class LocationTypeEnum(str, Enum):
    """Location type enumeration."""

    FAMILY = "family"
    FRIEND = "friend"
    WORK = "work"
    OTHER = "other"


class CustomLocationBase(BaseModel):
    """Base custom location schema."""

    name: str = Field(..., min_length=1, max_length=100, description="Friendly name")
    description: Optional[str] = Field(None, max_length=500)
    location_type: LocationTypeEnum = Field(LocationTypeEnum.OTHER, description="Category")
    priority: int = Field(0, ge=0, le=100, description="Priority (0-100)")
    is_active: bool = Field(True, description="Whether to use in distance calculations")


class CustomLocationCreate(CustomLocationBase):
    """Schema for creating a custom location."""

    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip_code: Optional[str] = None
    latitude: Optional[float] = Field(None, ge=-90, le=90)
    longitude: Optional[float] = Field(None, ge=-180, le=180)

    @field_validator("longitude")
    @classmethod
    def check_coordinates_or_address(cls, v, info):
        """Ensure either address or coordinates are provided."""
        address = info.data.get("address")
        latitude = info.data.get("latitude")

        # Must have either address or both coordinates
        if not address and (latitude is None or v is None):
            raise ValueError("Must provide either address or both latitude and longitude")

        # If longitude provided, latitude must also be provided
        if v is not None and latitude is None:
            raise ValueError("If longitude is provided, latitude must also be provided")

        return v


class CustomLocationUpdate(BaseModel):
    """Schema for updating a custom location."""

    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    address: Optional[str] = None
    latitude: Optional[float] = Field(None, ge=-90, le=90)
    longitude: Optional[float] = Field(None, ge=-180, le=180)
    location_type: Optional[LocationTypeEnum] = None
    priority: Optional[int] = Field(None, ge=0, le=100)
    is_active: Optional[bool] = None


class CustomLocationResponse(BaseModel):
    """Custom location response."""

    id: int
    user_id: int
    name: str
    description: Optional[str] = None
    address: str
    city: Optional[str]
    state: Optional[str]
    zip_code: Optional[str]
    latitude: float
    longitude: float
    location_type: Optional[LocationTypeEnum] = LocationTypeEnum.OTHER
    priority: int = 0
    is_active: bool = True
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class CustomLocationWithDistance(CustomLocationResponse):
    """Custom location with calculated distance."""

    distance_miles: Optional[float] = None
    driving_time_minutes: Optional[int] = None


class CustomLocationList(BaseModel):
    """List of custom locations with pagination."""

    items: List[CustomLocationResponse]
    total: int
    skip: int
    limit: int
