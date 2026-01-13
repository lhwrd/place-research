from typing import Any

from app.integrations.osrm_api import OSRMAPIClient


class DistanceService:
    def __init__(self):
        """Initialize distance service."""
        self.osrm_api = OSRMAPIClient()

    async def calculate_distances(
        self,
        origin_lat: float,
        origin_lon: float,
        destinations: list[tuple[float, float]],
    ) -> list[dict[str, Any]]:
        """Calculate distances from origin to multiple destinations."""
        distance_results = await self.osrm_api.distance_matrix(
            origin=(origin_lat, origin_lon),
            destinations=destinations,
        )
        return distance_results
