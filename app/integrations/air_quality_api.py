import logging
from typing import Any, Dict, Optional

from app.exceptions.external_api import ExternalAPIError

from .base_client import BaseAPIClient

logger = logging.getLogger(__name__)

# US EPA AQI bands: (upper bound inclusive, category name)
AQI_CATEGORIES = [
    (50, "Good"),
    (100, "Moderate"),
    (150, "Unhealthy for Sensitive Groups"),
    (200, "Unhealthy"),
    (300, "Very Unhealthy"),
]


def aqi_category(aqi: Optional[float]) -> Optional[str]:
    """Map a US AQI value to its EPA category name."""
    if aqi is None:
        return None
    for upper, name in AQI_CATEGORIES:
        if aqi <= upper:
            return name
    return "Hazardous"


class AirQualityAPIClient(BaseAPIClient):
    """
    Open-Meteo air quality client (no API key).

    Replaced AirNow, which retired its lat/long web services on October 1, 2026.
    Values are modelled (CAMS) for the location rather than read from the nearest
    monitoring station.
    """

    AIR_QUALITY_ENDPOINT = "v1/air-quality"

    def __init__(self):
        super().__init__(
            base_url="https://air-quality-api.open-meteo.com",
            api_key=None,
            timeout=10.0,
            rate_limit_per_second=1.0,
        )

    def _get_service_name(self) -> str:
        """Return service name."""
        return "air_quality"

    async def validate_api_key(self) -> bool:
        """No key is needed; check the API answers."""
        try:
            return bool(await self.get_air_quality(latitude=34.0522, longitude=-118.2437))
        except ExternalAPIError:
            return False

    async def get_air_quality(self, latitude: float, longitude: float) -> Dict[str, Any]:
        """
        Fetch current air quality for a location.

        Returns:
            {"aqi", "category", "pm2_5", "ozone"}, or {} if unavailable
        """
        logger.info(
            "Fetching air quality data for (%.6f, %.6f)",
            latitude,
            longitude,
            extra={"latitude": latitude, "longitude": longitude},
        )

        params = {
            "latitude": latitude,
            "longitude": longitude,
            "current": "us_aqi,pm2_5,ozone",
        }
        try:
            response = await self._make_request(
                method="GET",
                endpoint=self.AIR_QUALITY_ENDPOINT,
                params=params,
            )
        except ExternalAPIError as e:
            logger.error(
                "Failed to fetch air quality data for (%.6f, %.6f): %s",
                latitude,
                longitude,
                e.message,
                extra={"latitude": latitude, "longitude": longitude, "error": e.message},
            )
            return {}

        current = response.get("current") or {}
        aqi = current.get("us_aqi")
        if aqi is None:
            logger.warning("No air quality data found for (%.6f, %.6f)", latitude, longitude)
            return {}

        result = {
            "aqi": aqi,
            "category": aqi_category(aqi),
            "pm2_5": current.get("pm2_5"),
            "ozone": current.get("ozone"),
        }
        logger.info(
            "Air quality data retrieved: AQI=%s, category=%s",
            result["aqi"],
            result["category"],
            extra={"aqi": result["aqi"], "category": result["category"]},
        )
        return result
