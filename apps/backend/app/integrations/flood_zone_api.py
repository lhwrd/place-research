from typing import Dict

from app.core.config import settings

from .base_client import BaseAPIClient


class FloodZoneAPIClient(BaseAPIClient):
    def __init__(self):
        super().__init__(
            base_url="https://api.nationalflooddata.com/v3/data",
            api_key=settings.national_flood_data_api_key,
            timeout=30.0,
            rate_limit_per_second=5.0,
        )

    def _get_service_name(self) -> str:
        return "flood_zone_api"

    def _get_auth_headers(self) -> Dict[str, str]:
        return {"x-api-key": str(self.api_key)}

    async def validate_api_key(self) -> bool:
        """Validate the API key by making a test request."""
        headers = self._get_auth_headers()
        params = {
            "lat": "0",
            "lon": "0",
            "address": "test",
            "searchtype": "addresscoord",
        }
        async with self.client as client:
            response = await client.get(
                self.base_url,
                params=params,
                headers=headers,
            )
            if response.status_code == 401:
                return False
            response.raise_for_status()
            return True

    async def fetch_flood_zone_data(self, latitude: float, longitude: float, address: str) -> dict:
        """Fetch flood zone data for a given location."""
        headers = self._get_auth_headers()
        params = {
            "lat": str(latitude),
            "lon": str(longitude),
            "address": address,
            "searchtype": "addresscoord",
        }
        async with self.client as client:
            response = await client.get(
                self.base_url,
                params=params,
                headers=headers,
            )
            response.raise_for_status()
            return response.json()
