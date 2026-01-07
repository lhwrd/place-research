import logging
from typing import Any, Dict, Optional

from app.integrations.google_places_api import GooglePlacesAPI
from app.services.distance_service import DistanceService

from ..base_provider import (
    BaseEnrichmentProvider,
    ProviderCategory,
    ProviderMetadata,
    ProviderResult,
)


def categorize_distance(distance_miles: float | None) -> str:
    """Categorize distance into predefined categories.

    Args:
        distance_miles (float | None): Distance in miles.
    Returns:
        str: Distance category.
    """
    if distance_miles is None:
        return "Unknown"
    elif distance_miles < 2:
        return "Very Close"
    elif distance_miles < 5:
        return "Close"
    elif distance_miles < 10:
        return "Far"
    else:
        return "Very Far"


def categorize_duration(duration_m: float | None) -> str:
    """Categorize duration into predefined categories.

    Args:
        duration_m (float | None): Duration in minutes.

    Returns:
        str: Duration category.
    """
    if duration_m is None:
        return "Unknown"
    if duration_m < 7:
        return "Very Quick"
    elif duration_m < 15:
        return "Quick"
    elif duration_m < 30:
        return "Slow"
    else:
        return "Very Slow"


class PlacesNearbyProvider(BaseEnrichmentProvider):
    """Places nearby provider for fetching place data."""

    def __init__(self):
        self.places_api = GooglePlacesAPI()
        self.distance_service = DistanceService()
        self.logger = logging.getLogger(__name__)

    @property
    def metadata(self) -> ProviderMetadata:
        return ProviderMetadata(
            name="Places Nearby Provider",
            category=ProviderCategory.NEARBY_PLACES,
            description="Fetches nearby place information using Google Maps API.",
            version="1.0.0",
            enabled=True,
            requires_api_key=True,
            cost_per_call=0.002,  # Estimated cost in USD
            cache_duration_days=30,
            rate_limit_per_hour=1000,
            dependencies=[],
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
        Enrich property with provider-specific data.

        Args:
            latitude: Property latitude
            longitude: Property longitude
            address: Property address
            property_data: Additional property information
            user_preferences: User-specific preferences

        Returns:
            ProviderResult with enrichment data
        """
        place_types = user_preferences.get("preferred_amenities", []) if user_preferences else []
        text_queries = user_preferences.get("preferred_places", []) if user_preferences else []
        places_types_results = await self.places_api.nearby_search(
            lat=latitude,
            lon=longitude,
            place_types=place_types,
            radius_miles=10.0,
            max_results=3,
        )

        text_query_results = []

        for query in text_queries:
            results = await self.places_api.text_search(
                text_query=query,
                lat=latitude,
                lon=longitude,
                radius_miles=10.0,
                max_results=2,
            )
            text_query_results.extend(results)

        all_places = places_types_results + text_query_results

        # enriched_places = []
        # for place in all_places:
        #     distance_info = await self.distance_service.calculate_distances(
        #         origin_lat=latitude,
        #         origin_lon=longitude,
        #         destinations=[(place["latitude"], place["longitude"])],
        #     )
        #     distance_miles = distance_info[0].get("distance_miles", None)
        #     duration_minutes = distance_info[0].get("duration_minutes", None)

        #     enriched_places.append(
        #         {
        #             "name": place["name"],
        #             "place_id": place["place_id"],
        #             "latitude": place["latitude"],
        #             "longitude": place["longitude"],
        #             "address": place["address"],
        #             "type": place.get("type", "Unknown"),
        #             "distance_miles": distance_miles,
        #             "distance_category": categorize_distance(distance_miles),
        #             "duration_minutes": duration_minutes,
        #             "duration_category": categorize_duration(duration_minutes),
        #         }
        #     )

        return ProviderResult(
            provider_name=self.metadata.name,
            data={"places_nearby": all_places},
            success=True,
            error_message=None,
            api_calls_made=1,
            cached=False,
        )

    async def validate_config(self) -> bool:
        """
        Validate provider configuration (API keys, etc.).

        Returns:
            True if configuration is valid
        """
        return await self.places_api.validate_api_key()
