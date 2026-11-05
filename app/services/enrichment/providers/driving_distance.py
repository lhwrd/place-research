import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from app.integrations.google_maps_api import GoogleMapsAPI

from ..base_provider import (
    BaseEnrichmentProvider,
    ProviderCategory,
    ProviderMetadata,
    ProviderResult,
)

logger = logging.getLogger(__name__)


@dataclass
class CustomLocation:
    """A drive-time destination (a row in the Baserow Locations table)."""

    id: int
    name: str
    location_type: Optional[str]
    address: str
    latitude: float
    longitude: float
    priority: int = 0
    city: Optional[str] = None
    state: Optional[str] = None


class DistanceProvider(BaseEnrichmentProvider):
    """
    Provider to fetch driving distance and time using Google Maps API.
    Calculates distances to every custom location passed in user_preferences.
    """

    def __init__(self):
        self.api_client = GoogleMapsAPI()

    @property
    def metadata(self) -> ProviderMetadata:
        return ProviderMetadata(
            name="distance_provider",
            category=ProviderCategory.DISTANCES,
            enabled=True,
            description="Provides driving distance and time to custom locations using Google Maps API.",
            version="1.0.0",
            requires_api_key=True,
            cost_per_call=0.005,  # Cost per destination
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
        Enrich property with driving distances to the custom locations.

        Args:
            latitude: Property latitude
            longitude: Property longitude
            address: Property address
            property_data: Additional property information
            user_preferences: Provider inputs; "custom_locations" is a list of CustomLocation

        Returns:
            ProviderResult with distance and duration data for each custom location
        """
        custom_locations: List[CustomLocation] = (user_preferences or {}).get(
            "custom_locations", []
        )
        try:
            if not custom_locations:
                return ProviderResult(
                    provider_name=self.metadata.name,
                    data={"distances": [], "total_locations": 0},
                    success=True,
                    api_calls_made=0,
                )

            # Calculate distances in batches
            origin = (latitude, longitude)
            all_distances = await self._calculate_distances_batched(origin, custom_locations)

            # Format results
            data = {
                "distances": all_distances,
                "total_locations": len(custom_locations),
                "property_location": {
                    "latitude": latitude,
                    "longitude": longitude,
                    "address": address,
                },
            }

            # Count API calls (one per batch of 10)
            api_calls = (len(custom_locations) + 9) // 10  # Ceiling division

            return ProviderResult(
                provider_name=self.metadata.name,
                data=data,
                success=True,
                api_calls_made=api_calls,
            )

        except (ValueError, KeyError, AttributeError) as e:
            logger.error("Distance provider error: %s", str(e))
            return ProviderResult(
                provider_name=self.metadata.name,
                data={},
                success=False,
                error_message=str(e),
                api_calls_made=0,
            )

    async def _calculate_distances_batched(
        self,
        origin: tuple[float, float],
        custom_locations: List[CustomLocation],
    ) -> List[Dict[str, Any]]:
        """
        Calculate distances to custom locations in batches of 10.

        Args:
            origin: Origin coordinates (latitude, longitude)
            custom_locations: List of custom locations

        Returns:
            List of distance information for each location
        """
        all_distances = []
        batch_size = 10

        # Process locations in batches
        for i in range(0, len(custom_locations), batch_size):
            batch = custom_locations[i : i + batch_size]

            # Prepare destinations for this batch
            destinations = [
                (float(location.latitude), float(location.longitude))  # type: ignore
                for location in batch
            ]

            # Call distance_matrix API
            try:
                distance_results = await self.api_client.distance_matrix(
                    origin=origin,
                    destinations=destinations,
                    mode="driving",
                )

                # Combine location info with distance results
                for location, distance_info in zip(batch, distance_results):
                    result_item = {
                        "location_id": location.id,
                        "location_name": location.name,
                        "location_type": location.location_type,
                        "location_address": location.address,
                        "location_city": location.city,
                        "location_state": location.state,
                        "latitude": location.latitude,
                        "longitude": location.longitude,
                        "priority": location.priority,
                    }

                    # Add distance data if successful
                    if distance_info.get("status") == "OK":
                        result_item.update(
                            {
                                "distance_miles": distance_info.get("distance_miles"),
                                "distance_meters": distance_info.get("distance_meters"),
                                "duration_minutes": distance_info.get("duration_minutes"),
                                "duration_seconds": distance_info.get("duration_seconds"),
                                "duration_in_traffic_minutes": distance_info.get(
                                    "duration_in_traffic_minutes"
                                ),
                                "status": "OK",
                            }
                        )
                    else:
                        result_item.update(
                            {
                                "status": distance_info.get("status", "ERROR"),
                                "error": distance_info.get("error"),
                            }
                        )

                    all_distances.append(result_item)

            except (ValueError, KeyError, ConnectionError, TimeoutError) as e:
                logger.error(
                    "Error calculating distances for batch starting at index %s: %s",
                    i,
                    str(e),
                )
                # Add error entries for this batch
                for location in batch:
                    all_distances.append(
                        {
                            "location_id": location.id,
                            "location_name": location.name,
                            "location_type": location.location_type,
                            "status": "ERROR",
                            "error": str(e),
                        }
                    )

        return all_distances

    async def validate_config(self) -> bool:
        """Validate that the API key is set and valid."""
        is_valid = await self.api_client.validate_api_key()
        return is_valid
