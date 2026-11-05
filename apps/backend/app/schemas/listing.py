"""Listing ingest and Baserow webhook schemas."""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ListingCreateRequest(BaseModel):
    """Schema for a listing shared from the iOS Shortcut."""

    url: str = Field(..., min_length=10, description="Zillow listing URL")
    listing_json: Optional[Any] = Field(
        None,
        description="JSON extracted from the listing page (JSON-LD and/or __NEXT_DATA__), "
        "as an object or a JSON string",
    )


class ListingCreateResponse(BaseModel):
    """Schema for the created (or existing) Baserow row."""

    row_id: int
    created: bool = Field(..., description="False if the listing was already in Baserow")


class ListingImagesResponse(BaseModel):
    """Schema for an image upload result."""

    row_id: int
    uploaded: int
    photo_count: int


class BaserowWebhookPayload(BaseModel):
    """Subset of Baserow's row webhook payload that the handler uses."""

    table_id: Optional[int] = None
    event_type: str
    items: List[Dict[str, Any]] = Field(default_factory=list)
