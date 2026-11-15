"""The nearest Street View panorama, and which way to face to see the house.

The web UI embeds an interactive Street View starting at this panorama, turned toward
the property instead of up the street.
"""

import math
from typing import Any, Dict, Optional

from app.core.config import settings
from app.integrations.google_maps_api import GoogleMapsAPI
from app.services.enrichment.base_provider import (
    BaseEnrichmentProvider,
    ProviderCategory,
    ProviderMetadata,
    ProviderResult,
)


class StreetViewProvider(BaseEnrichmentProvider):
    def __init__(self):
        self.api_client = GoogleMapsAPI()

    @property
    def metadata(self) -> ProviderMetadata:
        return ProviderMetadata(
            name="street_view_provider",
            category=ProviderCategory.ENVIRONMENTAL,
            enabled=True,
            description="Nearest Street View panorama and the heading toward the property.",
            version="1.0.0",
            requires_api_key=True,
            cost_per_call=0.0,  # metadata requests are free
        )

    async def enrich(
        self,
        latitude: float,
        longitude: float,
        address: str,
        property_data: Optional[Dict[str, Any]] = None,
        user_preferences: Optional[Dict[str, Any]] = None,
    ) -> ProviderResult:
        # The embed key is the one set up for Street View; the main key may not allow it
        pano = await self.api_client.street_view_metadata(
            latitude, longitude, api_key=settings.google_maps_embed_key
        )
        if pano is None:
            data: Dict[str, Any] = {"available": False}
        else:
            data = {
                "available": True,
                **pano,
                "heading": (
                    round(bearing(pano["latitude"], pano["longitude"], latitude, longitude))
                    if pano.get("latitude") is not None
                    else None
                ),
            }
        return ProviderResult(
            provider_name=self.metadata.name, data=data, success=True, api_calls_made=1
        )

    async def validate_config(self) -> bool:
        return bool(settings.google_maps_embed_key or self.api_client.api_key)


def bearing(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Initial compass bearing in degrees (0 = north, 90 = east) from point 1 to point 2."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dlon = math.radians(lon2 - lon1)
    x = math.sin(dlon) * math.cos(phi2)
    y = math.cos(phi1) * math.sin(phi2) - math.sin(phi1) * math.cos(phi2) * math.cos(dlon)
    return (math.degrees(math.atan2(x, y)) + 360) % 360
