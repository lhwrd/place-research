"""Wetlands and open water near the property (USFWS National Wetlands Inventory).

Vegetated wetlands (marsh, swamp, mangrove) next door mean mosquitoes, wildlife and
drainage that backs up in heavy rain; they're also protected, so they stay undeveloped.
Ponds and lakes are reported separately because Florida subdivisions are full of
stormwater ponds. National coverage; no key.
"""

import logging
from typing import Any, Dict, List, Optional

import httpx

from app.integrations.arcgis_api import USFWS_WETLANDS, ArcGISClient
from app.utils.distance_calculator import geometry_distance_m

from ..base_provider import (
    BaseEnrichmentProvider,
    ProviderCategory,
    ProviderMetadata,
    ProviderResult,
)

WETLANDS_LAYER = "Wetlands/MapServer/0"
SEARCH_RADIUS_M = 500

# NWI WETLAND_TYPE values
VEGETATED_WETLANDS = {
    "Freshwater Emergent Wetland",
    "Freshwater Forested/Shrub Wetland",
    "Estuarine and Marine Wetland",
}
OPEN_WATER = {"Freshwater Pond", "Lake", "Riverine", "Estuarine and Marine Deepwater"}


class WetlandsProvider(BaseEnrichmentProvider):
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.api_client = ArcGISClient(USFWS_WETLANDS, service="USFWS wetlands", timeout=45.0)

    @property
    def metadata(self) -> ProviderMetadata:
        return ProviderMetadata(
            name="wetlands_provider",
            category=ProviderCategory.ENVIRONMENTAL,
            description="Nearest mapped wetland and open water within 500 m (USFWS NWI).",
            version="1.0.0",
            requires_api_key=False,
            cache_duration_days=180,
        )

    async def enrich(
        self,
        latitude: float,
        longitude: float,
        address: str,
        property_data: Optional[Dict[str, Any]] = None,
        user_preferences: Optional[Dict[str, Any]] = None,
    ) -> ProviderResult:
        """
        Returns:
            ProviderResult with in_wetland, nearest_wetland_m, nearest_wetland_type,
            nearest_water_m and nearest_water_type (None when nothing within 500 m)
        """
        try:
            features = await self.api_client.query_near(
                WETLANDS_LAYER,
                latitude,
                longitude,
                SEARCH_RADIUS_M,
                ("WETLAND_TYPE", "ACRES"),
                geometry=True,
            )
        except (httpx.HTTPError, ValueError) as e:
            self.logger.error("Error fetching wetlands for %s: %s", address, e)
            return ProviderResult(
                provider_name=self.metadata.name,
                data={},
                success=False,
                error_message=str(e),
                api_calls_made=1,
            )

        return ProviderResult(
            provider_name=self.metadata.name,
            data=summarize_wetlands(latitude, longitude, features),
            success=True,
            api_calls_made=1,
        )

    async def validate_config(self) -> bool:
        return True


def summarize_wetlands(
    latitude: float, longitude: float, features: List[Dict[str, Any]]
) -> Dict[str, Any]:
    def nearest(types: set) -> Optional[tuple]:
        candidates = [
            (geometry_distance_m(latitude, longitude, f["geometry"]), f["WETLAND_TYPE"])
            for f in features
            if f.get("WETLAND_TYPE") in types and f.get("geometry") is not None
        ]
        return min(candidates) if candidates else None

    wetland = nearest(VEGETATED_WETLANDS)
    water = nearest(OPEN_WATER)
    return {
        "in_wetland": wetland is not None and wetland[0] == 0,
        "nearest_wetland_m": round(wetland[0]) if wetland else None,
        "nearest_wetland_type": wetland[1] if wetland else None,
        "nearest_water_m": round(water[0]) if water else None,
        "nearest_water_type": water[1] if water else None,
    }
