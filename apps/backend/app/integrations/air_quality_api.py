import logging
from typing import Any, Dict, List, Union

from app.core.config import settings
from app.exceptions.external_api import ExternalAPIError

from .base_client import BaseAPIClient

logger = logging.getLogger(__name__)


class AirQualityAPIClient(BaseAPIClient):
    """
    Air Now API client for fetching air quality data.
    """

    FORECAST_ENDPOINT = "aq/forecast/latLong/"

    def __init__(self):
        super().__init__(
            base_url="https://www.airnowapi.org",
            api_key=settings.airnow_api_key,
            timeout=10.0,
            rate_limit_per_second=1.0,
        )

    def _get_service_name(self) -> str:
        """Return service name."""
        return "air_quality"

    async def validate_api_key(self) -> bool:
        """
        Validate the API key by making a test request.

        Returns:
            True if the API key is valid, False otherwise.
        """
        try:
            params = {
                "API_KEY": self.api_key,
                "latitude": "34.0522",  # Example coordinates (Los Angeles)
                "longitude": "-118.2437",
                "format": "application/json",
                "distance": 25,
            }
            data = await self._make_request(
                method="GET",
                endpoint=self.FORECAST_ENDPOINT,
                params=params,
            )
            if data:
                return True
            return False
        except ExternalAPIError as e:
            logger.error(f"API key validation failed: {e}")
            return False

    async def get_air_quality(
        self, latitude: float, longitude: float, distance: int = 50
    ) -> Dict[str, Any]:
        """
        Fetch air quality data for given latitude and longitude.

        Args:
            latitude: Latitude of the location
            longitude: Longitude of the location
            distance: Distance in miles to search for air quality data

        Returns:
            Air quality data as a dictionary
        """
        logger.info(
            "Fetching air quality data for (%.6f, %.6f) within %d miles",
            latitude,
            longitude,
            distance,
            extra={"latitude": latitude, "longitude": longitude, "distance": distance},
        )

        params = {
            "API_KEY": self.api_key,
            "latitude": str(latitude),
            "longitude": str(longitude),
            "format": "application/json",
            "distance": distance,
        }
        try:
            response = await self._make_request(
                method="GET",
                endpoint=self.FORECAST_ENDPOINT,
                params=params,
            )
            # API returns a list of air quality data
            data: List[Dict[str, Any]] = response if isinstance(response, list) else []
        except ExternalAPIError as e:
            logger.error(
                "Failed to fetch air quality data for (%.6f, %.6f): %s",
                latitude,
                longitude,
                str(e),
                extra={"latitude": latitude, "longitude": longitude, "error": str(e)},
                exc_info=True,
            )
            return {}

        if not data or len(data) == 0:
            logger.warning(
                "No air quality data found for (%.6f, %.6f) within %d miles",
                latitude,
                longitude,
                distance,
            )
            return {}

        logger.debug("Air quality API response: %s", data)

        result: dict = data[0]

        logger.info(
            "Air quality data retrieved: AQI=%s, category=%s",
            result.get("AQI"),
            result.get("Category"),
            extra={
                "aqi": result.get("AQI"),
                "category": result.get("Category"),
            },
        )
        return result
