import logging
from typing import Any, Dict, Optional

from app.integrations.google_places_api import GooglePlacesAPI

from ..base_provider import (
    BaseEnrichmentProvider,
    ProviderCategory,
    ProviderMetadata,
    ProviderResult,
)


class PlacesNearbyProvider(BaseEnrichmentProvider):
    """Places nearby provider for fetching place data."""

    def __init__(self):
        self.places_api = GooglePlacesAPI()
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

        all_places = places_types_results + text_query_results

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
