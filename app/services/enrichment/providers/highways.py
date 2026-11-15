"""Distance to the nearest major road and an estimate of road noise, from a local file.

Reads Census TIGER/Line primary and secondary roads (see scripts/build_highways.py) from
HIGHWAYS_PATH: GeoParquet or any OGR-readable file with MTFCC, FULLNAME and line
geometries. Lookups are in-memory spatial-index queries, so they take milliseconds and
don't depend on a public API.
"""

import logging
import math
import threading
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import geopandas as gpd
from shapely.geometry import Point

from app.core.config import settings
from app.services import noise
from app.services.enrichment.base_provider import (
    BaseEnrichmentProvider,
    ProviderCategory,
    ProviderMetadata,
    ProviderResult,
)

# TIGER MAF/TIGER feature class codes -> road class names (OSM-style, as stored before)
ROAD_CLASSES = {
    "S1100": "motorway",  # primary: interstates and other limited-access highways
    "S1200": "primary",  # secondary: US, state and county highways
}

# Past this, the property is almost certainly outside the states in the file
MAX_DISTANCE_M = 40 * 1609.344

logger = logging.getLogger(__name__)


class HighwayProvider(BaseEnrichmentProvider):
    """Nearest highway and road noise from TIGER roads, loaded once per process."""

    # Road class -> that class's roads in EPSG:3857, shared by every instance
    _shared_roads: Optional[Dict[str, gpd.GeoDataFrame]] = None
    _data_lock = threading.Lock()

    def __init__(self, roads: Optional[gpd.GeoDataFrame] = None):
        """
        Args:
            roads: Pre-loaded roads (tests). If None, HIGHWAYS_PATH is loaded once and
                shared across instances.

        Raises:
            ValueError: If HIGHWAYS_PATH isn't set or the data is unusable
            FileNotFoundError: If HIGHWAYS_PATH doesn't exist
        """
        self.logger = logger
        if roads is not None:
            self._roads = _split_by_class(roads)
            return

        cls = self.__class__
        if cls._shared_roads is None:
            with cls._data_lock:
                if cls._shared_roads is None:
                    cls._shared_roads = _split_by_class(self._load(settings.highways_path))
                    self.logger.info(
                        "Loaded highways: %s",
                        {k: len(v) for k, v in cls._shared_roads.items()},
                    )
        self._roads = cls._shared_roads

    @property
    def metadata(self) -> ProviderMetadata:
        return ProviderMetadata(
            name="highway_provider",
            category=ProviderCategory.ENVIRONMENTAL,
            enabled=True,
            description="Distance to the nearest major road and estimated road noise "
            "(local Census TIGER roads file).",
            version="2.0.0",
            requires_api_key=False,
            cost_per_call=0.0,
        )

    def _load(self, path: Optional[Path]) -> gpd.GeoDataFrame:
        if not path:
            raise ValueError("HIGHWAYS_PATH not configured")
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"Highways file not found: {path}")
        self.logger.info("Loading highways from %s", path)
        if path.suffix.lower() in (".parquet", ".geoparquet"):
            return gpd.read_parquet(path)
        return gpd.read_file(path)

    async def enrich(
        self,
        latitude: float,
        longitude: float,
        address: str,
        property_data: Optional[Dict[str, Any]] = None,
        user_preferences: Optional[Dict[str, Any]] = None,
    ) -> ProviderResult:
        nearest = self._nearest_by_class(latitude, longitude)
        if not nearest:
            self.logger.warning(
                "No highway within %.0f mi of (%.5f, %.5f); is its state in HIGHWAYS_PATH?",
                MAX_DISTANCE_M / 1609.344,
                latitude,
                longitude,
            )
            return ProviderResult(provider_name=self.metadata.name, data={}, success=True)

        road_class, (distance_m, name) = min(nearest.items(), key=lambda kv: kv[1][0])
        distances = {c: int(round(d)) for c, (d, _) in nearest.items()}
        noise_db = noise.loudest(noise.ROAD_LEVELS, distances)
        return ProviderResult(
            provider_name=self.metadata.name,
            data={
                "highway_distance_m": int(round(distance_m)),
                "nearest_highway_type": road_class,
                "nearest_highway_name": name,
                # Per road class, so the UI can recompute noise when the model changes
                "highway_distances_m": distances,
                "road_noise_level_db": noise_db,
                "road_noise_category": noise.category(noise_db),
            },
            success=True,
        )

    def _nearest_by_class(
        self, latitude: float, longitude: float
    ) -> Dict[str, Tuple[float, Optional[str]]]:
        """Road class -> (distance in meters, road name) of the nearest road of that class."""
        point = gpd.GeoSeries([Point(longitude, latitude)], crs="EPSG:4326").to_crs(epsg=3857)[0]
        # Web Mercator stretches distances by 1/cos(latitude); undo that locally
        scale = math.cos(math.radians(latitude))

        nearest: Dict[str, Tuple[float, Optional[str]]] = {}
        for road_class, roads in self._roads.items():
            if roads.empty:
                continue
            (_, (index,)), (mercator_distance,) = roads.sindex.nearest(
                point, return_distance=True, return_all=False
            )
            distance_m = float(mercator_distance) * scale
            if distance_m <= MAX_DISTANCE_M:
                name = roads.iloc[index]["FULLNAME"] if "FULLNAME" in roads else None
                nearest[road_class] = (distance_m, name if isinstance(name, str) else None)
        return nearest

    async def validate_config(self) -> bool:
        return bool(self._roads)


def _split_by_class(roads: gpd.GeoDataFrame) -> Dict[str, gpd.GeoDataFrame]:
    """Project to EPSG:3857 once and index each road class separately."""
    if roads.crs is None:
        raise ValueError("Highways data must have a CRS")
    if "MTFCC" not in roads:
        raise ValueError("Highways data must have an MTFCC column (TIGER roads)")
    roads = roads.to_crs(epsg=3857)
    by_class = {}
    for code, road_class in ROAD_CLASSES.items():
        subset = roads[roads["MTFCC"] == code].reset_index(drop=True)
        _ = subset.sindex  # build now, not on the first request
        by_class[road_class] = subset
    return by_class
