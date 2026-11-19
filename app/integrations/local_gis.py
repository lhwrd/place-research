"""Local copies of public ArcGIS layers and rasters, built by scripts/build_gis.py.

Public map servers (FEMA, USGS, USFWS, FDEP, Florida GIO) are slow and have bad days. For
the area you search in, scripts/build_gis.py copies the layers and rasters the providers
query into GIS_DATA_DIR, and ArcGISClient answers from them instead of the server whenever
the copy covers the whole query. Anything outside the copied area, or a layer that isn't
copied, still goes to the server, so the copy can cover just your search area.

GIS_DATA_DIR holds:
- layers.sqlite: one table per vector layer (attributes exactly as the server returned
  them, geometry as WKB in WGS84) with an R-tree index, and a "sources" table naming the
  server layer each copies and the area it covers
- one GeoTIFF per raster (elevation, sinkhole favorability), also listed in "sources"
"""

import json
import logging
import math
import sqlite3
import threading
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import shapely
import shapely.prepared
from shapely.geometry import Point, box

from app.core.config import settings
from app.utils.distance_calculator import geometry_distance_m

logger = logging.getLogger(__name__)

LAYERS_FILE = "layers.sqlite"
GEOMETRY_COLUMN = "_geometry"
ID_COLUMN = "_oid"

# (minx, miny, maxx, maxy) in WGS84 degrees
BBox = Tuple[float, float, float, float]

SOURCES_SCHEMA = """
CREATE TABLE IF NOT EXISTS sources (
    name          TEXT PRIMARY KEY,  -- table (layer) or file name (raster)
    kind          TEXT NOT NULL,     -- 'layer' or 'raster'
    base_url      TEXT NOT NULL,     -- the server's services root, as ArcGISClient has it
    path          TEXT NOT NULL,     -- the layer or image service path the providers query
    fields        TEXT,              -- JSON list of the attribute fields stored (layers)
    minx REAL NOT NULL, miny REAL NOT NULL, maxx REAL NOT NULL, maxy REAL NOT NULL,
    feature_count INTEGER,
    built_at      TEXT NOT NULL,
    -- WKB polygon of the area actually covered, when that isn't the whole bbox (e.g. the
    -- counties whose parcel files were imported); NULL: the bbox
    coverage      BLOB
)
"""
# Added after the first builds; build_gis adds it to older files
SOURCES_ADDED_COLUMNS = [("coverage", "BLOB")]


class LocalDataError(Exception):
    """A local copy couldn't answer (a field or filter it doesn't have, a broken file)."""


@dataclass(frozen=True)
class Source:
    name: str
    kind: str
    base_url: str
    path: str
    fields: Tuple[str, ...]
    bbox: BBox
    # The covered area (a prepared geometry) when it's less than the bbox
    coverage: Optional[Any] = None

    def covers(self, area: BBox) -> bool:
        minx, miny, maxx, maxy = self.bbox
        inside = area[0] >= minx and area[1] >= miny and area[2] <= maxx and area[3] <= maxy
        return inside and (self.coverage is None or self.coverage.covers(box(*area)))


def source_key(base_url: str, path: str) -> Tuple[str, str]:
    return base_url.rstrip("/"), path.strip("/")


def area_around(latitude: float, longitude: float, distance_m: float) -> BBox:
    """The square of +-distance_m around a point, in degrees."""
    dlat = distance_m / 110_950.0
    dlon = distance_m / (111_320.0 * math.cos(math.radians(latitude)))
    return (longitude - dlon, latitude - dlat, longitude + dlon, latitude + dlat)


class LocalGIS:
    """The copies in one GIS_DATA_DIR. Thread-safe; queries run in worker threads."""

    def __init__(self, directory: Path):
        self.directory = Path(directory)
        self.layers_path = self.directory / LAYERS_FILE
        self._lock = threading.Lock()
        self._sources: Dict[Tuple[str, str], Source] = {}
        self._loaded_mtime: Optional[float] = None

    def source(self, base_url: str, path: str) -> Optional[Source]:
        """The local copy of a server layer or raster, or None."""
        self._reload_if_changed()
        return self._sources.get(source_key(base_url, path))

    def _reload_if_changed(self) -> None:
        """Re-read "sources" when the file changes, so a rebuild needs no restart."""
        try:
            mtime = self.layers_path.stat().st_mtime
        except OSError:
            mtime = None
        if mtime == self._loaded_mtime:
            return
        with self._lock:
            if mtime == self._loaded_mtime:
                return
            sources: Dict[Tuple[str, str], Source] = {}
            if mtime is not None:
                try:
                    with closing(self._connect()) as conn:
                        for row in conn.execute("SELECT * FROM sources"):
                            source = Source(
                                name=row["name"],
                                kind=row["kind"],
                                base_url=row["base_url"],
                                path=row["path"],
                                fields=tuple(json.loads(row["fields"] or "[]")),
                                bbox=(row["minx"], row["miny"], row["maxx"], row["maxy"]),
                                coverage=(
                                    shapely.prepared.prep(shapely.from_wkb(row["coverage"]))
                                    if "coverage" in row.keys() and row["coverage"]
                                    else None
                                ),
                            )
                            sources[source_key(source.base_url, source.path)] = source
                except sqlite3.Error as e:
                    logger.warning(
                        "Could not read local GIS sources in %s: %s", self.layers_path, e
                    )
            if sources:
                logger.info("Local GIS data: %s", sorted(s.name for s in sources.values()))
            self._sources = sources
            self._loaded_mtime = mtime

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(f"file:{self.layers_path}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        return conn

    # Vector layers

    def query_near(
        self,
        source: Source,
        latitude: float,
        longitude: float,
        distance_m: float,
        out_fields: Sequence[str],
        geometry: bool,
        where: Optional[str],
    ) -> List[Dict[str, Any]]:
        """Like ArcGISClient.query_near, from the local copy."""
        area = area_around(latitude, longitude, max(distance_m, 0.01))
        found = []
        point = Point(longitude, latitude)
        for attributes, shape in self._query(source, area, out_fields, where):
            if distance_m:
                if geometry_distance_m(latitude, longitude, shape) > distance_m:
                    continue
            elif not shape.intersects(point):
                continue
            found.append({**attributes, "geometry": shape} if geometry else attributes)
        return found

    def query_box(
        self,
        source: Source,
        area: BBox,
        out_fields: Sequence[str],
        where: Optional[str],
    ) -> List[Dict[str, Any]]:
        """Like ArcGISClient.query_box (always with geometries), from the local copy."""
        square = box(*area)
        return [
            {**attributes, "geometry": shape}
            for attributes, shape in self._query(source, area, out_fields, where)
            if shape.intersects(square)
        ]

    def _query(
        self,
        source: Source,
        area: BBox,
        out_fields: Sequence[str],
        where: Optional[str],
    ) -> List[Tuple[Dict[str, Any], Any]]:
        fields = list(source.fields) if tuple(out_fields) == ("*",) else list(out_fields)
        missing = set(fields) - set(source.fields)
        if missing:
            raise LocalDataError(f"{source.name} has no fields {sorted(missing)}")
        columns = ", ".join(f't."{f}"' for f in fields)
        sql = (
            f'SELECT {columns}{", " if columns else ""}t."{GEOMETRY_COLUMN}" '
            f'FROM "{source.name}" t JOIN "{source.name}_rtree" r ON t."{ID_COLUMN}" = r.id '
            "WHERE r.minx <= ? AND r.maxx >= ? AND r.miny <= ? AND r.maxy >= ?"
        )
        if where:
            # ArcGIS's standardized SQL (=, IN, AND, OR, quotes) is also SQLite's
            sql += f" AND ({where})"
        # The servers answer in object ID order; some providers keep that order
        sql += f' ORDER BY t."{ID_COLUMN}"'
        try:
            with closing(self._connect()) as conn:
                rows = conn.execute(sql, (area[2], area[0], area[3], area[1])).fetchall()
        except sqlite3.Error as e:
            raise LocalDataError(f"{source.name}: {e}") from e
        return [
            ({f: row[f] for f in fields}, shapely.from_wkb(row[GEOMETRY_COLUMN])) for row in rows
        ]

    # Rasters

    def sample(
        self, source: Source, points: Sequence[Tuple[float, float]]
    ) -> List[Optional[float]]:
        """Raster values at (latitude, longitude) points, None where it has no data."""
        import numpy as np
        import rasterio  # imported late: only needed when a raster is copied

        try:
            with rasterio.open(self.directory / source.name) as raster:
                scale = raster.scales[0] if raster.scales else 1.0
                offset = raster.offsets[0] if raster.offsets else 0.0
                coords = [(lon, lat) for lat, lon in points]
                values: List[Optional[float]] = []
                for sample in raster.sample(coords, indexes=1, masked=True):
                    if np.ma.getmaskarray(sample)[0]:
                        values.append(None)
                    else:
                        values.append(float(sample[0]) * scale + offset)
                return values
        except rasterio.RasterioIOError as e:
            raise LocalDataError(f"{source.name}: {e}") from e


_default: Optional[LocalGIS] = None
_default_dir: Optional[Path] = None
_default_lock = threading.Lock()


def default_local_gis() -> Optional[LocalGIS]:
    """The LocalGIS for GIS_DATA_DIR, or None if it isn't set."""
    global _default, _default_dir  # pylint: disable=global-statement
    directory = settings.gis_data_dir
    if directory is None:
        return None
    with _default_lock:
        if _default is None or _default_dir != directory:
            _default, _default_dir = LocalGIS(directory), directory
        return _default
