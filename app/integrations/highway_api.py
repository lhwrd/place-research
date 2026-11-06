import httpx

from .base_client import BaseAPIClient, send_with_retry


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

        # The public instance answers 429/5xx when it's at capacity and asks clients to
        # retry with exponential backoff
        async with self.client as client:
            response = await send_with_retry(
                lambda: client.post(
                    self.base_url,
                    data={"data": query},
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                ),
                service="Overpass",
            )
            response.raise_for_status()
            return response.json()

    async def validate_api_key(self) -> bool:
        """Validate that the API is reachable (no API key needed)."""
        try:
            async with self.client as client:
                response = await client.get(self.base_url)
                response.raise_for_status()
                return True
        except (httpx.HTTPError, httpx.RequestError):
            return False
