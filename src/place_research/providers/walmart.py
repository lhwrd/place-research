import math
import os
from typing import TYPE_CHECKING

import requests

if TYPE_CHECKING:
    from ..config import Config
    from ..models import Place


class WalmartProvider:
    def __init__(self, config: "Config | None" = None):
        self.config = config
        self.timeout = config.timeout_seconds if config else 30

        # Get Google Maps API key from environment, config, or provider config
        self.api_key = os.getenv("GOOGLE_MAPS_API_KEY")

        if not self.api_key and config:
            self.api_key = config.get("google_maps_api_key")
            if not self.api_key:
                provider_config = config.get_provider_config("walmart")
                self.api_key = provider_config.get("google_maps_api_key")

        if not self.api_key:
            raise ValueError(
                "Google Maps API key is required for Walmart provider. Set GOOGLE_MAPS_API_KEY environment variable or configure it in config.json"
            )

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

    def _find_nearest_walmart_supercenter(self, lat: float, lon: float) -> dict | None:
        """
        Use Google Maps Places API to find the nearest Walmart Supercenter.
        """
        base_url = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"

        params = {
            "location": f"{lat},{lon}",
            "radius": 50000,  # Search within 50km radius
            "keyword": "Walmart Supercenter",
            "type": "store",
            "key": self.api_key,
        }

        try:
            response = requests.get(base_url, params=params, timeout=self.timeout)
            response.raise_for_status()
            data = response.json()

            if data.get("status") != "OK":
                raise ValueError(
                    f"Google Maps API error: {data.get('status', 'Unknown error')}"
                )

            results = data.get("results", [])

            # Filter for Walmart Supercenters specifically
            walmart_supercenters = []
            for place in results:
                name = place.get("name", "").lower()

                # Check if it's specifically a Walmart Supercenter
                if ("walmart" in name and "supercenter" in name) or (
                    "walmart supercenter" in name
                ):
                    walmart_supercenters.append(place)

            if not walmart_supercenters:
                return None

            # Find the closest one by calculating straight-line distance first
            closest_walmart = None
            min_distance = float("inf")

            for walmart in walmart_supercenters:
                walmart_location = walmart.get("geometry", {}).get("location", {})
                walmart_lat = walmart_location.get("lat")
                walmart_lon = walmart_location.get("lng")

                if walmart_lat is not None and walmart_lon is not None:
                    distance = self._haversine_distance(
                        lat, lon, walmart_lat, walmart_lon
                    )
                    if distance < min_distance:
                        min_distance = distance
                        closest_walmart = {
                            "place_id": walmart.get("place_id"),
                            "name": walmart.get("name"),
                            "address": walmart.get("vicinity", ""),
                            "latitude": walmart_lat,
                            "longitude": walmart_lon,
                            "straight_line_distance_meters": distance,
                            "rating": walmart.get("rating"),
                            "price_level": walmart.get("price_level"),
                            "open_now": walmart.get("opening_hours", {}).get(
                                "open_now"
                            ),
                        }

            return closest_walmart

        except requests.RequestException as e:
            raise ValueError(
                f"Failed to fetch Walmart data from Google Maps API: {e}"
            ) from e

    def _get_driving_distance_and_time(
        self, origin_lat: float, origin_lon: float, dest_lat: float, dest_lon: float
    ) -> dict:
        """
        Use Google Maps Distance Matrix API to get driving distance and time.
        """
        base_url = "https://maps.googleapis.com/maps/api/distancematrix/json"

        params = {
            "origins": f"{origin_lat},{origin_lon}",
            "destinations": f"{dest_lat},{dest_lon}",
            "mode": "driving",
            "units": "metric",
            "key": self.api_key,
        }

        try:
            response = requests.get(base_url, params=params, timeout=self.timeout)
            response.raise_for_status()
            data = response.json()

            if data.get("status") != "OK":
                raise ValueError(
                    f"Google Maps Distance Matrix API error: {data.get('status', 'Unknown error')}"
                )

            rows = data.get("rows", [])
            if not rows or not rows[0].get("elements"):
                raise ValueError("No distance data returned from Google Maps")

            element = rows[0]["elements"][0]
            if element.get("status") != "OK":
                raise ValueError(
                    f"Distance calculation failed: {element.get('status', 'Unknown error')}"
                )

            distance = element.get("distance", {})
            duration = element.get("duration", {})

            return {
                "driving_distance_meters": distance.get("value"),  # Distance in meters
                "driving_distance_text": distance.get(
                    "text"
                ),  # Human readable distance
                "driving_time_seconds": duration.get("value"),  # Duration in seconds
                "driving_time_text": duration.get("text"),  # Human readable duration
            }

        except requests.RequestException as e:
            raise ValueError(
                f"Failed to fetch driving distance from Google Maps API: {e}"
            ) from e

    def fetch_place_data(self, place: "Place"):
        """
        Fetch nearest Walmart Supercenter data for the given place.
        """
        lat, lon = place.coordinates

        try:
            # Find nearest Walmart Supercenter
            nearest_walmart = self._find_nearest_walmart_supercenter(lat, lon)

            if nearest_walmart is None:
                # No Walmart Supercenter found within search radius
                place.attributes["walmart_supercenter_driving_distance_m"] = None
                place.attributes["walmart_supercenter_driving_distance_km"] = None
                place.attributes["walmart_supercenter_driving_time_minutes"] = None
                place.attributes["walmart_supercenter_straight_line_distance_m"] = None
                place.attributes["nearest_walmart_supercenter_name"] = None
                place.attributes["nearest_walmart_supercenter_address"] = None
                place.attributes["nearest_walmart_supercenter_coordinates"] = None
                place.attributes["nearest_walmart_supercenter_rating"] = None
                place.attributes["nearest_walmart_supercenter_open_now"] = None
                place.attributes["walmart_supercenter_distance_category"] = None
                return

            # Get driving distance and time
            driving_data = self._get_driving_distance_and_time(
                lat, lon, nearest_walmart["latitude"], nearest_walmart["longitude"]
            )

            # Store Walmart Supercenter data
            driving_distance_m = driving_data["driving_distance_meters"]
            driving_time_s = driving_data["driving_time_seconds"]

            place.attributes["walmart_supercenter_driving_distance_m"] = (
                driving_distance_m
            )
            place.attributes["walmart_supercenter_driving_distance_km"] = (
                round(driving_distance_m / 1000, 2) if driving_distance_m else None
            )
            place.attributes["walmart_supercenter_driving_time_minutes"] = (
                round(driving_time_s / 60, 1) if driving_time_s else None
            )
            place.attributes["walmart_supercenter_driving_distance_text"] = (
                driving_data["driving_distance_text"]
            )
            place.attributes["walmart_supercenter_driving_time_text"] = driving_data[
                "driving_time_text"
            ]

            # Keep straight line distance for reference
            place.attributes["walmart_supercenter_straight_line_distance_m"] = round(
                nearest_walmart["straight_line_distance_meters"], 1
            )

            place.attributes["nearest_walmart_supercenter_name"] = nearest_walmart[
                "name"
            ]
            place.attributes["nearest_walmart_supercenter_address"] = nearest_walmart[
                "address"
            ]
            place.attributes["nearest_walmart_supercenter_coordinates"] = [
                nearest_walmart["latitude"],
                nearest_walmart["longitude"],
            ]
            place.attributes["nearest_walmart_supercenter_rating"] = (
                nearest_walmart.get("rating")
            )
            place.attributes["nearest_walmart_supercenter_open_now"] = (
                nearest_walmart.get("open_now")
            )

            # Add convenience distance categories based on driving distance
            if driving_distance_m <= 1000:
                distance_category = "Very Close"  # Within 1km driving
            elif driving_distance_m <= 5000:
                distance_category = "Close"  # Within 5km driving
            elif driving_distance_m <= 15000:
                distance_category = "Moderate"  # Within 15km driving
            elif driving_distance_m <= 30000:
                distance_category = "Far"  # Within 30km driving
            else:
                distance_category = "Very Far"  # Beyond 30km driving

            place.attributes["walmart_supercenter_distance_category"] = (
                distance_category
            )

        except (requests.RequestException, ValueError) as e:
            # Set error attributes if API call fails
            place.attributes["walmart_supercenter_driving_distance_m"] = None
            place.attributes["walmart_supercenter_driving_distance_km"] = None
            place.attributes["walmart_supercenter_driving_time_minutes"] = None
            place.attributes["walmart_supercenter_straight_line_distance_m"] = None
            place.attributes["nearest_walmart_supercenter_name"] = None
            place.attributes["nearest_walmart_supercenter_address"] = None
            place.attributes["nearest_walmart_supercenter_coordinates"] = None
            place.attributes["nearest_walmart_supercenter_rating"] = None
            place.attributes["nearest_walmart_supercenter_open_now"] = None
            place.attributes["walmart_supercenter_distance_category"] = "Unknown"
            place.attributes["walmart_error"] = str(e)
