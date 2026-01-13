import logging
import math
from typing import Any, Dict, Optional

from app.integrations.highway_api import HighwayAPIClient
from app.services.enrichment.base_provider import (
    BaseEnrichmentProvider,
    ProviderCategory,
    ProviderMetadata,
    ProviderResult,
)
from app.utils.distance_calculator import haversine_distance


class HighwayProvider(BaseEnrichmentProvider):
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.api_client = HighwayAPIClient()

    @property
    def metadata(self) -> ProviderMetadata:
        return ProviderMetadata(
            name="highway_provider",
            category=ProviderCategory.ENVIRONMENTAL,
            enabled=True,
            description="Provides proximity to highways and estimates road noise levels using Highway API.",  # pylint: disable=line-too-long
            version="1.0.0",
            requires_api_key=True,
            cost_per_call=0.001,  # Estimated cost per API call
        )

    def _calculate_min_distance_to_highways(
        self, place_lat: float, place_lon: float, highways: list
    ) -> float | None:
        """
        Calculate the minimum distance from the place to any highway segment.
        """
        min_distance = float("inf")

        for highway in highways:
            if highway.get("type") == "way" and "geometry" in highway:
                # Calculate distance to each point in the highway geometry
                for node in highway["geometry"]:
                    node_lat = node.get("lat")
                    node_lon = node.get("lon")
                    if node_lat is not None and node_lon is not None:
                        distance = haversine_distance(place_lat, place_lon, node_lat, node_lon)
                        min_distance = min(min_distance, distance)

        return min_distance if min_distance != float("inf") else None

    def _estimate_road_noise_level(self, distance_m: float | None, highway_types: list) -> dict:
        """
        Estimate road noise level based on distance and highway types.
        This is a simplified model - real noise depends on traffic volume,
        terrain, barriers, etc.
        """
        if distance_m is None:
            return {"noise_level_db": None, "noise_category": "Unknown"}

        # Base noise levels for different highway types (approximate)
        base_noise = {
            "motorway": 75,  # dB(A) at 30m
            "trunk": 70,  # dB(A) at 30m
            "primary": 65,  # dB(A) at 30m
        }

        # Get the highest noise level from nearby highway types
        max_base_noise = (
            max([base_noise.get(htype, 60) for htype in highway_types]) if highway_types else 60
        )

        # Sound level decreases roughly 6 dB per doubling of distance
        # Reference distance is 30 meters
        reference_distance = 30
        if distance_m <= reference_distance:
            estimated_db = max_base_noise
        else:
            distance_ratio = distance_m / reference_distance
            db_reduction = 6 * math.log2(distance_ratio)
            estimated_db = max(max_base_noise - db_reduction, 35)  # Minimum ambient noise

        # Categorize noise level
        if estimated_db >= 70:
            category = "Very High"
        elif estimated_db >= 60:
            category = "High"
        elif estimated_db >= 50:
            category = "Moderate"
        elif estimated_db >= 40:
            category = "Low"
        else:
            category = "Very Low"

        return {"noise_level_db": round(estimated_db, 1), "noise_category": category}

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
        # Get nearby highways
        response = await self.api_client.fetch_nearby_highways(latitude, longitude)
        highways = response.get("elements", [])

        if not highways:
            self.logger.info("No highways found near the place.")
            return ProviderResult(
                provider_name=self.metadata.name,
                data={},
                success=True,
                api_calls_made=1,
            )

        # Calculate minimum distance
        min_distance = self._calculate_min_distance_to_highways(latitude, longitude, highways)

        # Extract highway types for noise estimation
        highway_types = []
        for highway in highways:
            highway_type = highway.get("tags", {}).get("highway")
            if highway_type:
                highway_types.append(highway_type)

        # Get the closest highway type
        closest_highway_type = None
        if highways and min_distance is not None:
            closest_distance = float("inf")
            for highway in highways:
                if highway.get("type") == "way" and "geometry" in highway:
                    for node in highway["geometry"]:
                        node_lat = node.get("lat")
                        node_lon = node.get("lon")
                        if node_lat is not None and node_lon is not None:
                            distance = haversine_distance(latitude, longitude, node_lat, node_lon)
                            if distance < closest_distance:
                                closest_distance = distance
                                closest_highway_type = highway.get("tags", {}).get("highway")

        # Estimate road noise
        noise_data = self._estimate_road_noise_level(min_distance, highway_types)

        # Store results
        highway_distance_m = int(round(min_distance, 0)) if min_distance is not None else None
        nearest_highway_type = closest_highway_type
        road_noise_level_db = noise_data["noise_level_db"]
        road_noise_category = noise_data["noise_category"]

        return ProviderResult(
            provider_name=self.metadata.name,
            data={
                "highway_distance_m": highway_distance_m,
                "nearest_highway_type": nearest_highway_type,
                "road_noise_level_db": road_noise_level_db,
                "road_noise_category": road_noise_category,
            },
            success=True,
            api_calls_made=1,
        )

    async def validate_config(self) -> bool:
        """
        Validate provider configuration (API keys, etc.).

        Returns:
            True if configuration is valid
        """
        return await self.api_client.validate_api_key()
