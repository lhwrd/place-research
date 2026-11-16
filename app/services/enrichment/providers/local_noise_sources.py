"""Central Florida noise sources the road/rail/aircraft model doesn't cover.

- Theme park fireworks: Disney, Universal and SeaWorld have shows most nights, audible
  several miles away (and louder on holidays).
- Cape Canaveral: rocket launches, and sonic booms from boosters landing back at the Cape,
  rattle windows across Brevard and into Orange and Osceola.

Fixed locations, no API. Coordinates are approximate (well within a mile).
"""

from typing import Any, Dict, List, Optional

from app.utils.distance_calculator import haversine_distance

from ..base_provider import (
    BaseEnrichmentProvider,
    ProviderCategory,
    ProviderMetadata,
    ProviderResult,
)

FIREWORKS_VENUES = [
    ("Magic Kingdom", 28.4195, -81.5812),
    ("EPCOT", 28.3754, -81.5494),
    ("Disney's Hollywood Studios", 28.3575, -81.5583),
    ("Universal Studios Florida", 28.4752, -81.4664),
    ("Universal Epic Universe", 28.4724, -81.4472),
    ("SeaWorld Orlando", 28.4112, -81.4612),
]

LAUNCH_SITES = [
    ("Kennedy Space Center LC-39A", 28.6082, -80.6041),
    ("Cape Canaveral SLC-40", 28.5620, -80.5772),
    ("Cape Canaveral landing zones", 28.4858, -80.5442),
]

METERS_PER_MILE = 1609.344
# Past these the source is no longer worth a mention
FIREWORKS_RANGE_M = 10 * METERS_PER_MILE
LAUNCH_RANGE_M = 75 * METERS_PER_MILE


class LocalNoiseSourcesProvider(BaseEnrichmentProvider):
    @property
    def metadata(self) -> ProviderMetadata:
        return ProviderMetadata(
            name="local_noise_sources_provider",
            category=ProviderCategory.NOISE,
            description="Distance to theme park fireworks and Cape Canaveral launches.",
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
            ProviderResult with fireworks (venues within 10 miles, nearest first) and
            launch_site (the nearest, if within 75 miles), each {name, distance_m}
        """
        fireworks = _within(FIREWORKS_VENUES, latitude, longitude, FIREWORKS_RANGE_M)
        launches = _within(LAUNCH_SITES, latitude, longitude, LAUNCH_RANGE_M)
        return ProviderResult(
            provider_name=self.metadata.name,
            data={"fireworks": fireworks, "launch_site": launches[0] if launches else None},
            success=True,
        )

    async def validate_config(self) -> bool:
        return True


def _within(sites, latitude: float, longitude: float, max_m: float) -> List[Dict[str, Any]]:
    found = [
        {"name": name, "distance_m": round(haversine_distance(latitude, longitude, lat, lon))}
        for name, lat, lon in sites
    ]
    return sorted((s for s in found if s["distance_m"] <= max_m), key=lambda s: s["distance_m"])
