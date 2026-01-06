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
