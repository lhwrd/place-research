"""Drive times from a self-hosted OSRM server (car profile).

Free and unmetered, unlike Google's Distance Matrix, so GoogleMapsAPI.distance_matrix sends
driving requests here whenever OSRM_URL is set. OSRM has no traffic model: its durations are
free-flow drive times, a little shorter than Google's typical ones.
"""

import logging
from typing import Any, Dict, List, Optional, Tuple

from app.exceptions import ExternalAPIError
from app.integrations.base_client import BaseAPIClient

logger = logging.getLogger(__name__)

METERS_PER_MILE = 1609.34


class OsrmAPI(BaseAPIClient):
    """Client for OSRM's table service: one origin to many destinations."""

    def __init__(self, base_url: str):
        super().__init__(base_url=base_url, timeout=30.0)

    def _get_service_name(self) -> str:
        return "osrm"

    def _get_auth_headers(self) -> Dict[str, str]:
        return {}

    async def validate_api_key(self) -> bool:
        """No key; reachable is enough."""
        return True

    async def distance_matrix(
        self,
        origin: Tuple[float, float],
        destinations: List[Tuple[float, float]],
    ) -> List[Dict[str, Any]]:
        """
        Drive distance and time to each destination, in GoogleMapsAPI.distance_matrix's format.

        Args:
            origin: (lat, lon)
            destinations: (lat, lon) each

        Returns:
            One dict per destination, in order: status "OK" with distance_meters,
            distance_miles, duration_seconds and duration_minutes, or status "ZERO_RESULTS"
            when OSRM finds no route.
        """
        if not destinations:
            return []

        # OSRM takes lon,lat; the origin is coordinate 0
        coords = ";".join(f"{lon:.6f},{lat:.6f}" for lat, lon in [origin, *destinations])
        data = await self._make_request(
            "GET",
            f"table/v1/driving/{coords}",
            params={"sources": "0", "annotations": "duration,distance"},
        )
        if data.get("code") != "Ok":
            raise ExternalAPIError(
                service="osrm",
                message=f"OSRM table failed: {data.get('message') or data.get('code')}",
            )

        durations = _first_row(data.get("durations"))
        distances = _first_row(data.get("distances"))
        results = []
        for i in range(len(destinations)):
            # Column 0 is the origin itself
            seconds = _at(durations, i + 1)
            meters = _at(distances, i + 1)
            if seconds is None or meters is None:
                results.append(
                    {
                        "destination_index": i,
                        "status": "ZERO_RESULTS",
                        "error": "Destination unreachable or invalid",
                    }
                )
                continue
            results.append(
                {
                    "destination_index": i,
                    "distance_meters": round(meters),
                    "distance_miles": round(meters / METERS_PER_MILE, 2),
                    "duration_seconds": round(seconds),
                    "duration_minutes": int(seconds / 60),
                    "status": "OK",
                }
            )

        logger.info(
            "OSRM table: %d destinations, %d routed",
            len(results),
            sum(1 for r in results if r["status"] == "OK"),
        )
        return results


def _first_row(matrix: Optional[List[List[Optional[float]]]]) -> List[Optional[float]]:
    return matrix[0] if matrix else []


def _at(row: List[Optional[float]], i: int) -> Optional[float]:
    return row[i] if i < len(row) else None
