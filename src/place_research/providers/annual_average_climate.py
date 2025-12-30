import logging
import os

import pandas as pd

from place_research.interfaces import ProviderNameMixin
from place_research.models.place import Place
from place_research.models.results import AnnualAverageClimateResult


class AnnualAverageClimateProvider(ProviderNameMixin):
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.path_to_data = os.getenv("ANNUAL_CLIMATE_PATH")
        self.data = self.load_data(self.path_to_data)

    def load_data(self, path) -> pd.DataFrame:
        return pd.read_csv(path)

    async def fetch_place_data(self, place: Place) -> AnnualAverageClimateResult | None:
        lat, lon = place.latitude, place.longitude

        # Find the nearest station
        df = self.data.copy()
        df["distance"] = (
            (df["LATITUDE"] - lat) ** 2 + (df["LONGITUDE"] - lon) ** 2
        ) ** 0.5
        nearest_station = df.loc[df["distance"].idxmin()].to_dict()

        annual_avg_temp = nearest_station["ANN-TAVG-NORMAL"]
        annual_avg_precip = nearest_station["ANN-PRCP-NORMAL"]
        self.logger.info(
            "Annual climate data fetched for place with latitude: %s and longitude: %s",
            lat,
            lon,
        )
        return AnnualAverageClimateResult(
            annual_average_temperature=annual_avg_temp,
            annual_average_precipitation=annual_avg_precip,
        )
