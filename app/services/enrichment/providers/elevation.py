"""Ground elevation, and how it compares with the surrounding ground.

Absolute elevation says little about flooding in Florida, where Orlando sits ~100 ft up and
still floods. What matters is whether the house is lower than its surroundings, so rain
runs toward it: many homes outside FEMA flood zones flooded in Hurricane Ian for that
reason. This samples the USGS 3DEP elevation at the property and at eight points on a
ring around it, in one request. National coverage; no key.
"""

import logging
import math
from typing import Any, Dict, List, Optional, Tuple

import httpx

from app.integrations.arcgis_api import USGS_ELEVATION, ArcGISClient

from ..base_provider import (
    BaseEnrichmentProvider,
    ProviderCategory,
    ProviderMetadata,
    ProviderResult,
)

DEM_SERVICE = "3DEPElevation/ImageServer"
FEET_PER_METER = 3.28084

RING_RADIUS_M = 250
RING_POINTS = 8
METERS_PER_DEG_LAT = 110_950.0


class ElevationProvider(BaseEnrichmentProvider):
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        # The DEM can take several seconds to sample
        self.api_client = ArcGISClient(USGS_ELEVATION, service="USGS 3DEP", timeout=60.0)

    @property
    def metadata(self) -> ProviderMetadata:
        return ProviderMetadata(
            name="elevation_provider",
            category=ProviderCategory.CLIMATE,
            description=(
                "Ground elevation (USGS 3DEP) and how it compares with the ground "
                f"{RING_RADIUS_M} m around."
            ),
            version="1.0.0",
            requires_api_key=False,
            cache_duration_days=365,
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
            ProviderResult with elevation_ft, surrounding_mean_ft, relative_ft (property
            minus surroundings: negative means lower) and lower_than_pct (share of the ring
            points higher than the property)
        """
        points = [(latitude, longitude), *ring(latitude, longitude)]
        try:
            meters = await self.api_client.sample_many(DEM_SERVICE, points)
        except (httpx.HTTPError, ValueError) as e:
            self.logger.error("Error fetching elevation for %s: %s", address, e)
            return ProviderResult(
                provider_name=self.metadata.name,
                data={},
                success=False,
                error_message=str(e),
                api_calls_made=1,
            )

        feet = [m * FEET_PER_METER if m is not None else None for m in meters]
        return ProviderResult(
            provider_name=self.metadata.name,
            data=compare(feet[0], feet[1:]),
            success=True,
            api_calls_made=1,
        )

    async def validate_config(self) -> bool:
        return True


def ring(latitude: float, longitude: float) -> List[Tuple[float, float]]:
    """Points RING_RADIUS_M from the property, evenly spaced around it."""
    meters_per_deg_lon = 111_320.0 * math.cos(math.radians(latitude))
    return [
        (
            latitude + RING_RADIUS_M * math.cos(angle) / METERS_PER_DEG_LAT,
            longitude + RING_RADIUS_M * math.sin(angle) / meters_per_deg_lon,
        )
        for angle in (2 * math.pi * i / RING_POINTS for i in range(RING_POINTS))
    ]


def compare(center: Optional[float], around: List[Optional[float]]) -> Dict[str, Any]:
    around = [e for e in around if e is not None]
    if center is None:
        return {"elevation_ft": None}
    data: Dict[str, Any] = {"elevation_ft": round(center, 1)}
    if around:
        mean = sum(around) / len(around)
        data.update(
            surrounding_mean_ft=round(mean, 1),
            relative_ft=round(center - mean, 1),
            lower_than_pct=round(100 * sum(1 for e in around if e > center) / len(around)),
        )
    return data
