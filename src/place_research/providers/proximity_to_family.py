import logging
import os
import googlemaps
from place_research.interfaces import ProviderNameMixin


class FamilyConfig:
    def __init__(self, config_path):
        self.config_path = config_path
        self.addresses = self.load_config()

    def load_config(self):
        import json

        if not os.path.exists(self.config_path):
            raise FileNotFoundError(f"Family config file not found: {self.config_path}")
        with open(self.config_path, "r") as f:
            data = json.load(f)
        return data.get("addresses", {})


class ProximityToFamilyProvider(ProviderNameMixin):
    def __init__(self):
        self.api_key = os.getenv("GOOGLE_MAPS_API_KEY")
        self.family_config = FamilyConfig(os.getenv("FAMILY_CONFIG_PATH"))
        self.logger = logging.getLogger(__name__)

    def fetch_place_data(self, place):
        # Use Google Maps distance matrix API to get distances to family members
        if not self.api_key:
            self.logger.error(
                "Google Maps API key missing. Set GOOGLE_MAPS_API_KEY envvar or config.json"
            )
            return

        if not place.geolocation:
            self.logger.error("Geolocation must be set on place.")
            return

        if not self.family_config.addresses:
            self.logger.error("No family addresses configured.")
            return

        if place.proximity_to_family:
            self.logger.info(
                "Proximity to family data already fetched for place ID %s", place.id
            )
            return

        gmaps = googlemaps.Client(key=self.api_key, queries_per_second=5)
        coordinates = place.geolocation.split(";")
        coordinates = (float(coordinates[0]), float(coordinates[1]))

        if len(coordinates) != 2:
            self.logger.error("Geolocation must be in 'lat;lng' format.")
            return

        distances = {}
        for name, address in self.family_config.addresses.items():

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
                    distances[name] = {
                        "distance_km": distance_km,
                        "duration_m": duration_m,
                    }
                else:
                    self.logger.error(
                        "Distance matrix error for %s: %s", name, element["status"]
                    )
            except (KeyError, IndexError) as e:
                self.logger.error(
                    "Error parsing distance matrix result for %s: %s", name, e
                )
        place.proximity_to_family = distances
