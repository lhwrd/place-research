from typing import Any

from app.exceptions import OSRMAPIError
from app.integrations.base_client import BaseAPIClient


class OSRMAPIClient(BaseAPIClient):
    """
    OSRM API client.

    Provides access to:
    - Route calculation endpoints.
    """

    # API endpoints
    ROUTE_ENDPOINT = "route/v1/driving/{coordinates}"

    def __init__(self):
        """Initialize OSRM API client."""
        super().__init__(
            base_url="http://router.project-osrm.org/",
            timeout=30.0,
            rate_limit_per_second=10,  # Be conservative with public OSRM server
        )

    def _get_service_name(self) -> str:
        """Return service name."""
        return "osrm"

    async def validate_api_key(self) -> bool:
        """OSRM does not require an API key, always return True."""
        return True

    async def get_driving_distance_duration(
        self, start_lat: float, start_lon: float, end_lat: float, end_lon: float
    ) -> dict:
        """Fetch route data between two coordinates.

        Args:
            start_lat (float): Starting latitude.
            start_lon (float): Starting longitude.
            end_lat (float): Ending latitude.
            end_lon (float): Ending longitude.

        Returns:
            dict: Route information including distance and duration.
        """
        coordinates = f"{start_lon},{start_lat};{end_lon},{end_lat}"
        endpoint = self.ROUTE_ENDPOINT.format(coordinates=coordinates)

        params = {
            "overview": "false",
            "alternatives": "false",
            "steps": "false",
        }

        data = await self._make_request("GET", endpoint, params=params)

        if not data or "routes" not in data:
            raise OSRMAPIError("Failed to fetch route data from OSRM API")

        return {
            "distance_meters": data["routes"][0]["distance"],
            "duration_seconds": data["routes"][0]["duration"],
        }

    async def distance_matrix(
        self,
        origin: tuple[float, float],
        destinations: list[tuple[float, float]],
    ) -> list[dict[str, Any]]:
        """Calculate distances from origin to multiple destinations.

        Args:
            origin (tuple): (latitude, longitude) of the origin point.
            destinations (list): List of (latitude, longitude) tuples for destinations.

        Returns:
            list: List of distance and duration info to each destination.
        """
        results = []
        for index, (dest_lat, dest_lon) in enumerate(destinations):
            route_info = await self.get_driving_distance_duration(
                start_lat=origin[0],
                start_lon=origin[1],
                end_lat=dest_lat,
                end_lon=dest_lon,
            )
            results.append(
                {
                    "destination_index": index,
                    "distance_miles": route_info["distance_meters"] / 1609.34,
                    "duration_minutes": route_info["duration_seconds"] / 60,
                }
            )
        return results
