"""Distance to the nearest active railroad, from a local file.

Reads rail lines (GeoParquet or any OGR-readable file, e.g. GeoJSON) from RAILLINES_PATH.
With the North American Rail Network's NET_CODE column, abandoned, out-of-service and
ferry lines are dropped (a rail trail makes no noise), and main lines are told apart from
spurs and yards. The lines are projected once at load time; each lookup is a
spatial-index nearest query, so it takes about a millisecond.
"""

import logging
import math
import threading
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

logger = logging.getLogger(__name__)

# NET_CODE values: M = main line, O = other active track (spurs, sidings, yards),
# A = abandoned, X = out of service, F = ferry
ACTIVE_NET_CODES = ("M", "O")
MAINLINE_NET_CODE = "M"


class RailroadProvider(BaseEnrichmentProvider):
    """Nearest railroad distance, with the file loaded once per process."""

    # Active rail lines in EPSG:3857 with a spatial index, shared by every instance
    _shared_raillines: Optional["RailLines"] = None
    _data_lock = threading.Lock()

    def __init__(self, raillines_data: Optional[gpd.GeoDataFrame] = None):
        """
        Args:
            raillines_data: Pre-loaded rail lines (tests). If None, RAILLINES_PATH is loaded
                once and shared across instances.

        Raises:
            ValueError: If RAILLINES_PATH isn't set or the data has no CRS
            FileNotFoundError: If RAILLINES_PATH doesn't exist
        """
        self.logger = logger
        if raillines_data is not None:
            self._raillines = RailLines(raillines_data)
            return

        cls = self.__class__
        if cls._shared_raillines is None:
            with cls._data_lock:
                if cls._shared_raillines is None:
                    cls._shared_raillines = RailLines(self._load(settings.raillines_path))
                    self.logger.info(
                        "Loaded %d active railroad lines", len(cls._shared_raillines.all)
                    )
        self._raillines = cls._shared_raillines

    @property
    def metadata(self) -> ProviderMetadata:
        return ProviderMetadata(
            name="railroad_provider",
            category=ProviderCategory.ENVIRONMENTAL,
            enabled=True,
            description="Distance to the nearest railroad line (local GeoParquet/GeoJSON).",
            version="2.0.0",
            requires_api_key=False,
            cost_per_call=0.0,
        )

    def _load(self, path: Optional[Path]) -> gpd.GeoDataFrame:
        if not path:
            raise ValueError("RAILLINES_PATH not configured")
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"Railroad lines file not found: {path}")
        self.logger.info("Loading railroad lines from %s", path)
        return self._load_geodataframe(path)

    def _load_geodataframe(self, path: Path) -> gpd.GeoDataFrame:
        """GeoParquet for .parquet/.geoparquet, otherwise anything OGR reads."""
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
        distance = self._calculate_nearest_distance(latitude, longitude)
        if distance is None:
            return ProviderResult(provider_name=self.metadata.name, data={}, success=True)
        data: Dict[str, Any] = {"railroad_distance_m": distance}
        if self._raillines.mainline is not None:
            data["mainline_distance_m"] = _nearest(self._raillines.mainline, latitude, longitude)
        return ProviderResult(
            provider_name=self.metadata.name, data=data, success=True, api_calls_made=0
        )

    def _calculate_nearest_distance(self, latitude: float, longitude: float) -> Optional[int]:
        """Meters to the nearest active rail line, or None if there are no lines."""
        return _nearest(self._raillines.all, latitude, longitude)

    async def validate_config(self) -> bool:
        return not self._raillines.all.empty


class RailLines:
    """Active lines (and main lines, when the data says which) projected and indexed."""

    def __init__(self, raillines: gpd.GeoDataFrame):
        if raillines.crs is None:
            raise ValueError("Railroad lines data must have a CRS")
        codes = raillines["NET_CODE"] if "NET_CODE" in raillines else None
        if codes is not None:
            raillines = raillines[codes.isin(ACTIVE_NET_CODES)]
        self.all = _indexed(raillines)
        self.mainline = (
            _indexed(raillines[raillines["NET_CODE"] == MAINLINE_NET_CODE])
            if codes is not None
            else None
        )


def _indexed(lines: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Geometry only, projected to EPSG:3857 once, with the spatial index built now."""
    projected = gpd.GeoDataFrame(geometry=lines.geometry.to_crs(epsg=3857)).reset_index(drop=True)
    _ = projected.sindex
    return projected


def _nearest(lines: gpd.GeoDataFrame, latitude: float, longitude: float) -> Optional[int]:
    if lines.empty:
        return None
    point = gpd.GeoSeries([Point(longitude, latitude)], crs="EPSG:4326").to_crs(epsg=3857)[0]
    _, (mercator_distance,) = lines.sindex.nearest(point, return_distance=True, return_all=False)
    # Web Mercator stretches distances by 1/cos(latitude); undo that locally
    return int(round(float(mercator_distance) * math.cos(math.radians(latitude))))
