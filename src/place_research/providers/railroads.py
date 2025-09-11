import os
import logging
from pathlib import Path
from typing import TYPE_CHECKING

import geopandas as gpd
from shapely.geometry import Point

from place_research.interfaces import ProviderNameMixin

if TYPE_CHECKING:
    from ..models import Place


class RailroadProvider(ProviderNameMixin):
    def __init__(self):
        self._raillines_data = None
        self.logger = logging.getLogger(__name__)

    def _load_raillines_data(self):
        """Load railroad lines data from the configured GeoJSON file."""
        if self._raillines_data is not None:
            self.logger.debug("Railroad lines data already loaded.")
            return

        raillines_path = os.getenv("RAILLINES_PATH")
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

    def fetch_place_data(self, place: "Place"):
        """Fetch railroad data for the given place."""
        if place.nearest_railroad:
            self.logger.debug("Already fetched nearest railroad data.")
            return

        self.logger.info("Fetching railroad data for place: %s", place.id)
        self._load_raillines_data()

        if not isinstance(self._raillines_data, gpd.GeoDataFrame):
            self.logger.error("Railroad lines data not loaded.")
            raise ValueError("Railroad lines data not loaded")

        if not place.geolocation:
            self.logger.error("Geolocation must be set on place.")
            raise ValueError("Geolocation must be set.")

        # Note: place.geolocation is (lat;lng) but Point expects (lng, lat)
        coords = [float(x) for x in place.geolocation.split(";")]
        self.logger.debug("Parsed coordinates for place: %s", coords)
        # Swap to (lng, lat) for Point
        place_point = Point(coords[1], coords[0])

        # Ensure both GeoDataFrames are in the same CRS
        rail_gdf = self._raillines_data.to_crs(epsg=3857)
        point_gdf = gpd.GeoDataFrame(geometry=[place_point], crs="EPSG:4326").to_crs(
            epsg=3857
        )

        # Find the nearest railroad line
        distances = rail_gdf.distance(point_gdf.geometry[0])
        nearest_idx = distances.idxmin()
        nearest_distance = int(distances.loc[nearest_idx])
        self.logger.info(
            "Nearest railroad distance for place: %d meters", nearest_distance
        )

        # For now, just indicate that railroad data is available
        place.nearest_railroad = nearest_distance
