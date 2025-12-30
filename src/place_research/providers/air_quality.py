import logging
import os

import requests
from dotenv import load_dotenv

from ..interfaces import ProviderNameMixin
from ..models.place import Place
from ..models.results import AirQualityResult

load_dotenv()


class AirQualityProvider(ProviderNameMixin):
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self._api_url = "https://www.airnowapi.org/aq/forecast/latLong/"

    def fetch_place_data(self, place: Place) -> AirQualityResult:
        """Fetch air quality data for a specific place."""
        self.logger.debug("Fetching air quality data...")

        api_key = os.getenv("AIRNOW_API_KEY")
        params = {
            "API_KEY": api_key,
            "latitude": str(place.latitude),
            "longitude": str(place.longitude),
            "format": "application/json",
            "distance": 50,
        }
        response = requests.get(self._api_url, params=params, timeout=10)
        response.raise_for_status()
        json_data = response.json()
        if len(json_data) == 0:
            return AirQualityResult(air_quality=None, air_quality_category="No data")

        air_quality = json_data[0].get("AQI")
        air_quality_category = json_data[0].get("Category", {}).get("Name", "No data")
        self.logger.debug("Air quality data fetched successfully.")

        return AirQualityResult(
            air_quality=air_quality, air_quality_category=air_quality_category
        )
