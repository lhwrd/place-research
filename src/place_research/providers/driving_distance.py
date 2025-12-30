import json
import logging
import os

import googlemaps

from ..interfaces import ProviderNameMixin
from ..models.results import DistanceResult, DistancesResult


class DistanceConfig:
    def __init__(self, config_path):
        self.config_path = config_path
        self.addresses = self.load_config()

    def load_config(self):
        if not os.path.exists(self.config_path):
            raise FileNotFoundError(
                f"Distances config file not found: {self.config_path}"
            )
        with open(self.config_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("addresses", {})


class DistanceProvider(ProviderNameMixin):
    def __init__(self):
        self.api_key = os.getenv("GOOGLE_MAPS_API_KEY")
        self.distance_config = DistanceConfig(os.getenv("DISTANCE_CONFIG_PATH"))
        self.logger = logging.getLogger(__name__)

    async def fetch_place_data(self, place) -> DistancesResult:
        # Use Google Maps distance matrix API to get distances to addresses
        if not self.distance_config.addresses:
            self.logger.error("No addresses configured.")
            return DistancesResult()

        gmaps = googlemaps.Client(key=self.api_key, queries_per_second=5)
        coordinates = (place.latitude, place.longitude)

        distances = {}
        for name, address in self.distance_config.addresses.items():

            matrix_result = gmaps.distance_matrix(  # type: ignore
                origins=[coordinates],
                destinations=[address],
                mode="driving",
                units="metric",
            )
            try:
                element = matrix_result["rows"][0]["elements"][0]
                if element["status"] == "OK":
                    distance_km = element["distance"]["value"] / 1000.0
                    duration_m = element["duration"]["value"] / 60.0
                    distances[name] = DistanceResult(
                        distance_km=distance_km, duration_m=duration_m
                    )
                else:
                    self.logger.error(
                        "Distance matrix error for %s: %s", name, element["status"]
                    )
            except (KeyError, IndexError) as e:
                self.logger.error(
                    "Error parsing distance matrix result for %s: %s", name, e
                )
        return DistancesResult(distances=distances)
