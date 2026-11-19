"""Copy the slow public map layers the providers query into GIS_DATA_DIR.

Flood zones (FEMA), parcels (Florida DOR, for the parcel and industrial-neighbor
providers), wetlands (USFWS), Florida DEP's sinkhole, cleanup-site, impaired-water and odor
layers, ground elevation (USGS 3DEP) and sinkhole favorability (FGS), for one area. With
GIS_DATA_DIR set, the app answers from these copies instead of the servers whenever a
lookup falls inside the area (see app/integrations/local_gis.py); anything outside it still
goes to the servers.

    uv run python scripts/build_gis.py data/gis                    # everything, default area
    uv run python scripts/build_gis.py data/gis --only parcels     # one source, e.g. yearly
    uv run python scripts/build_gis.py data/gis --only parcels --parcels-from ~/Downloads
    uv run python scripts/build_gis.py data/gis --bbox -82.6 27.6 -80.4 29.7
    uv run python scripts/build_gis.py --list

The default area is Central Florida (Ocala and Ormond Beach down to Kissimmee, Gulf-side
Marion County to the Brevard coast). Vector layers are pulled from the same ArcGIS layers
the providers query, so fields and values match exactly; each source is staged and swapped
in only when complete, so an interrupted rebuild keeps the previous copy; run the same
command again to resume it. Parcels are
republished every August, flood maps a few times a year; the rest change rarely.

Everything but parcels takes about 20 minutes. Paging through the statewide parcel layer
(about 2.7 million parcels in the default area) takes most of a day; importing the
Department of Revenue's county files with --parcels-from takes minutes, and only the
imported counties are answered locally. Disk use is roughly 2.5 GB, most of it parcels and
elevation.
"""

import argparse
import asyncio
import json
import math
import sqlite3
import sys
import time
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import httpx
import numpy as np
import rasterio
import shapely
from rasterio.transform import from_bounds
from rasterio.windows import Window
from shapely.geometry import box, shape
from shapely.geometry.base import BaseGeometry

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.integrations import fema_nfhl_api  # noqa: E402
from app.integrations.arcgis_api import (  # noqa: E402
    FDEP_OPEN_DATA,
    FL_GIO,
    USFWS_WETLANDS,
    USGS_ELEVATION,
)
from app.integrations.base_client import USER_AGENT, send_with_retry  # noqa: E402
from app.integrations.local_gis import (  # noqa: E402
    GEOMETRY_COLUMN,
    ID_COLUMN,
    LAYERS_FILE,
    SOURCES_ADDED_COLUMNS,
    SOURCES_SCHEMA,
    BBox,
)
from app.services.enrichment.providers import (  # noqa: E402
    contamination,
    elevation,
    impaired_waters,
    odor_sources,
    parcel,
    sinkholes,
    wetlands,
)

# West, south, east, north
CENTRAL_FLORIDA: BBox = (-82.6, 27.6, -80.4, 29.7)


@dataclass(frozen=True)
class LayerSpec:
    name: str
    base_url: str
    path: str
    # Attribute fields to keep; None keeps them all (small layers, whose where clauses
    # filter on fields the providers don't ask for)
    fields: Optional[Tuple[str, ...]]
    # Have the server simplify geometries to within this many degrees (1e-5 is ~1 m):
    # flood polygons are digitized far finer than a geocoded point is accurate
    max_offset_deg: float = 0.0
    # Starting cell size; cells holding more than a page are split in four
    cell_deg: float = 0.25
    concurrency: int = 4
    # Features per query (None: the layer's maxRecordCount)
    page_size: Optional[int] = None


@dataclass(frozen=True)
class RasterSpec:
    name: str  # file name in the output directory
    base_url: str
    path: str


LAYERS = [
    LayerSpec(
        "flood_zones",
        fema_nfhl_api.FEMA_NFHL,
        fema_nfhl_api.FLOOD_HAZARD_ZONES_LAYER,
        fema_nfhl_api.FIELDS,
        max_offset_deg=1e-5,
        cell_deg=0.05,
    ),
    LayerSpec(
        "parcels",
        FL_GIO,
        parcel.PARCELS_LAYER,
        parcel.FIELDS,
        cell_deg=0.05,
        concurrency=8,
        # Full 2000-parcel pages with geometry often time out on the server
        page_size=1000,
    ),
    LayerSpec(
        "wetlands",
        USFWS_WETLANDS,
        wetlands.WETLANDS_LAYER,
        ("WETLAND_TYPE", "ACRES"),
        cell_deg=0.05,
        concurrency=6,
    ),
    LayerSpec("sinkhole_incidents", FDEP_OPEN_DATA, sinkholes.INCIDENTS_LAYER, None),
    LayerSpec("cleanup_sites", FDEP_OPEN_DATA, contamination.CLEANUP_SITES_LAYER, None),
    LayerSpec("impaired_waters", FDEP_OPEN_DATA, impaired_waters.IMPAIRED_WATERS_LAYER, None),
    LayerSpec("wastewater_facilities", FDEP_OPEN_DATA, odor_sources.WASTEWATER_LAYER, None),
    LayerSpec("solid_waste_facilities", FDEP_OPEN_DATA, odor_sources.SOLID_WASTE_LAYER, None),
    LayerSpec("air_permits", FDEP_OPEN_DATA, odor_sources.AIR_LAYER, None),
]
RASTERS = [
    RasterSpec("elevation.tif", USGS_ELEVATION, elevation.DEM_SERVICE),
    RasterSpec("sinkhole_favorability.tif", FDEP_OPEN_DATA, sinkholes.FAVORABILITY_SERVICE),
]
SOURCES = [s.name for s in LAYERS] + [s.name.removesuffix(".tif") for s in RASTERS]

# Cells this small that still hold more than a page are paged through instead of split
MIN_CELL_DEG = 0.002


def log(message: str) -> None:
    print(f"{time.strftime('%H:%M:%S')} {message}", flush=True)


async def get_json(
    client: httpx.AsyncClient, url: str, params: Dict[str, Any], attempts: int = 4
) -> Dict[str, Any]:
    """
    GET a JSON answer, retrying busy statuses and ArcGIS error bodies.

    Overloaded ArcGIS Online layers answer HTTP 200 with {"error": "Unable to perform
    query"} rather than a 504, so those are retried too.
    """
    for attempt in range(1, attempts + 1):
        response = await send_with_retry(
            lambda: client.get(url, params=params), service=url, max_attempts=6, backoff_seconds=3
        )
        response.raise_for_status()
        data = response.json()
        if not (isinstance(data, dict) and "error" in data):
            return data
        error = data["error"]
        message = f"{url}: {error.get('message')} {error.get('details')}"
        if attempt == attempts:
            raise ValueError(message)
        log(f"  query failed ({message}); retrying in {3 * attempt}s")
        await asyncio.sleep(3 * attempt)
    raise RuntimeError("unreachable")


# Vector layers


async def build_layer(
    client: httpx.AsyncClient,
    conn: sqlite3.Connection,
    spec: LayerSpec,
    bbox: BBox,
    fresh: bool = False,
) -> None:
    """
    Harvest one layer into a staging table, then swap it in.

    Resumable: finished cells are recorded with the staging table, so running again after
    a failure picks up where it stopped (unless fresh, or the area or fields changed).
    """
    url = f"{spec.base_url.rstrip('/')}/{spec.path}"
    info = await get_json(client, url, {"f": "json"})
    page = min(int(info.get("maxRecordCount") or 1000), spec.page_size or 10**9)
    oid_field = info.get("objectIdField") or next(
        (f["name"] for f in info.get("fields") or [] if f.get("type") == "esriFieldTypeOID"),
        None,
    )
    if not oid_field:
        raise ValueError(f"{url} has no object ID field")
    fields = list(spec.fields) if spec.fields else [
        f["name"]
        for f in info.get("fields") or []
        if f.get("type") not in ("esriFieldTypeGeometry", "esriFieldTypeBlob", "esriFieldTypeRaster")
    ]  # fmt: skip

    staging = f"{spec.name}__staging"
    columns = ", ".join(f'"{f}"' for f in fields)
    # What the staged rows were harvested for; resuming needs the same
    job = json.dumps({"bbox": list(bbox), "fields": fields, "offset": spec.max_offset_deg})
    previous = None
    if not fresh:
        try:
            previous = conn.execute(f'SELECT job FROM "{staging}_job"').fetchone()
        except sqlite3.OperationalError:
            pass
    if previous and previous[0] == job:
        done_cells = {row[0] for row in conn.execute(f'SELECT cell FROM "{staging}_done"')}
        log(f"  {spec.name}: resuming, {len(done_cells):,} cells already done")
    else:
        for suffix in ("", "_rtree", "_done", "_job"):
            conn.execute(f'DROP TABLE IF EXISTS "{staging}{suffix}"')
        conn.execute(
            f'CREATE TABLE "{staging}" ("{ID_COLUMN}" INTEGER PRIMARY KEY, {columns}, '
            f'"{GEOMETRY_COLUMN}" BLOB NOT NULL)'
        )
        conn.execute(
            f'CREATE VIRTUAL TABLE "{staging}_rtree" USING rtree(id, minx, maxx, miny, maxy)'
        )
        conn.execute(f'CREATE TABLE "{staging}_done" (cell TEXT PRIMARY KEY)')
        conn.execute(f'CREATE TABLE "{staging}_job" (job TEXT NOT NULL)')
        conn.execute(f'INSERT INTO "{staging}_job" VALUES (?)', (job,))
        conn.commit()
        done_cells = set()
    insert = (
        f'INSERT OR IGNORE INTO "{staging}" ("{ID_COLUMN}", {columns}, "{GEOMETRY_COLUMN}") '
        f"VALUES ({', '.join('?' * (len(fields) + 2))})"
    )
    insert_box = f'INSERT INTO "{staging}_rtree" VALUES (?, ?, ?, ?, ?)'
    out_fields = ",".join(dict.fromkeys([oid_field, *fields]))

    stored = conn.execute(f'SELECT count(*) FROM "{staging}"').fetchone()[0]
    queries = 0

    def finished(cell: BBox) -> None:
        conn.execute(f'INSERT OR IGNORE INTO "{staging}_done" VALUES (?)', (cell_key(cell),))
        conn.commit()

    def store(features: List[Dict[str, Any]]) -> None:
        nonlocal stored
        for feature in features:
            props = feature.get("properties") or {}
            oid = feature.get("id", props.get(oid_field))
            geometry = feature.get("geometry")
            if oid is None or not geometry:
                continue
            geom = shape(geometry)
            if geom.is_empty:
                continue
            row = [int(oid), *(props.get(f) for f in fields), shapely.to_wkb(geom)]
            if conn.execute(insert, row).rowcount:
                minx, miny, maxx, maxy = geom.bounds
                conn.execute(insert_box, (int(oid), minx, maxx, miny, maxy))
                stored += 1

    async def fetch(cell: BBox, offset: int = 0) -> Tuple[List[Dict[str, Any]], bool]:
        nonlocal queries
        params: Dict[str, Any] = {
            "geometry": ",".join(str(round(v, 6)) for v in cell),
            "geometryType": "esriGeometryEnvelope",
            "inSR": 4326,
            "spatialRel": "esriSpatialRelIntersects",
            "outFields": out_fields,
            "returnGeometry": "true",
            "outSR": 4326,
            "geometryPrecision": 6,
            "orderByFields": oid_field,
            "resultOffset": offset,
            "resultRecordCount": page,
            "f": "geojson",
        }
        if spec.max_offset_deg:
            params["maxAllowableOffset"] = spec.max_offset_deg
        data = await get_json(client, f"{url}/query", params)
        queries += 1
        features = data.get("features") or []
        more = bool(
            data.get("exceededTransferLimit")
            or (data.get("properties") or {}).get("exceededTransferLimit")
            or len(features) >= page
        )
        return features, more

    queue: asyncio.Queue = asyncio.Queue()
    for cell in grid(bbox, spec.cell_deg):
        queue.put_nowait(cell)
    started = time.monotonic()
    last_report = started

    async def worker() -> None:
        nonlocal last_report
        while True:
            cell = await queue.get()
            try:
                if cell_key(cell) in done_cells:
                    continue
                try:
                    features, more = await fetch(cell)
                except (ValueError, httpx.HTTPStatusError) as e:
                    # A query the server keeps failing on (too heavy: a timeout, a 500);
                    # smaller ones usually work. Not for a bad request, and only a couple
                    # of levels down, so a server that's simply down fails the build
                    # instead of being sent ever smaller queries.
                    client_error = (
                        isinstance(e, httpx.HTTPStatusError) and e.response.status_code < 500
                    )
                    width = cell[2] - cell[0]
                    if client_error or width <= MIN_CELL_DEG or width <= spec.cell_deg / 4:
                        raise
                    log(f"  {spec.name}: splitting a cell the server can't answer")
                    for quarter in split(cell):
                        queue.put_nowait(quarter)
                    continue
                if more and cell[2] - cell[0] > MIN_CELL_DEG:
                    for quarter in split(cell):
                        queue.put_nowait(quarter)
                else:
                    store(features)
                    offset = len(features)
                    while more:
                        features, more = await fetch(cell, offset)
                        store(features)
                        offset += len(features)
                        more = more and bool(features)
                    finished(cell)
                if time.monotonic() - last_report > 30:
                    last_report = time.monotonic()
                    log(
                        f"  {spec.name}: {stored:,} features, {queries:,} queries, "
                        f"{queue.qsize():,} cells left"
                    )
            finally:
                queue.task_done()

    workers = [asyncio.create_task(worker()) for _ in range(spec.concurrency)]
    join = asyncio.create_task(queue.join())
    try:
        # A worker that fails (the server gave up even after retries) fails the build
        done, _ = await asyncio.wait([join, *workers], return_when=asyncio.FIRST_COMPLETED)
        for task in done:
            if task is not join:
                task.result()
    finally:
        for task in [join, *workers]:
            task.cancel()
        await asyncio.gather(join, *workers, return_exceptions=True)

    # Swap the finished copy in
    conn.execute(f'DROP TABLE IF EXISTS "{spec.name}"')
    conn.execute(f'DROP TABLE IF EXISTS "{spec.name}_rtree"')
    conn.execute(f'ALTER TABLE "{staging}" RENAME TO "{spec.name}"')
    conn.execute(f'ALTER TABLE "{staging}_rtree" RENAME TO "{spec.name}_rtree"')
    conn.execute(f'DROP TABLE "{staging}_done"')
    conn.execute(f'DROP TABLE "{staging}_job"')
    record_source(conn, spec.name, "layer", spec.base_url, spec.path, fields, bbox, stored)
    conn.commit()
    log(
        f"{spec.name}: {stored:,} features in {queries:,} queries "
        f"({time.monotonic() - started:.0f}s)"
    )


def cell_key(cell: BBox) -> str:
    return ",".join(f"{v:.6f}" for v in cell)


def grid(bbox: BBox, size: float) -> List[BBox]:
    west, south, east, north = bbox
    cells = []
    for i in range(math.ceil((east - west) / size)):
        for j in range(math.ceil((north - south) / size)):
            x, y = west + i * size, south + j * size
            cells.append((x, y, min(x + size, east), min(y + size, north)))
    return cells


def split(cell: BBox) -> List[BBox]:
    west, south, east, north = cell
    mx, my = (west + east) / 2, (south + north) / 2
    return [
        (west, south, mx, my),
        (mx, south, east, my),
        (west, my, mx, north),
        (mx, my, east, north),
    ]


def record_source(
    conn: sqlite3.Connection,
    name: str,
    kind: str,
    base_url: str,
    path: str,
    fields: Optional[Sequence[str]],
    bbox: BBox,
    count: Optional[int],
    coverage: Optional[BaseGeometry] = None,
) -> None:
    conn.execute(
        "INSERT OR REPLACE INTO sources (name, kind, base_url, path, fields, minx, miny, maxx,"
        " maxy, feature_count, built_at, coverage) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            name,
            kind,
            base_url.rstrip("/"),
            path.strip("/"),
            json.dumps(list(fields)) if fields is not None else None,
            *bbox,
            count,
            datetime.now(timezone.utc).isoformat(timespec="seconds"),
            shapely.to_wkb(coverage) if coverage is not None else None,
        ),
    )


def open_layers(directory: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(directory / LAYERS_FILE)
    conn.execute(SOURCES_SCHEMA)
    existing = {row[1] for row in conn.execute("PRAGMA table_info(sources)")}
    for column, definition in SOURCES_ADDED_COLUMNS:
        if column not in existing:
            conn.execute(f"ALTER TABLE sources ADD COLUMN {column} {definition}")
    conn.commit()
    return conn


# Rasters

# USGS 1/3 arc-second (~10 m) seamless DEM, as 1x1 degree cloud-optimized GeoTIFFs named
# for their northwest corner. The same data the 3DEP image service serves at that size.
DEM_TILE = (
    "https://prd-tnm.s3.amazonaws.com/StagedProducts/Elevation/13/TIFF/current/"
    "{tile}/USGS_13_{tile}.tif"
)
DEM_NODATA = -32768  # stored as int16 centimeters
DEM_SCALE = 0.01


def build_elevation(directory: Path, bbox: BBox) -> Tuple[BBox, str]:
    """Mosaic the DEM tiles over bbox into one int16 (centimeter) GeoTIFF."""
    west, south, east, north = bbox
    tiles = [
        f"n{lat:02d}w{-lon:03d}"
        for lat in range(math.floor(south) + 1, math.ceil(north) + 1)
        for lon in range(math.floor(west), math.ceil(east))
    ]
    env = rasterio.Env(GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR", GDAL_HTTP_MAX_RETRY=5)
    with env:
        with rasterio.open(f"/vsicurl/{DEM_TILE.format(tile=tiles[0])}") as first:
            res = first.res[0]
            crs = first.crs
            # Snap the output to the tiles' pixel grid, so pixels copy across unresampled
            ox, oy = first.transform.c, first.transform.f
        left = ox + math.floor((west - ox) / res) * res
        top = oy - math.floor((oy - north) / res) * res
        width = math.ceil((east - left) / res)
        height = math.ceil((top - south) / res)
        transform = rasterio.Affine(res, 0, left, 0, -res, top)
        out_bbox = (left, top - height * res, left + width * res, top)

        output = directory / "elevation.tif"
        partial = directory / "elevation.tif.partial"
        profile = {
            "driver": "GTiff",
            "width": width,
            "height": height,
            "count": 1,
            "dtype": "int16",
            "nodata": DEM_NODATA,
            "crs": crs,
            "transform": transform,
            "tiled": True,
            "blockxsize": 512,
            "blockysize": 512,
            "compress": "deflate",
            "predictor": 2,
            "BIGTIFF": "IF_SAFER",
        }
        with rasterio.open(partial, "w", **profile) as dst:
            dst.scales = (DEM_SCALE,)
            for i, tile in enumerate(tiles, 1):
                url = f"/vsicurl/{DEM_TILE.format(tile=tile)}"
                log(f"  elevation: tile {i}/{len(tiles)} {tile}")
                with rasterio.open(url) as src:
                    copy_tile(src, dst, transform, width, height)
        partial.replace(output)
    log(f"elevation: {width:,} x {height:,} px -> {output} ({output.stat().st_size / 1e6:.0f} MB)")
    return out_bbox, str(crs)


def copy_tile(src, dst, transform, width: int, height: int, rows: int = 1024) -> None:
    res = transform.a
    # Where the tile sits on the output grid
    col0 = round((src.transform.c - transform.c) / res)
    row0 = round((transform.f - src.transform.f) / res)
    c_start, c_end = max(0, col0), min(width, col0 + src.width)
    r_start, r_end = max(0, row0), min(height, row0 + src.height)
    if c_start >= c_end or r_start >= r_end:
        return
    for r in range(r_start, r_end, rows):
        n = min(rows, r_end - r)
        window = Window(c_start - col0, r - row0, c_end - c_start, n)
        meters = src.read(1, window=window, masked=True)
        centimeters = np.where(
            np.ma.getmaskarray(meters), DEM_NODATA, np.round(meters.filled(0) / DEM_SCALE)
        ).astype("int16")
        dst.write(centimeters, 1, window=Window(c_start, r, c_end - c_start, n))


# Sinkhole favorability: 100 m classes 1-14, exported once at about that resolution
FAVORABILITY_RES_DEG = 0.001
FAVORABILITY_NODATA = 255


async def build_favorability(client: httpx.AsyncClient, directory: Path, bbox: BBox) -> BBox:
    west, south, east, north = bbox
    width = math.ceil((east - west) / FAVORABILITY_RES_DEG)
    height = math.ceil((north - south) / FAVORABILITY_RES_DEG)
    east, north = west + width * FAVORABILITY_RES_DEG, south + height * FAVORABILITY_RES_DEG
    url = f"{FDEP_OPEN_DATA}/{sinkholes.FAVORABILITY_SERVICE}/exportImage"
    image = await get_json(
        client,
        url,
        {
            "bbox": f"{west},{south},{east},{north}",
            "bboxSR": 4326,
            "imageSR": 4326,
            "size": f"{width},{height}",
            "format": "tiff",
            "pixelType": "U8",
            "noData": FAVORABILITY_NODATA,
            "interpolation": "RSP_NearestNeighbor",
            "f": "json",
        },
    )
    response = await send_with_retry(
        lambda: client.get(image["href"]), service="FDEP favorability", max_attempts=6
    )
    response.raise_for_status()
    extent = image.get("extent") or {}
    out_bbox = (
        extent.get("xmin", west),
        extent.get("ymin", south),
        extent.get("xmax", east),
        extent.get("ymax", north),
    )
    with rasterio.MemoryFile(response.content) as memory, memory.open() as src:
        values = src.read(1)
    output = directory / "sinkhole_favorability.tif"
    with rasterio.open(
        output,
        "w",
        driver="GTiff",
        width=values.shape[1],
        height=values.shape[0],
        count=1,
        dtype="uint8",
        nodata=FAVORABILITY_NODATA,
        crs="EPSG:4326",
        transform=from_bounds(*out_bbox, values.shape[1], values.shape[0]),
        compress="deflate",
    ) as dst:
        dst.write(values, 1)
    classes = {int(v): int(n) for v, n in zip(*np.unique(values, return_counts=True))}
    log(f"sinkhole_favorability: {values.shape[1]} x {values.shape[0]} px, values {classes}")
    return out_bbox


# Parcels from the Department of Revenue's county files

# Map Data files on https://floridarevenue.com/property/Pages/DataPortal.aspx: parcel
# outlines joined with that year's tax roll (NAL), e.g. volusia_2026Ppar.zip. The fields
# are the statewide layer's (it's built from the same files), in each county's state
# plane projection.
DOR_PARCEL_GLOB = "*Ppar.zip"
TIGER_COUNTIES = (
    "https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/State_County/MapServer/1"
)
FLORIDA_FIPS = "12"
# File name prefix -> Census county name, where title-casing it isn't enough
COUNTY_NAMES = {
    "desoto": "DeSoto",
    "indianriver": "Indian River",
    "miamidade": "Miami-Dade",
    "palmbeach": "Palm Beach",
    "santarosa": "Santa Rosa",
    "stjohns": "St. Johns",
    "stlucie": "St. Lucie",
}
DOUBLE_TYPES = ("esriFieldTypeDouble", "esriFieldTypeSingle")
INTEGER_TYPES = ("esriFieldTypeInteger", "esriFieldTypeSmallInteger", "esriFieldTypeBigInteger")


def county_of(path: Path) -> str:
    """volusia_2026Ppar.zip -> Volusia"""
    prefix = path.name.split("_")[0].lower().replace(" ", "").replace(".", "")
    return COUNTY_NAMES.get(prefix, prefix.title())


async def county_outline(client: httpx.AsyncClient, county: str) -> BaseGeometry:
    """The county's Census boundary (including its water), in WGS84."""
    name = county.replace("'", "''")
    data = await get_json(
        client,
        f"{TIGER_COUNTIES}/query",
        {
            "where": f"STATE = '{FLORIDA_FIPS}' AND BASENAME = '{name}'",
            "outFields": "BASENAME",
            "returnGeometry": "true",
            "outSR": 4326,
            "f": "geojson",
        },
    )
    features = data.get("features") or []
    if len(features) != 1:
        raise ValueError(f"No Florida county named {county!r} in the Census boundaries")
    return shape(features[0]["geometry"])


def server_value(value: Any, field_type: Optional[str]) -> Any:
    """A shapefile value as the ArcGIS layer's JSON gives it (whole doubles as ints)."""
    if value is None:
        return None
    if field_type in DOUBLE_TYPES or field_type in INTEGER_TYPES:
        number = float(value)
        if math.isnan(number):
            return None
        return int(number) if number.is_integer() else number
    if field_type == "esriFieldTypeString":
        return str(value)
    return value


def read_county(path: Path, fields: Sequence[str]) -> Tuple[Dict[str, list], np.ndarray]:
    """A county file's field values (column lists) and its geometries in WGS84."""
    from pyogrio import read_arrow  # imported late: only the importer needs it
    from pyproj import Transformer

    shapefiles = [n for n in zipfile.ZipFile(path).namelist() if n.lower().endswith(".shp")]
    if len(shapefiles) != 1:
        raise ValueError(f"{path.name}: expected one shapefile, found {shapefiles}")
    meta, table = read_arrow(f"/vsizip/{path}/{shapefiles[0]}", columns=list(fields))
    missing = set(fields) - set(table.column_names)
    if missing:
        raise ValueError(f"{path.name} has no fields {sorted(missing)}")
    geometries = shapely.from_wkb(table[meta["geometry_name"] or "wkb_geometry"].to_numpy(False))
    to_wgs84 = Transformer.from_crs(meta["crs"], "EPSG:4326", always_xy=True)
    geometries = shapely.transform(
        geometries, lambda xy: np.column_stack(to_wgs84.transform(xy[:, 0], xy[:, 1]))
    )
    return {f: table[f].to_pylist() for f in fields}, geometries


async def import_parcels(
    client: httpx.AsyncClient,
    conn: sqlite3.Connection,
    spec: LayerSpec,
    files: List[Path],
    bbox: BBox,
) -> None:
    """Load parcels from DOR county files instead of paging through the statewide layer."""
    started = time.monotonic()
    url = f"{spec.base_url.rstrip('/')}/{spec.path}"
    info = await get_json(client, url, {"f": "json"})
    types = {f["name"]: f.get("type") for f in info.get("fields") or []}
    fields = list(spec.fields or ())

    staging = f"{spec.name}__staging"
    for suffix in ("", "_rtree", "_done", "_job"):
        conn.execute(f'DROP TABLE IF EXISTS "{staging}{suffix}"')
    columns = ", ".join(f'"{f}"' for f in fields)
    conn.execute(
        f'CREATE TABLE "{staging}" ("{ID_COLUMN}" INTEGER PRIMARY KEY, {columns}, '
        f'"{GEOMETRY_COLUMN}" BLOB NOT NULL)'
    )
    conn.execute(f'CREATE VIRTUAL TABLE "{staging}_rtree" USING rtree(id, minx, maxx, miny, maxy)')
    insert = f'INSERT INTO "{staging}" VALUES ({", ".join("?" * (len(fields) + 2))})'
    insert_box = f'INSERT INTO "{staging}_rtree" VALUES (?, ?, ?, ?, ?)'

    area = box(*bbox)
    outlines = []
    oid = 0
    for path in files:
        county = county_of(path)
        outline = await county_outline(client, county)
        if not outline.intersects(area):
            log(f"  parcels: skipping {path.name}: {county} County is outside the area")
            continue
        values, geometries = await asyncio.to_thread(read_county, path, fields)
        keep = shapely.intersects(geometries, area) & ~shapely.is_missing(geometries)
        rows, boxes = [], []
        for i in np.flatnonzero(keep):
            oid += 1
            geometry = geometries[i]
            rows.append(
                [
                    oid,
                    *(server_value(values[f][i], types.get(f)) for f in fields),
                    shapely.to_wkb(geometry),
                ]
            )
            minx, miny, maxx, maxy = geometry.bounds
            boxes.append((oid, minx, maxx, miny, maxy))
        conn.executemany(insert, rows)
        conn.executemany(insert_box, boxes)
        conn.commit()
        outlines.append(outline)
        log(f"  parcels: {county}: {len(rows):,} of {len(geometries):,} parcels in the area")

    if not outlines:
        raise ValueError("None of the parcel files is a county in the area")
    coverage = shapely.union_all(outlines).intersection(area)
    conn.execute(f'DROP TABLE IF EXISTS "{spec.name}"')
    conn.execute(f'DROP TABLE IF EXISTS "{spec.name}_rtree"')
    conn.execute(f'ALTER TABLE "{staging}" RENAME TO "{spec.name}"')
    conn.execute(f'ALTER TABLE "{staging}_rtree" RENAME TO "{spec.name}_rtree"')
    record_source(
        conn, spec.name, "layer", spec.base_url, spec.path, fields, coverage.bounds, oid, coverage
    )
    conn.commit()
    log(
        f"parcels: {oid:,} parcels from {len(outlines)} counties ({time.monotonic() - started:.0f}s)"
    )


# Main


async def build(
    directory: Path,
    bbox: BBox,
    only: Optional[List[str]],
    fresh: bool,
    parcel_files: Optional[List[Path]] = None,
) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    conn = open_layers(directory)
    wanted = set(only or SOURCES)
    async with httpx.AsyncClient(
        timeout=120, follow_redirects=True, headers={"User-Agent": USER_AGENT}
    ) as client:
        for raster in RASTERS:
            name = raster.name.removesuffix(".tif")
            if name not in wanted:
                continue
            log(f"{name}: building")
            if name == "elevation":
                out_bbox, _ = await asyncio.to_thread(build_elevation, directory, bbox)
            else:
                out_bbox = await build_favorability(client, directory, bbox)
            record_source(
                conn, raster.name, "raster", raster.base_url, raster.path, None, out_bbox, None
            )
            conn.commit()
        for spec in LAYERS:
            if spec.name not in wanted:
                continue
            if spec.name == "parcels" and parcel_files:
                log(f"parcels: importing {len(parcel_files)} county files")
                await import_parcels(client, conn, spec, parcel_files, bbox)
            else:
                log(f"{spec.name}: harvesting {spec.base_url}/{spec.path}")
                await build_layer(client, conn, spec, bbox, fresh)
    conn.execute("VACUUM")
    conn.close()
    size = (directory / LAYERS_FILE).stat().st_size / 1e6
    log(f"Done: {directory / LAYERS_FILE} is {size:,.0f} MB")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("output", type=Path, nargs="?", help="Directory for GIS_DATA_DIR")
    parser.add_argument(
        "--bbox",
        nargs=4,
        type=float,
        metavar=("WEST", "SOUTH", "EAST", "NORTH"),
        default=CENTRAL_FLORIDA,
        help="Area to copy, in degrees (default: Central Florida)",
    )
    parser.add_argument("--only", nargs="+", choices=SOURCES, help="Build just these sources")
    parser.add_argument(
        "--fresh", action="store_true", help="Start layers over instead of resuming"
    )
    parser.add_argument(
        "--parcels-from",
        type=Path,
        metavar="DIR",
        help=(
            "Import parcels from the Department of Revenue's county files in DIR "
            f"({DOR_PARCEL_GLOB}) instead of paging through the statewide layer"
        ),
    )
    parser.add_argument("--list", action="store_true", help="List the sources and exit")
    args = parser.parse_args()
    if args.list:
        for spec in LAYERS:
            print(f"{spec.name:24s} {spec.base_url}/{spec.path}")
        for raster in RASTERS:
            print(f"{raster.name.removesuffix('.tif'):24s} {raster.base_url}/{raster.path}")
        return 0
    if args.output is None:
        parser.error("output directory is required")
    west, south, east, north = args.bbox
    if not (west < east and south < north):
        parser.error("--bbox is WEST SOUTH EAST NORTH")
    parcel_files = None
    if args.parcels_from:
        parcel_files = sorted(args.parcels_from.glob(DOR_PARCEL_GLOB))
        empty = [f.name for f in parcel_files if f.stat().st_size == 0]
        if empty:
            parser.error(f"empty files (download again?): {', '.join(empty)}")
        if not parcel_files:
            parser.error(f"no {DOR_PARCEL_GLOB} files in {args.parcels_from}")
    asyncio.run(build(args.output, (west, south, east, north), args.only, args.fresh, parcel_files))
    return 0


if __name__ == "__main__":
    sys.exit(main())
