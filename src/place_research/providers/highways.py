import logging
import math

import httpx

from place_research.interfaces import ProviderNameMixin
from place_research.models.place import Place
from place_research.models.results import HighwayResult
from place_research.utils import haversine_distance


class HighwayProvider(ProviderNameMixin):
    def __init__(self):
        self.logger = logging.getLogger(__name__)

    async def _get_nearby_highways(
        self, lat: float, lon: float, radius_km: float = 5.0
    ) -> list:
        """
        Query OpenStreetMap Overpass API for nearby highways.
        """
        overpass_url = "https://overpass-api.de/api/interpreter"

        # Overpass QL query for highways within radius
        # highway=motorway, trunk, primary are the major roads that generate most noise
        query = f"""
        [out:json][timeout:25];
        (
          way["highway"~"^(motorway|trunk|primary)$"](around:{radius_km * 1000},{lat},{lon});
        );
        out geom;
        """

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    overpass_url,
                    data=query,
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                )
                response.raise_for_status()
                return response.json().get("elements", [])
        except httpx.HTTPError as e:
            # Fallback to a smaller radius if the query fails
            if radius_km > 1.0:
                return await self._get_nearby_highways(lat, lon, radius_km / 2)
            raise ValueError(f"Failed to fetch highway data: {e}") from e

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
                        distance = haversine_distance(
                            place_lat, place_lon, node_lat, node_lon
                        )
                        min_distance = min(min_distance, distance)

        return min_distance if min_distance != float("inf") else None

    def _estimate_road_noise_level(
        self, distance_m: float | None, highway_types: list
    ) -> dict:
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
            max([base_noise.get(htype, 60) for htype in highway_types])
            if highway_types
            else 60
        )

        # Sound level decreases roughly 6 dB per doubling of distance
        # Reference distance is 30 meters
        reference_distance = 30
        if distance_m <= reference_distance:
            estimated_db = max_base_noise
        else:
            distance_ratio = distance_m / reference_distance
            db_reduction = 6 * math.log2(distance_ratio)
            estimated_db = max(
                max_base_noise - db_reduction, 35
            )  # Minimum ambient noise

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

    async def fetch_place_data(self, place: Place) -> HighwayResult:
        """
        Fetch highway distance and road noise data for the given place.
        """
        # Get nearby highways
        highways = await self._get_nearby_highways(place.latitude, place.longitude)

        if not highways:
            self.logger.info("No highways found near the place.")
            return HighwayResult(
                highway_distance_m=None,
                nearest_highway_type=None,
                road_noise_level_db=None,
                road_noise_category="Unknown",
            )

        # Calculate minimum distance
        min_distance = self._calculate_min_distance_to_highways(
            place.latitude, place.longitude, highways
        )

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
                            distance = haversine_distance(
                                place.latitude, place.longitude, node_lat, node_lon
                            )
                            if distance < closest_distance:
                                closest_distance = distance
                                closest_highway_type = highway.get("tags", {}).get(
                                    "highway"
                                )

        # Estimate road noise
        noise_data = self._estimate_road_noise_level(min_distance, highway_types)

        # Store results
        highway_distance_m = (
            int(round(min_distance, 0)) if min_distance is not None else None
        )
        nearest_highway_type = closest_highway_type
        road_noise_level_db = noise_data["noise_level_db"]
        road_noise_category = noise_data["noise_category"]

        return HighwayResult(
            highway_distance_m=highway_distance_m,
            nearest_highway_type=nearest_highway_type,
            road_noise_level_db=road_noise_level_db,
            road_noise_category=road_noise_category,
        )
