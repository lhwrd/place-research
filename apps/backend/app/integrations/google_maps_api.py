"""Google Maps API integration."""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from app.core.config import settings
from app.exceptions import GoogleMapsAPIError
from app.integrations.base_client import BaseAPIClient, retry_on_failure

logger = logging.getLogger(__name__)


class GoogleMapsAPI(BaseAPIClient):
    """
    Google Maps API client.

    Provides access to:
    - Geocoding API
    - Distance Matrix API
    - Directions API
    """

    # API endpoints
    GEOCODING_ENDPOINT = "geocode/json"
    DISTANCE_MATRIX_ENDPOINT = "distancematrix/json"
    DIRECTIONS_ENDPOINT = "directions/json"

    def __init__(self):
        """Initialize Google Maps API client."""
        super().__init__(
            base_url="https://maps.googleapis.com/maps/api",
            api_key=settings.google_maps_api_key,
            timeout=30.0,
            rate_limit_per_second=50,  # Google's default is higher, but be conservative
        )

    def _get_service_name(self) -> str:
        """Return service name."""
        return "google_maps"

    def _get_auth_headers(self) -> Dict[str, str]:
        """Google Maps uses query param for auth, not headers."""
        return {}

    async def validate_api_key(self) -> bool:
        """Validate API key by making a simple geocoding request."""
        try:
            result = await self.geocode("1600 Amphitheatre Parkway, Mountain View, CA")
            return result is not None
        except GoogleMapsAPIError:
            return False

    # Geocoding API

    @retry_on_failure(max_retries=3, backoff_factor=1.0)
    async def geocode(
        self, address: str, components: Optional[Dict[str, str]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Geocode an address to get coordinates and formatted address.

        Args:
            address: Address to geocode
            components: Optional component filters (e.g., {"country": "US"})

        Returns:
            Dictionary with geocoding results or None if not found

        Example return:
            {
                "formatted_address": "123 Main St, Seattle, WA 98101, USA",
                "latitude": 47.6062,
                "longitude": -122.3321,
                "city": "Seattle",
                "state": "WA",
                "zip_code": "98101",
                "county": "King County",
                "country": "United States"
            }
        """
        params = {"address": address, "key": self.api_key}

        if components:
            # Format:  "country: US|postal_code:98101"
            components_str = "|".join(f"{k}:{v}" for k, v in components.items())
            params["components"] = components_str

        try:
            data = await self._make_request("GET", self.GEOCODING_ENDPOINT, params=params)

            if data.get("status") == "OK" and data.get("results"):
                result = data["results"][0]
                return self._parse_geocode_result(result)
            elif data.get("status") == "ZERO_RESULTS":
                logger.warning(f"No geocoding results for address: {address}")
                return None
            else:
                error_msg = data.get("error_message", data.get("status"))
                raise GoogleMapsAPIError(
                    message=f"Geocoding failed:  {error_msg}", api_status_code=200
                )

        except Exception as e:
            logger.error(f"Geocoding error for '{address}': {str(e)}")
            raise

    @retry_on_failure(max_retries=3, backoff_factor=1.0)
    async def reverse_geocode(self, latitude: float, longitude: float) -> Optional[Dict[str, Any]]:
        """
        Reverse geocode coordinates to get address.

        Args:
            latitude: Latitude
            longitude: Longitude

        Returns:
            Dictionary with address information
        """
        params = {"latlng": f"{latitude},{longitude}", "key": self.api_key}

        try:
            data = await self._make_request("GET", self.GEOCODING_ENDPOINT, params=params)

            if data.get("status") == "OK" and data.get("results"):
                result = data["results"][0]
                return self._parse_geocode_result(result)

            return None

        except Exception as e:
            logger.error(f"Reverse geocoding error for ({latitude}, {longitude}): {str(e)}")
            raise

    def _parse_geocode_result(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Parse geocoding result into standardized format."""
        geometry = result.get("geometry", {})
        location = geometry.get("location", {})

        # Extract address components
        components = {}
        for component in result.get("address_components", []):
            types = component.get("types", [])

            if "locality" in types:
                components["city"] = component.get("long_name")
            elif "administrative_area_level_1" in types:
                components["state"] = component.get("short_name")
            elif "postal_code" in types:
                components["zip_code"] = component.get("long_name")
            elif "administrative_area_level_2" in types:
                components["county"] = component.get("long_name")
            elif "country" in types:
                components["country"] = component.get("long_name")

        return {
            "formatted_address": result.get("formatted_address"),
            "latitude": location.get("lat"),
            "longitude": location.get("lng"),
            "place_id": result.get("place_id"),
            **components,
        }

    # Distance Matrix API

    @retry_on_failure(max_retries=3, backoff_factor=1.0)
    async def distance_matrix(
        self,
        origin: Tuple[float, float],
        destinations: List[Tuple[float, float]],
        mode: str = "driving",
        departure_time: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        """
        Calculate distance and duration to multiple destinations.

        Args:
            origin: Origin coordinates (lat, lon)
            destinations:  List of destination coordinates
            mode:  Travel mode (driving, walking, bicycling, transit)
            departure_time: Optional departure time for traffic estimates

        Returns:
            List of distance/duration information for each destination

        Example return:
            [
                {
                    "destination_index": 0,
                    "distance_miles": 5.2,
                    "distance_meters": 8369,
                    "duration_minutes": 12,
                    "duration_seconds": 720,
                    "duration_in_traffic_minutes": 18,  # If departure_time provided
                    "status": "OK"
                },
                ...
            ]
        """
        # Format origins and destinations
        origin_str = f"{origin[0]},{origin[1]}"
        destinations_str = "|".join(f"{lat},{lon}" for lat, lon in destinations)

        params = {
            "origins": origin_str,
            "destinations": destinations_str,
            "mode": mode,
            "units": "imperial",  # Use miles
            "key": self.api_key,
        }

        # Add departure time for traffic data
        if departure_time:
            # Convert to Unix timestamp
            timestamp = int(departure_time.timestamp())
            params["departure_time"] = timestamp
        elif mode == "driving":
            # Use "now" for current traffic
            params["departure_time"] = "now"

        try:
            data = await self._make_request("GET", self.DISTANCE_MATRIX_ENDPOINT, params=params)

            if data.get("status") != "OK":
                error_msg = data.get("error_message", data.get("status"))
                raise GoogleMapsAPIError(
                    message=f"Distance matrix failed: {error_msg}", api_status_code=200
                )

            # Parse results
            results = []
            rows = data.get("rows", [])

            if rows:
                elements = rows[0].get("elements", [])

                for i, element in enumerate(elements):
                    status = element.get("status")

                    if status == "OK":
                        distance = element.get("distance", {})
                        duration = element.get("duration", {})
                        duration_in_traffic = element.get("duration_in_traffic", {})

                        result = {
                            "destination_index": i,
                            "distance_meters": distance.get("value"),
                            "distance_miles": round(distance.get("value", 0) / 1609.34, 2),
                            "duration_seconds": duration.get("value"),
                            "duration_minutes": int(duration.get("value", 0) / 60),
                            "status": status,
                        }

                        # Add traffic duration if available
                        if duration_in_traffic:
                            result["duration_in_traffic_seconds"] = duration_in_traffic.get("value")
                            result["duration_in_traffic_minutes"] = int(
                                duration_in_traffic.get("value", 0) / 60
                            )

                        results.append(result)
                    else:
                        # Handle failed destination
                        results.append(
                            {
                                "destination_index": i,
                                "status": status,
                                "error": "Destination unreachable or invalid",
                            }
                        )

            return results

        except Exception as e:
            logger.error(f"Distance matrix error: {str(e)}")
            raise

    # Directions API

    @retry_on_failure(max_retries=3, backoff_factor=1.0)
    async def get_directions(
        self,
        origin: Tuple[float, float],
        destination: Tuple[float, float],
        mode: str = "driving",
        alternatives: bool = False,
    ) -> Dict[str, Any]:
        """
        Get detailed directions between two points.

        Args:
            origin: Origin coordinates (lat, lon)
            destination:  Destination coordinates (lat, lon)
            mode: Travel mode (driving, walking, bicycling, transit)
            alternatives: Whether to return alternative routes

        Returns:
            Directions with route information and steps
        """
        params = {
            "origin": f"{origin[0]},{origin[1]}",
            "destination": f"{destination[0]},{destination[1]}",
            "mode": mode,
            "alternatives": "true" if alternatives else "false",
            "key": self.api_key,
        }

        try:
            data = await self._make_request("GET", self.DIRECTIONS_ENDPOINT, params=params)

            if data.get("status") != "OK":
                error_msg = data.get("error_message", data.get("status"))
                raise GoogleMapsAPIError(
                    message=f"Directions failed: {error_msg}", api_status_code=200
                )

            routes = data.get("routes", [])

            if not routes:
                return {}

            # Return the first (best) route
            route = routes[0]
            leg = route["legs"][0]  # Single origin/destination has one leg

            return {
                "distance_miles": round(leg["distance"]["value"] / 1609.34, 2),
                "duration_minutes": int(leg["duration"]["value"] / 60),
                "start_address": leg["start_address"],
                "end_address": leg["end_address"],
                "steps": [
                    {
                        "instruction": step["html_instructions"],
                        "distance": step["distance"]["text"],
                        "duration": step["duration"]["text"],
                    }
                    for step in leg.get("steps", [])
                ],
                "polyline": route["overview_polyline"]["points"],
            }

        except Exception as e:
            logger.error(f"Directions error:  {str(e)}")
            raise
