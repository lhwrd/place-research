from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, validator


class PropertySearchRequest(BaseModel):
    address: str = Field(
        ...,
        min_length=5,
        max_length=200,
        description="Full street address to search for",
        example="123 Main St, Seattle, WA 98101",
    )

    @validator("address")
    def validate_address(self, v):
        # Basic sanitization
        if any(char in v for char in ["<", ">", ";", "--", '"', "'"]):
            raise ValueError("Invalid characters in address")
        return v.strip()


class PropertyBase(BaseModel):
    address: str
    city: Optional[str]
    state: Optional[str]
    zip_code: Optional[str]
    latitude: float
    longitude: float
    bedrooms: Optional[int]
    bathrooms: Optional[float]
    square_feet: Optional[int]
    year_built: Optional[int]
    property_type: Optional[str]
    estimated_value: Optional[int]


class PropertyData(PropertyBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class PropertySearchResponse(BaseModel):
    success: bool
    property: PropertyData
    message: str


class WalkScoreData(BaseModel):
    walk_score: Optional[int] = Field(None, ge=0, le=100)
    bike_score: Optional[int] = Field(None, ge=0, le=100)
    transit_score: Optional[int] = Field(None, ge=0, le=100)
    description: Optional[str]


class NearbyPlace(BaseModel):
    name: str
    type: str  # "grocery_store", "park", "restaurant", etc.
    address: str
    distance_miles: float
    walking_time_minutes: Optional[int]
    rating: Optional[float]


class CustomLocationDistance(BaseModel):
    location_id: int
    location_name: str  # "Mom's House", "Best Friend's Apt"
    distance_miles: float
    driving_time_minutes: int
    traffic_time_minutes: Optional[int]  # With typical traffic


class EnrichmentProviderData(BaseModel):
    data: dict
    success: bool
    cached: bool
    enriched_at: datetime
    error: Optional[str] = None


class EnrichmentMetadata(BaseModel):
    total_providers: int
    successful_providers: int
    failed_providers: int
    total_api_calls: int
    cached_providers: int


class EnrichmentData(BaseModel):
    success: bool
    enrichment_data: dict[str, EnrichmentProviderData]
    metadata: EnrichmentMetadata


class PropertyEnrichmentResponse(BaseModel):
    success: bool
    property_id: int
    enrichment: EnrichmentData
    message: str
