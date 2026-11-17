"""How many restaurants, bars and coffee shops are close by (Google Places).

One Nearby Search for the 20 closest sit-down restaurants, bars, pubs, wine bars, cafes and
coffee shops within a mile and a half, fast food excluded. Twenty is the most one search
returns, so the count is exact where places are sparse and, where they are dense, the
distance to the 20th says how dense: twenty within half a mile is a main street, twenty
spread over a mile and a half is a few strip malls.
"""

import logging
from typing import Any, Dict, List, Optional

from app.integrations.google_places_api import GooglePlacesAPI
from app.utils.distance_calculator import haversine_distance

from ..base_provider import (
    BaseEnrichmentProvider,
    ProviderCategory,
    ProviderMetadata,
    ProviderResult,
)

TYPES = ["restaurant", "bar", "pub", "wine_bar", "cafe", "coffee_shop"]
EXCLUDED_TYPES = ["fast_food_restaurant"]
RADIUS_MILES = 1.5
MAX_RESULTS = 20  # the API's limit

METERS_PER_MILE = 1609.344
WALK_M = 0.5 * METERS_PER_MILE  # about ten minutes on foot

logger = logging.getLogger(__name__)


class FoodDrinkProvider(BaseEnrichmentProvider):
    def __init__(self):
        self.places_api = GooglePlacesAPI()

    @property
    def metadata(self) -> ProviderMetadata:
        return ProviderMetadata(
            name="food_drink_provider",
            category=ProviderCategory.NEARBY_PLACES,
            description="Restaurants, bars and coffee shops within walking distance.",
            version="1.0.0",
            requires_api_key=True,
            cost_per_call=0.032,
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
            ProviderResult with places (the closest 20 at most, nearest first: name, type,
            distance_m), walkable_count (within half a mile), count, capped (True when
            there are more than were returned) and radius_m
        """
        try:
            found = await self.places_api.nearby_search(
                lat=latitude,
                lon=longitude,
                place_types=TYPES,
                radius_miles=RADIUS_MILES,
                max_results=MAX_RESULTS,
                excluded_types=EXCLUDED_TYPES,
                nearest_first=True,
            )
        except Exception as e:  # pylint: disable=broad-except
            logger.error("Error fetching food and drink places for %s: %s", address, e)
            return ProviderResult(
                provider_name=self.metadata.name,
                data={},
                success=False,
                error_message=str(e),
                api_calls_made=1,
            )
        return ProviderResult(
            provider_name=self.metadata.name,
            data=summarize_places(latitude, longitude, found),
            success=True,
            api_calls_made=1,
        )

    async def validate_config(self) -> bool:
        return await self.places_api.validate_api_key()


def summarize_places(
    latitude: float, longitude: float, found: List[Dict[str, Any]]
) -> Dict[str, Any]:
    places = sorted(
        (
            {
                "name": p.get("name"),
                "type": p.get("type"),
                "distance_m": round(
                    haversine_distance(latitude, longitude, p["latitude"], p["longitude"])
                ),
            }
            for p in found
            if p.get("latitude") is not None and p.get("longitude") is not None
        ),
        key=lambda p: p["distance_m"],
    )
    return {
        "places": places,
        "count": len(places),
        "walkable_count": sum(1 for p in places if p["distance_m"] <= WALK_M),
        "capped": len(found) >= MAX_RESULTS,
        "radius_m": round(RADIUS_MILES * METERS_PER_MILE),
    }
