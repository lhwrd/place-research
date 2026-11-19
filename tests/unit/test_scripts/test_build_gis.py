"""Tests for scripts/build_gis.py's layer harvest, against a fake ArcGIS server."""

import importlib.util
import json
import sqlite3
from pathlib import Path
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from app.integrations.local_gis import LAYERS_FILE, SOURCES_SCHEMA, LocalGIS

SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "build_gis.py"
spec = importlib.util.spec_from_file_location("build_gis", SCRIPT)
build_gis = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build_gis)

BASE = "https://gis.example/arcgis/rest/services"
BBOX = (-81.0, 28.0, -80.0, 29.0)
# Five points, two in the same corner so that cell has to split twice
POINTS = {
    1: (-80.9, 28.1),
    2: (-80.89, 28.11),
    3: (-80.2, 28.8),
    4: (-80.5, 28.5),
    5: (-80.1, 28.1),
}
LAYER = build_gis.LayerSpec("sites", BASE, "Svc/MapServer/0", ("NAME", "YEAR"), cell_deg=1.0)


@pytest.fixture(autouse=True)
def no_backoff_sleep():
    with patch("app.integrations.base_client.asyncio.sleep", new_callable=AsyncMock):
        yield


def server(fail_after=None):
    calls = {"queries": 0}

    def handle(request):
        if not request.url.path.endswith("/query"):
            return httpx.Response(200, json={"maxRecordCount": 2, "objectIdField": "OBJECTID"})
        calls["queries"] += 1
        if fail_after is not None and calls["queries"] > fail_after:
            return httpx.Response(400, json={"error": {"message": "down"}})
        params = request.url.params
        west, south, east, north = map(float, params["geometry"].split(","))
        inside = [
            oid
            for oid, (x, y) in sorted(POINTS.items())
            if west <= x <= east and south <= y <= north
        ]
        offset, count = int(params["resultOffset"]), int(params["resultRecordCount"])
        page = inside[offset : offset + count]
        return httpx.Response(
            200,
            json={
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "id": oid,
                        "geometry": {"type": "Point", "coordinates": list(POINTS[oid])},
                        "properties": {"OBJECTID": oid, "NAME": f"site {oid}", "YEAR": None},
                    }
                    for oid in page
                ],
            },
        )

    return handle, calls


async def harvest(directory, handle, fresh=False):
    conn = sqlite3.connect(directory / LAYERS_FILE)
    conn.execute(SOURCES_SCHEMA)
    try:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
            await build_gis.build_layer(client, conn, LAYER, BBOX, fresh)
    finally:
        conn.close()


@pytest.mark.asyncio
async def test_splits_full_cells_and_stores_every_feature(tmp_path):
    handle, _ = server()

    await harvest(tmp_path, handle)

    conn = sqlite3.connect(tmp_path / LAYERS_FILE)
    rows = conn.execute("SELECT _oid, NAME, YEAR FROM sites ORDER BY _oid").fetchall()
    assert rows == [(oid, f"site {oid}", None) for oid in POINTS]
    assert conn.execute("SELECT count(*) FROM sites_rtree").fetchone() == (5,)
    source = conn.execute("SELECT path, fields, minx, maxy, feature_count FROM sources").fetchone()
    assert source == ("Svc/MapServer/0", json.dumps(["NAME", "YEAR"]), -81.0, 29.0, 5)
    # Staging tables are gone
    names = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    assert not any("staging" in n for n in names)
    conn.close()

    # And the app can read it
    gis = LocalGIS(tmp_path)
    assert gis.source(BASE, "Svc/MapServer/0").covers((-80.95, 28.05, -80.85, 28.15))


@pytest.mark.asyncio
async def test_resumes_after_a_failure(tmp_path):
    failing, _ = server(fail_after=4)
    with pytest.raises(httpx.HTTPStatusError):
        await harvest(tmp_path, failing)
    conn = sqlite3.connect(tmp_path / LAYERS_FILE)
    done = conn.execute("SELECT count(*) FROM sites__staging_done").fetchone()[0]
    conn.close()
    assert done > 0

    working, calls = server()
    await harvest(tmp_path, working)

    conn = sqlite3.connect(tmp_path / LAYERS_FILE)
    assert conn.execute("SELECT count(*) FROM sites").fetchone() == (5,)
    conn.close()
    # Resuming skipped the cells finished before the failure
    full, full_calls = server()
    other = tmp_path / "fresh"
    other.mkdir()
    await harvest(other, full)
    assert calls["queries"] < full_calls["queries"]


@pytest.mark.asyncio
async def test_a_failed_rebuild_keeps_the_previous_copy(tmp_path):
    handle, _ = server()
    await harvest(tmp_path, handle)

    failing, _ = server(fail_after=1)
    with pytest.raises(httpx.HTTPStatusError):
        await harvest(tmp_path, failing, fresh=True)

    conn = sqlite3.connect(tmp_path / LAYERS_FILE)
    assert conn.execute("SELECT count(*) FROM sites").fetchone() == (5,)
    conn.close()


@pytest.mark.asyncio
async def test_splits_cells_the_server_cant_answer(tmp_path):
    handle, _ = server()

    def overloaded(request):
        if request.url.path.endswith("/query"):
            west, _, east, _ = map(float, request.url.params["geometry"].split(","))
            if east - west > 0.5:
                # How ArcGIS Online reports a query that timed out
                return httpx.Response(200, json={"error": {"message": "Unable to perform query"}})
        return handle(request)

    await harvest(tmp_path, overloaded)

    conn = sqlite3.connect(tmp_path / LAYERS_FILE)
    assert conn.execute("SELECT count(*) FROM sites").fetchone() == (5,)
    conn.close()


# Importing the Department of Revenue's county parcel files


def test_server_value_matches_the_layers_json():
    assert build_gis.server_value(2026.0, "esriFieldTypeDouble") == 2026
    assert isinstance(build_gis.server_value(2026.0, "esriFieldTypeDouble"), int)
    assert build_gis.server_value(0.23, "esriFieldTypeDouble") == 0.23
    assert build_gis.server_value(float("nan"), "esriFieldTypeDouble") is None
    assert build_gis.server_value("048", "esriFieldTypeString") == "048"
    assert build_gis.server_value(None, "esriFieldTypeString") is None


def test_county_of():
    assert build_gis.county_of(Path("volusia_2026Ppar.zip")) == "Volusia"
    assert build_gis.county_of(Path("stjohns_2026Ppar.zip")) == "St. Johns"
    assert build_gis.county_of(Path("indianriver_2026Ppar.zip")) == "Indian River"


def write_county_zip(directory: Path, name: str, parcels):
    """A DOR-style county file: a zipped shapefile in Florida East state plane feet."""
    import zipfile

    import geopandas as gpd

    frame = gpd.GeoDataFrame(
        [{k: v for k, v in p.items() if k != "geometry"} for p in parcels],
        geometry=[p["geometry"] for p in parcels],
        crs="EPSG:4326",
    ).to_crs("EPSG:2881")  # NAD83(HARN) / Florida East (ftUS)
    shp_dir = directory / name
    shp_dir.mkdir()
    frame.to_file(shp_dir / f"{name}.shp")
    archive = directory / f"{name}.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        for part in shp_dir.iterdir():
            zf.write(part, part.name)
    return archive


@pytest.mark.asyncio
async def test_imports_county_files_with_their_outline_as_coverage(tmp_path):
    from shapely.geometry import box

    from app.integrations.arcgis_api import ArcGISClient

    # Volusia is imported; Flagler (to the north) isn't
    volusia = box(-81.2, 28.8, -80.9, 29.1)
    flagler = box(-81.2, 29.1, -80.9, 29.4)
    archive = write_county_zip(
        tmp_path,
        "volusia_2026Ppar",
        [
            {
                "PARCEL_ID": "A1",
                "DOR_UC": "001",
                "JV": 250000.0,
                "geometry": box(-81.0, 29.0, -80.999, 29.001),
            },
            {
                "PARCEL_ID": "B2",
                "DOR_UC": "048",
                "JV": 1.5,
                "geometry": box(-81.1, 28.9, -81.099, 28.901),
            },
        ],
    )

    def handle(request):
        if request.url.host == "tigerweb.geo.census.gov":
            assert "BASENAME = 'Volusia'" in request.url.params["where"]
            return httpx.Response(
                200,
                json={
                    "features": [
                        {"type": "Feature", "geometry": volusia.__geo_interface__, "properties": {}}
                    ]
                },
            )
        return httpx.Response(
            200,
            json={
                "fields": [
                    {"name": "PARCEL_ID", "type": "esriFieldTypeString"},
                    {"name": "DOR_UC", "type": "esriFieldTypeString"},
                    {"name": "JV", "type": "esriFieldTypeDouble"},
                ]
            },
        )

    spec = build_gis.LayerSpec(
        "parcels", BASE, "Parcels/FeatureServer/0", ("PARCEL_ID", "DOR_UC", "JV")
    )
    conn = build_gis.open_layers(tmp_path)
    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
        await build_gis.import_parcels(client, conn, spec, [archive], (-82.0, 28.0, -80.0, 30.0))
    rows = conn.execute("SELECT PARCEL_ID, DOR_UC, JV FROM parcels ORDER BY PARCEL_ID").fetchall()
    conn.close()
    assert rows == [("A1", "001", 250000), ("B2", "048", 1.5)]

    def server(request):
        return httpx.Response(200, json={"type": "FeatureCollection", "features": []})

    api = ArcGISClient(BASE, service="test", local_gis=LocalGIS(tmp_path))
    api._client = httpx.AsyncClient(transport=httpx.MockTransport(server))
    # Inside Volusia: answered locally, from the reprojected outlines
    found = await api.query_box(
        "Parcels/FeatureServer/0", 29.0005, -80.9995, 20, ("PARCEL_ID", "JV")
    )
    assert [(p["PARCEL_ID"], p["JV"]) for p in found] == [("A1", 250000)]
    # In Flagler, inside the area but not imported: the server is asked
    source = LocalGIS(tmp_path).source(BASE, "Parcels/FeatureServer/0")
    assert not source.covers(flagler.centroid.buffer(0.001).bounds)
    assert await api.query_box("Parcels/FeatureServer/0", 29.3, -81.0, 20, ("PARCEL_ID",)) == []


@pytest.mark.asyncio
async def test_splits_cells_that_keep_failing_with_server_errors(tmp_path):
    handle, _ = server()

    def overloaded(request):
        if request.url.path.endswith("/query"):
            west, _, east, _ = map(float, request.url.params["geometry"].split(","))
            if east - west > 0.5:
                return httpx.Response(500)
        return handle(request)

    await harvest(tmp_path, overloaded)

    conn = sqlite3.connect(tmp_path / LAYERS_FILE)
    assert conn.execute("SELECT count(*) FROM sites").fetchone() == (5,)
    conn.close()
