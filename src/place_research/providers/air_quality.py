import logging
import os

import requests
from dotenv import load_dotenv

from ..models.place import Place

load_dotenv()


class AirQualityProvider:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self._api_url = "https://www.airnowapi.org/aq/forecast/latLong/"

    def fetch_place_data(self, place: Place):
        """Fetch air quality data for a specific place."""
        self.logger.debug("Fetching air quality data...")
        if not place.geolocation:
            self.logger.debug("Geolocation not available.")
            return

        if place.air_quality and place.air_quality_category:
            self.logger.info(
                "Air quality data already fetched for place ID %s", place.id
            )
            return

        coordinates = [float(x) for x in place.geolocation.split(";")]
        api_key = os.getenv("AIRNOW_API_KEY")
        params = {
            "API_KEY": api_key,
            "latitude": coordinates[0],
            "longitude": coordinates[1],
            "format": "application/json",
            "distance": 50,
        }
        response = requests.get(self._api_url, params=params, timeout=10)
        response.raise_for_status()
        json_data = response.json()
        if len(json_data) == 0:
            place.air_quality = "No data"
            place.air_quality_category = "No data"
            self.logger.debug("No air quality data found.")
            return
        air_quality = json_data[0].get("AQI")
        air_quality_category = json_data[0].get("Category", {}).get("Name", "No data")
        self.logger.debug("Air quality data fetched successfully.")

        place.air_quality = air_quality
        place.air_quality_category = air_quality_category
