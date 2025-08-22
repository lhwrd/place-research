from pathlib import Path
from typing import TYPE_CHECKING

import geopandas as gpd
from shapely.geometry import Point

if TYPE_CHECKING:
    from ..config import Config
    from ..models import Place


class RailroadProvider:
    def __init__(self, config: "Config | None" = None):
        self.config = config
        self._raillines_data = None

    def _load_raillines_data(self):
        """Load railroad lines data from the configured GeoJSON file."""
        if self._raillines_data is not None:
            return

        if not self.config:
            raise ValueError("Config is required for RailroadProvider")

        raillines_path = self.config.get("providers.railroads.raillines_path")
        if not raillines_path:
            raise ValueError("raillines_path not configured")

        path = Path(raillines_path)
        if not path.exists():
            raise FileNotFoundError(f"Railroad lines file not found: {raillines_path}")

        self._raillines_data = gpd.read_file(path)

        if self._raillines_data.crs is None:
            raise ValueError("Railroad lines data must have a defined CRS")

    def fetch_place_data(self, place: "Place"):
        """Fetch railroad data for the given place."""
        self._load_raillines_data()

        if not isinstance(self._raillines_data, gpd.GeoDataFrame):
            raise ValueError("Railroad lines data not loaded")

        # Note: place.coordinates is (lat, lng) but Point expects (lng, lat)
        place_point = Point(place.coordinates[1], place.coordinates[0])

        # Ensure both GeoDataFrames are in the same CRS
        rail_gdf = self._raillines_data.to_crs(epsg=3857)
        point_gdf = gpd.GeoDataFrame(geometry=[place_point], crs="EPSG:4326").to_crs(
            epsg=3857
        )

        # Find the nearest railroad line
        distances = rail_gdf.distance(point_gdf.geometry[0])
        nearest_idx = distances.idxmin()
        nearest_distance = distances.loc[nearest_idx]

        # For now, just indicate that railroad data is available
        place.attributes["railroad_data_loaded"] = True
        place.attributes["nearby_railroad_distance_m"] = nearest_distance
