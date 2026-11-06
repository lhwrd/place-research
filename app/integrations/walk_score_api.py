import logging

from app.core.config import settings
from app.exceptions import WalkScoreAPIError
from app.integrations.base_client import BaseAPIClient

logger = logging.getLogger(__name__)


class WalkScoreAPI(BaseAPIClient):
    """
    Walk score and bike score API client.
    """

    WALKSCORE_ENDPOINT = "score"

    def __init__(self):
        super().__init__(
            base_url="https://api.walkscore.com",
            api_key=settings.walkscore_api_key,
            timeout=30,
            rate_limit_per_second=None,
        )

    def _get_service_name(self) -> str:
        """Return service name."""
        return "walkscore"

    async def get_score(self, lat: float, lon: float, address: str) -> dict:
        """Fetch walk score data from Walk Score API."""
        logger.info(
            "Fetching WalkScore for address: %s at (%.6f, %.6f)",
            address,
            lat,
            lon,
            extra={"address": address, "latitude": lat, "longitude": lon},
        )

        params = {
            "format": "json",
            "lat": lat,
            "lon": lon,
            "address": address,
            "wsapikey": self.api_key,
        }
        try:
            data = await self._make_request(
                method="GET",
                endpoint=self.WALKSCORE_ENDPOINT,
                params=params,
            )
            logger.info(
                "WalkScore result: status=%s, walkscore=%s",
                data.get("status"),
                data.get("walkscore"),
                extra={
                    "address": address,
                    "walkscore": data.get("walkscore"),
                    "status": data.get("status"),
                },
            )
            return data
        except WalkScoreAPIError as e:
            logger.error(
                "WalkScore API error for address '%s': %s",
                address,
                str(e),
                extra={"address": address, "error": str(e)},
                exc_info=True,
            )
            raise e

    async def validate_api_key(self) -> bool:
        """Validate the Walk Score API key."""
        try:
            logger.info("Validating WalkScore API key")
            # Use a known location for validation
            data = await self.get_score(
                lat=47.608013,
                lon=-122.335167,
                address="Seattle, WA",
            )
            is_valid = data is not None and "status" in data and data["status"] == 1
            logger.info("WalkScore API key validation: %s", "success" if is_valid else "failed")
            return is_valid
        except WalkScoreAPIError as e:
            logger.warning("WalkScore API key validation failed: %s", str(e))
            return False
