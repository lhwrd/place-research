"""Google Maps API integration."""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from app.core.config import settings
from app.exceptions import GoogleMapsAPIError
from app.integrations.base_client import BaseAPIClient

logger = logging.getLogger(__name__)


class GoogleMapsAPI(BaseAPIClient):
    """
    Google Maps API client.

    Provides access to:
    - Geocoding API
    - Distance Matrix API
    - Directions API
    - Street View metadata (free; needs the Street View Static API enabled)
    """

    # API endpoints
    GEOCODING_ENDPOINT = "geocode/json"
    DISTANCE_MATRIX_ENDPOINT = "distancematrix/json"
    STREET_VIEW_METADATA_ENDPOINT = "streetview/metadata"

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
            logger.info("Validating Google Maps API key")
            result = await self.geocode("1600 Amphitheatre Parkway, Mountain View, CA")
            is_valid = result is not None
            logger.info(
                "Google Maps API key validation: %s",
                "success" if is_valid else "failed",
            )
            return is_valid
        except GoogleMapsAPIError as e:
            logger.warning("Google Maps API key validation failed: %s", str(e))
            return False

    # Geocoding API

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
        logger.info(
            "Geocoding address: %s",
            address,
            extra={"address": address, "components": components},
        )

        params = {"address": address, "key": self.api_key}

        if components:
            # Format:  "country: US|postal_code:98101"
            components_str = "|".join(f"{k}:{v}" for k, v in components.items())
            params["components"] = components_str

        try:
            data = await self._make_request("GET", self.GEOCODING_ENDPOINT, params=params)

            if data.get("status") == "OK" and data.get("results"):
                result = data["results"][0]
                parsed_result = self._parse_geocode_result(result)
                logger.info(
                    "Successfully geocoded address: %s -> (%.6f, %.6f)",
                    address,
                    parsed_result.get("latitude"),
                    parsed_result.get("longitude"),
                    extra={"address": address, "result": parsed_result},
                )
                return parsed_result
            elif data.get("status") == "ZERO_RESULTS":
                logger.warning("No geocoding results for address: %s", address)
                return None
            else:
                error_msg = data.get("error_message", data.get("status"))
                logger.error(
                    "Geocoding failed for address '%s': %s",
                    address,
                    error_msg,
                    extra={
                        "address": address,
                        "error_message": error_msg,
                        "status": data.get("status"),
                    },
                )
                raise GoogleMapsAPIError(
                    message=f"Geocoding failed:  {error_msg}", api_status_code=200
                )

        except Exception as e:
            logger.error(
                "Geocoding error for address '%s': %s",
                address,
                str(e),
                extra={"address": address, "error": str(e)},
                exc_info=True,
            )
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
            departure_time: Departure time for a traffic estimate (billed at a higher
                rate). Without one, durations are typical drive times.

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

        logger.info(
            "Distance matrix request: origin=(%.6f, %.6f), %d destinations, mode=%s",
            origin[0],
            origin[1],
            len(destinations),
            mode,
            extra={
                "origin": origin,
                "destination_count": len(destinations),
                "mode": mode,
                "has_departure_time": departure_time is not None,
            },
        )

        params = {
            "origins": origin_str,
            "destinations": destinations_str,
            "mode": mode,
            "units": "imperial",  # Use miles
            "key": self.api_key,
        }

        # Traffic estimates only when asked for: a departure time bills every destination at
        # the Advanced rate (twice the basic one), and "now" would make drive times depend on
        # the hour a property happened to be enriched
        if departure_time:
            params["departure_time"] = int(departure_time.timestamp())

        try:
            data = await self._make_request("GET", self.DISTANCE_MATRIX_ENDPOINT, params=params)

            if data.get("status") != "OK":
                error_msg = data.get("error_message", data.get("status"))
                logger.error(
                    "Distance matrix failed: %s",
                    error_msg,
                    extra={
                        "origin": origin,
                        "destination_count": len(destinations),
                        "error_message": error_msg,
                    },
                )
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

            logger.info(
                "Distance matrix completed: %d results, %d successful",
                len(results),
                sum(1 for r in results if r.get("status") == "OK"),
                extra={
                    "total_results": len(results),
                    "successful_results": sum(1 for r in results if r.get("status") == "OK"),
                },
            )
            return results

        except Exception as e:
            logger.error(
                "Distance matrix error for origin (%.6f, %.6f): %s",
                origin[0],
                origin[1],
                str(e),
                extra={
                    "origin": origin,
                    "destination_count": len(destinations),
                    "error": str(e),
                },
                exc_info=True,
            )
            raise

    # Directions API

    # Street View

    async def street_view_metadata(
        self,
        latitude: float,
        longitude: float,
        radius_m: int = 100,
        api_key: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        The nearest outdoor Street View panorama to a point. Metadata requests are free.

        Args:
            api_key: Key to use instead of the client's (e.g. the Street View embed key)

        Returns:
            {"pano_id", "latitude", "longitude", "date"}, or None if there's no
            outdoor panorama within radius_m

        Raises:
            GoogleMapsAPIError: If the request is refused (e.g. the API isn't enabled
                for the key)
        """
        params = {
            "location": f"{latitude},{longitude}",
            "radius": radius_m,
            "source": "outdoor",  # skip indoor and business photospheres
            "key": api_key or self.api_key,
        }
        data = await self._make_request("GET", self.STREET_VIEW_METADATA_ENDPOINT, params=params)
        status = data.get("status")
        if status in ("ZERO_RESULTS", "NOT_FOUND"):
            return None
        if status != "OK":
            raise GoogleMapsAPIError(
                message=f"Street View metadata failed: {data.get('error_message', status)}",
                api_status_code=200,
            )
        location = data.get("location") or {}
        return {
            "pano_id": data.get("pano_id"),
            "latitude": location.get("lat"),
            "longitude": location.get("lng"),
            "date": data.get("date"),
        }
