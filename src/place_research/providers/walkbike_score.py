import os
from typing import TYPE_CHECKING

import requests

if TYPE_CHECKING:
    from ..config import Config


class WalkBikeScoreProvider:
    def __init__(self, api_key: str | None = None, config: "Config | None" = None):
        self.config = config
        api_key = api_key or os.getenv("WALKSCORE_API_KEY")
        self.api_key = api_key

        # Use timeout from config if available
        self.timeout = config.timeout_seconds if config else 10

    def fetch_place_data(self, place):
        url = "https://api.walkscore.com/score"
        params = {
            "format": "json",
            "address": place.address,
            "lat": place.coordinates[0],
            "lon": place.coordinates[1],
            "wsapikey": self.api_key,
            "bike": 1,
        }

        response = requests.get(url, params=params, timeout=self.timeout)
        if response.status_code == 200:
            data = response.json()
            place.attributes["walk_score"] = {
                "score": data.get("walkscore"),
                "description": data.get("description"),
            }
            place.attributes["bike_score"] = data.get("bike")
        else:
            place.attributes["walk_score"] = None
            place.attributes["bike_score"] = None
