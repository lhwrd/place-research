import logging
from typing import Any, Dict, List, Optional

from app.integrations.google_maps_api import GoogleMapsAPI
from app.integrations.google_places_api import GooglePlacesAPI

from ..base_provider import (
    BaseEnrichmentProvider,
    ProviderCategory,
    ProviderMetadata,
    ProviderResult,
)


class PlacesNearbyProvider(BaseEnrichmentProvider):
    """Nearby amenities and preferred places, each with its drive time and distance."""

    # Distance Matrix allows 25 destinations per request
    DISTANCE_BATCH_SIZE = 25

    def __init__(self):
        self.places_api = GooglePlacesAPI()
        self.maps_api = GoogleMapsAPI()
        self.logger = logging.getLogger(__name__)

    @property
    def metadata(self) -> ProviderMetadata:
        return ProviderMetadata(
            name="places_nearby_provider",
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

        # The same place can match an amenity type and a search
        all_places: List[Dict[str, Any]] = []
        seen_ids = set()
        for place in places_types_results + text_query_results:
            if place.get("place_id") and place["place_id"] in seen_ids:
                continue
            seen_ids.add(place.get("place_id"))
            all_places.append(place)

        distance_calls = await self._add_drive_times((latitude, longitude), all_places)
        # Closest drive first; places without a drive time last
        all_places.sort(key=lambda p: (p.get("drive_minutes") is None, p.get("drive_minutes") or 0))

        return ProviderResult(
            provider_name=self.metadata.name,
            data={"places_nearby": all_places},
            success=True,
            error_message=None,
            api_calls_made=1 + len(text_queries) + distance_calls,
            cached=False,
        )

    async def _add_drive_times(
        self, origin: tuple[float, float], places: List[Dict[str, Any]]
    ) -> int:
        """
        Set drive_minutes and drive_miles on each place that has coordinates.

        A failed lookup leaves those places without drive data rather than failing the
        provider. Returns the number of Distance Matrix calls made.
        """
        located = [
            p for p in places if p.get("latitude") is not None and p.get("longitude") is not None
        ]
        calls = 0
        for start in range(0, len(located), self.DISTANCE_BATCH_SIZE):
            batch = located[start : start + self.DISTANCE_BATCH_SIZE]
            calls += 1
            try:
                results = await self.maps_api.distance_matrix(
                    origin=origin,
                    destinations=[(p["latitude"], p["longitude"]) for p in batch],
                    mode="driving",
                )
            except Exception as e:  # pylint: disable=broad-except
                self.logger.warning("Drive times to nearby places failed: %s", e)
                continue
            for result in results:
                index = result.get("destination_index")
                if result.get("status") != "OK" or index is None or index >= len(batch):
                    continue
                batch[index]["drive_minutes"] = result.get(
                    "duration_in_traffic_minutes"
                ) or result.get("duration_minutes")
                batch[index]["drive_miles"] = result.get("distance_miles")
        return calls

    async def validate_config(self) -> bool:
        """
        Validate provider configuration (API keys, etc.).

        Returns:
            True if configuration is valid
        """
        return await self.places_api.validate_api_key()
