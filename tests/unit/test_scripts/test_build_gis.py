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
