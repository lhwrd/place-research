"""Listing ingest schemas (iOS Shortcut API)."""

from typing import Any, Optional
from urllib.parse import urlparse

from pydantic import BaseModel, Field, field_validator


class ListingCreateRequest(BaseModel):
    """Schema for a listing shared from the iOS Shortcut."""

    url: str = Field(..., min_length=10, description="Zillow listing URL")
    listing_json: Optional[Any] = Field(
        None,
        description="JSON extracted from the listing page (JSON-LD and/or __NEXT_DATA__), "
        "as an object or a JSON string",
    )

    @field_validator("url")
    @classmethod
    def _http_url(cls, value: str) -> str:
        """The URL becomes a link in the UI, so no javascript:, data: or other schemes."""
        value = value.strip()
        parsed = urlparse(value)
        if parsed.scheme.lower() not in ("http", "https") or not parsed.netloc:
            raise ValueError("url must be an http(s) URL")
        return value


class ListingCreateResponse(BaseModel):
    """Schema for the created (or existing) listing."""

    row_id: int = Field(..., description="Property id (named row_id for Shortcut compatibility)")
    created: bool = Field(..., description="False if the listing was already saved")


class ListingImagesResponse(BaseModel):
    """Schema for an image upload result."""

    row_id: int
    uploaded: int
    photo_count: int
