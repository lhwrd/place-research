import logging
from typing import Any, Dict, Optional

import pandas as pd

from app.core.config import settings
from app.services.enrichment.base_provider import (
    BaseEnrichmentProvider,
    ProviderCategory,
    ProviderMetadata,
    ProviderResult,
)


class AnnualAverageClimateProvider(BaseEnrichmentProvider):
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.data = self._load_data(settings.annual_climate_path)

    @property
    def metadata(self) -> ProviderMetadata:
        return ProviderMetadata(
            name="AnnualAverageClimateProvider",
            category=ProviderCategory.ENVIRONMENTAL,
            enabled=True,
            description="Provides annual average climate data from NOAA.",
            version="1.0.0",
            requires_api_key=False,
            cost_per_call=0.0,
        )

    def _load_data(self, path) -> pd.DataFrame:
        return pd.read_csv(path)

    async def enrich(
        self,
        latitude: float,
        longitude: float,
        address: str,
        property_data: Optional[Dict[str, Any]] = None,
        user_preferences: Optional[Dict[str, Any]] = None,
    ) -> ProviderResult:
        lat, lon = latitude, longitude

        # Find the nearest station
        df = self.data.copy()
        df["distance"] = ((df["LATITUDE"] - lat) ** 2 + (df["LONGITUDE"] - lon) ** 2) ** 0.5
        nearest_station = df.loc[df["distance"].idxmin()].to_dict()

        annual_avg_temp = nearest_station["ANN-TAVG-NORMAL"]
        annual_avg_precip = nearest_station["ANN-PRCP-NORMAL"]
        self.logger.info(
            "Annual climate data fetched for place with latitude: %s and longitude: %s",
            lat,
            lon,
        )
        return ProviderResult(
            provider_name=self.metadata.name,
            data={
                "annual_average_temperature": annual_avg_temp,
                "annual_average_precipitation": annual_avg_precip,
                "station_id": nearest_station["STATION_ID"],
                "station_name": nearest_station["STATION_NAME"],
            },
            success=True,
            api_calls_made=0,
            cached=False,
        )

    async def validate_config(self) -> bool:
        """No configuration needed for this provider."""
        if settings.annual_climate_path and self.data is not None:
            return True
        return False
