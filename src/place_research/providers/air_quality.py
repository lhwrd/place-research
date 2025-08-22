import os
from dotenv import load_dotenv

import requests

from ..models.place import Place

load_dotenv()

class AirQualityProvider:
    def __init__(self, config=None):
        self.config = config
        self._api_url = "https://www.airnowapi.org/aq/forecast/latLong/"

    def fetch_place_data(self, place: Place):
        """Fetch air quality data for a specific place."""
        api_key = os.getenv("AIRNOW_API_KEY")
        params = {
            "API_KEY": api_key,
            "latitude": place.coordinates[0],
            "longitude": place.coordinates[1],
            "format": "application/json",
            "distance": 50
        }
        response = requests.get(self._api_url, params=params, timeout=10)
        response.raise_for_status()
        json_data = response.json()
        if len(json_data) == 0:
            place.attributes["air_quality"] = "No data"
            return

        place.attributes["air_quality"] = json_data[0].get("AQI", "No data")
        place.attributes["air_quality_category"] = json_data[0].get("Category", {}).get("Name", "No data")
