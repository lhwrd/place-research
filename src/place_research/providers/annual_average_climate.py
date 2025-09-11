from glob import glob
import os
import logging

import pandas as pd

from place_research.interfaces import ProviderNameMixin
from place_research.models.place import Place


class AnnualAverageClimateProvider(ProviderNameMixin):
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.path_to_data = os.getenv("ANNUAL_CLIMATE_PATH")
        self.data = self.load_data(self.path_to_data)

    def load_data(self, path) -> pd.DataFrame:
        return pd.read_csv(path)

    def fetch_place_data(self, place: Place):
        if not place.geolocation:
            self.logger.debug("Geolocation not available.")
            return

        if place.annual_avg_temp and place.annual_avg_precip:
            self.logger.info(
                "Annual climate data already fetched for place ID %s", place.id
            )
            return

        coordinates = [float(x) for x in place.geolocation.split(";")]
        lat, lon = coordinates

        # Find the nearest station
        df = self.data.copy()
        df["distance"] = (
            (df["LATITUDE"] - lat) ** 2 + (df["LONGITUDE"] - lon) ** 2
        ) ** 0.5
        nearest_station = df.loc[df["distance"].idxmin()].to_dict()

        place.annual_avg_temp = nearest_station["ANN-TAVG-NORMAL"]
        place.annual_avg_precip = nearest_station["ANN-PRCP-NORMAL"]
        self.logger.info(
            "Annual climate data fetched for place with geolocation: %s",
            place.geolocation,
        )
