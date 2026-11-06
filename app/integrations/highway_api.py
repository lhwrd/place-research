import asyncio
import logging

import httpx

from .base_client import BaseAPIClient

logger = logging.getLogger(__name__)

# The public Overpass instance answers 429/502/503/504 when it's at capacity and asks
# clients to retry with exponential backoff
RETRY_STATUSES = (429, 502, 503, 504)
MAX_ATTEMPTS = 4
BACKOFF_SECONDS = 2.0


class HighwayAPIClient(BaseAPIClient):
    def __init__(self):
        super().__init__(
            base_url="https://overpass-api.de/api/interpreter",
            api_key=None,  # Assuming no API key is required
            # Longer than the query's own [timeout:25] so the server, not us, gives up first
            timeout=40.0,
            rate_limit_per_second=10.0,
        )

    def _get_service_name(self) -> str:
        return "highway_api"

    async def fetch_nearby_highways(
        self, latitude: float, longitude: float, radius_miles: float = 10.0
    ) -> dict:
        """Fetch nearby highways for a given location."""
        # Overpass QL query for highways within radius
        # highway=motorway, trunk, primary are the major roads that generate most noise
        radius_meters = radius_miles * 1609.34  # Convert miles to meters

        # pylint: disable=line-too-long
        query = f"""
        [out:json][timeout:25];
        (
          way["highway"~"^(motorway|trunk|primary)$"](around:{radius_meters},{latitude},{longitude});
        );
        out geom;
        """

        async with self.client as client:
            for attempt in range(1, MAX_ATTEMPTS + 1):
                try:
                    response = await client.post(
                        self.base_url,
                        data={"data": query},
                        headers={"Content-Type": "application/x-www-form-urlencoded"},
                    )
                except httpx.TimeoutException:
                    if attempt == MAX_ATTEMPTS:
                        raise
                    retry_reason = "timeout"
                else:
                    if response.status_code not in RETRY_STATUSES or attempt == MAX_ATTEMPTS:
                        response.raise_for_status()
                        return response.json()
                    retry_reason = f"HTTP {response.status_code}"

                delay = BACKOFF_SECONDS * 2 ** (attempt - 1)
                logger.warning(
                    "Overpass busy (%s), retrying in %.0fs (attempt %d/%d)",
                    retry_reason,
                    delay,
                    attempt,
                    MAX_ATTEMPTS,
                )
                await asyncio.sleep(delay)
        raise RuntimeError("unreachable")

    async def validate_api_key(self) -> bool:
        """Validate that the API is reachable (no API key needed)."""
        try:
            async with self.client as client:
                response = await client.get(self.base_url)
                response.raise_for_status()
                return True
        except (httpx.HTTPError, httpx.RequestError):
            return False
