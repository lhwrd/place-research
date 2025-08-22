import requests
from typing import TYPE_CHECKING
import math

if TYPE_CHECKING:
    from ..config import Config
    from ..models import Place


class HighwayProvider:
    def __init__(self, config: "Config | None" = None):
        self.config = config
        self.timeout = config.timeout_seconds if config else 30

    def _haversine_distance(
        self, lat1: float, lon1: float, lat2: float, lon2: float
    ) -> float:
        """
        Calculate the great circle distance between two points
        on the earth (specified in decimal degrees) in meters.
        """
        # Convert decimal degrees to radians
        lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])

        # Haversine formula
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        a = (
            math.sin(dlat / 2) ** 2
            + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
        )
        c = 2 * math.asin(math.sqrt(a))

        # Radius of earth in meters
        r = 6371000
        return c * r

    def _get_nearby_highways(
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
            response = requests.post(
                overpass_url,
                data=query,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=self.timeout,
            )
            response.raise_for_status()
            return response.json().get("elements", [])
        except requests.RequestException as e:
            # Fallback to a smaller radius if the query fails
            if radius_km > 1.0:
                return self._get_nearby_highways(lat, lon, radius_km / 2)
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
                        distance = self._haversine_distance(
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

    def fetch_place_data(self, place: "Place"):
        """
        Fetch highway distance and road noise data for the given place.
        """
        lat, lon = place.coordinates

        try:
            # Get nearby highways
            highways = self._get_nearby_highways(lat, lon)

            if not highways:
                # No highways found within 5km
                place.attributes["highway_distance_m"] = None
                place.attributes["nearest_highway_type"] = None
                place.attributes["road_noise_level_db"] = None
                place.attributes["road_noise_category"] = "Very Low"
                return

            # Calculate minimum distance
            min_distance = self._calculate_min_distance_to_highways(lat, lon, highways)

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
                                distance = self._haversine_distance(
                                    lat, lon, node_lat, node_lon
                                )
                                if distance < closest_distance:
                                    closest_distance = distance
                                    closest_highway_type = highway.get("tags", {}).get(
                                        "highway"
                                    )

            # Estimate road noise
            noise_data = self._estimate_road_noise_level(min_distance, highway_types)

            # Store results
            place.attributes["highway_distance_m"] = (
                round(min_distance, 1) if min_distance else None
            )
            place.attributes["nearest_highway_type"] = closest_highway_type
            place.attributes["road_noise_level_db"] = noise_data["noise_level_db"]
            place.attributes["road_noise_category"] = noise_data["noise_category"]
            place.attributes["nearby_highway_types"] = list(
                set(highway_types)
            )  # Remove duplicates

        except (requests.RequestException, ValueError) as e:
            # Set error attributes if API call fails
            place.attributes["highway_distance_m"] = None
            place.attributes["nearest_highway_type"] = None
            place.attributes["road_noise_level_db"] = None
            place.attributes["road_noise_category"] = "Unknown"
            place.attributes["highway_error"] = str(e)
