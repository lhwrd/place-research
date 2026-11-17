"""Central Florida places whose crowds spill onto the roads around them.

- The attractions area: theme parks, Disney Springs, International Drive and the
  convention center. Traffic is heavy every day, worst at park opening and closing, and
  the nearby shops and restaurants are priced and crowded for visitors.
- Event venues: arenas, stadiums and the speedway. Quiet most days; on event days the
  streets around them close or back up and parking fills the neighborhood.

Fixed locations, no API. Coordinates are approximate (well within a mile).
"""

from typing import Any, Dict, Optional

from ..base_provider import (
    BaseEnrichmentProvider,
    ProviderCategory,
    ProviderMetadata,
    ProviderResult,
)
from .local_noise_sources import FIREWORKS_VENUES, METERS_PER_MILE, _within

ATTRACTIONS = [
    *FIREWORKS_VENUES,
    ("Disney's Animal Kingdom", 28.3597, -81.5913),
    ("Disney Springs", 28.3702, -81.5190),
    ("Universal Islands of Adventure", 28.4717, -81.4702),
    ("International Drive / ICON Park", 28.4433, -81.4683),
    ("Orange County Convention Center", 28.4255, -81.4690),
    ("US-192 tourist strip (Kissimmee)", 28.3330, -81.5150),
    ("Kennedy Space Center Visitor Complex", 28.5230, -80.6820),
    ("Daytona Beach boardwalk", 29.2290, -81.0070),
]

VENUES = [
    ("Kia Center", 28.5392, -81.3839),
    ("Camping World Stadium", 28.5390, -81.4028),
    ("Inter&Co Stadium", 28.5411, -81.3893),
    ("Dr. Phillips Center", 28.5376, -81.3770),
    ("UCF stadium and arena", 28.6075, -81.1940),
    ("Central Florida Fairgrounds", 28.5560, -81.4560),
    ("Osceola Heritage Park / Silver Spurs Arena", 28.2960, -81.3690),
    ("ESPN Wide World of Sports", 28.3371, -81.5560),
    ("Daytona International Speedway", 29.1852, -81.0705),
    ("USTA National Campus", 28.3760, -81.2530),
]

# Past these the place is no longer worth a mention
ATTRACTION_RANGE_M = 5 * METERS_PER_MILE
VENUE_RANGE_M = 3 * METERS_PER_MILE


class EventTrafficProvider(BaseEnrichmentProvider):
    @property
    def metadata(self) -> ProviderMetadata:
        return ProviderMetadata(
            name="event_traffic_provider",
            category=ProviderCategory.TRANSIT,
            description="Distance to tourist attractions and event venues that draw traffic.",
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
            ProviderResult with attractions (within 5 miles) and venues (within 3), each a
            list of {name, distance_m}, nearest first
        """
        return ProviderResult(
            provider_name=self.metadata.name,
            data={
                "attractions": _within(ATTRACTIONS, latitude, longitude, ATTRACTION_RANGE_M),
                "venues": _within(VENUES, latitude, longitude, VENUE_RANGE_M),
            },
            success=True,
        )

    async def validate_config(self) -> bool:
        return True
