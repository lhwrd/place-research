import logging
from pathlib import Path
from typing import Any, Dict, Optional

import geopandas as gpd
from shapely.geometry import Point

from app.core.config import settings
from app.services.enrichment.base_provider import (
    BaseEnrichmentProvider,
    ProviderCategory,
    ProviderMetadata,
    ProviderResult,
)


class RailroadProvider(BaseEnrichmentProvider):
    def __init__(self):
        self._raillines_data = None
        self.logger = logging.getLogger(__name__)

        self._load_raillines_data()

    @property
    def metadata(self) -> ProviderMetadata:
        return ProviderMetadata(
            name="railroad_provider",
            category=ProviderCategory.ENVIRONMENTAL,
            enabled=True,
            description="Provides proximity to railroad lines using local GeoJSON data.",
            version="1.0.0",
            requires_api_key=False,
            cost_per_call=0.0,  # No external API calls
        )

    def _load_raillines_data(self):
        """Load railroad lines data from the configured GeoJSON file."""
        if self._raillines_data is not None:
            self.logger.debug("Railroad lines data already loaded.")
            return

        raillines_path = settings.raillines_path
        if not raillines_path:
            self.logger.error("RAILLINES_PATH environment variable not set.")
            raise ValueError("raillines_path not configured")

        path = Path(raillines_path)
        if not path.exists():
            self.logger.error("Railroad lines file not found: %s", raillines_path)
            raise FileNotFoundError(f"Railroad lines file not found: {raillines_path}")

        self.logger.debug("Loading railroad lines data from %s", raillines_path)
        self._raillines_data = gpd.read_file(path)

        if self._raillines_data.crs is None:
            self.logger.error("Railroad lines data must have a defined CRS.")
            raise ValueError("Railroad lines data must have a defined CRS")

    async def enrich(
        self,
        latitude: float,
        longitude: float,
        address: str,
        property_data: Optional[Dict[str, Any]] = None,
        user_preferences: Optional[Dict[str, Any]] = None,
    ) -> ProviderResult:
        """
        Enrich property with provider-specific data.

        Args:
            latitude: Property latitude
            longitude: Property longitude
            address: Property address
            property_data: Additional property information
            user_preferences: User-specific preferences

        Returns:
            ProviderResult with enrichment data
        """
        self.logger.info("Fetching railroad data for place: %s", (address,))

        if not isinstance(self._raillines_data, gpd.GeoDataFrame):
            self.logger.error("Railroad lines data not loaded.")
            raise ValueError("Railroad lines data not loaded")

        self.logger.debug("Parsed coordinates for place: %s", (latitude, longitude))
        # Swap to (lng, lat) for Point
        place_point = Point(longitude, latitude)

        # Ensure both GeoDataFrames are in the same CRS
        rail_gdf = self._raillines_data.to_crs(epsg=3857)
        point_gdf = gpd.GeoDataFrame(geometry=[place_point], crs="EPSG:4326").to_crs(epsg=3857)

        # Find the nearest railroad line
        distances = rail_gdf.distance(point_gdf.geometry[0])
        nearest_idx = distances.idxmin()
        nearest_distance = int(distances.loc[nearest_idx])
        self.logger.info("Nearest railroad distance for place: %d meters", nearest_distance)

        # For now, just indicate that railroad data is available
        return ProviderResult(
            provider_name=self.metadata.name,
            data={"railroad_distance_m": nearest_distance},
            success=True,
            api_calls_made=0,
        )

    async def validate_config(self) -> bool:
        """
        Validate provider configuration (API keys, etc.).

        Returns:
            True if configuration is valid
        """
        try:
            self._load_raillines_data()
            return True
        except (ValueError, FileNotFoundError) as e:
            self.logger.error("RailroadProvider configuration validation failed: %s", e)
            return False
