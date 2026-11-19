"""Tests for the local copies of ArcGIS layers and rasters, and ArcGISClient's use of them."""

import json
import sqlite3
from pathlib import Path

import httpx
import numpy as np
import pytest
import rasterio
import shapely
from rasterio.transform import from_bounds
from shapely.geometry import Point, box

from app.integrations.arcgis_api import ArcGISClient
from app.integrations.local_gis import (
    GEOMETRY_COLUMN,
    ID_COLUMN,
    LAYERS_FILE,
    SOURCES_SCHEMA,
    LocalGIS,
)

BASE = "https://gis.example/arcgis/rest/services"
LAYER = "Svc/MapServer/0"
COVERAGE = (-81.5, 28.4, -81.3, 28.6)
LAT, LON = 28.5, -81.4


def write_layer(directory: Path, name, path, fields, features, bbox=COVERAGE):
    """features: (oid, {field: value}, shapely geometry)"""
    conn = sqlite3.connect(directory / LAYERS_FILE)
    conn.execute(SOURCES_SCHEMA)
    columns = ", ".join(f'"{f}"' for f in fields)
    conn.execute(
        f'CREATE TABLE "{name}" ("{ID_COLUMN}" INTEGER PRIMARY KEY, {columns}, '
        f'"{GEOMETRY_COLUMN}" BLOB)'
    )
    conn.execute(f'CREATE VIRTUAL TABLE "{name}_rtree" USING rtree(id, minx, maxx, miny, maxy)')
    for oid, attributes, geometry in features:
        conn.execute(
            f'INSERT INTO "{name}" VALUES ({", ".join("?" * (len(fields) + 2))})',
            [oid, *(attributes.get(f) for f in fields), shapely.to_wkb(geometry)],
        )
        minx, miny, maxx, maxy = geometry.bounds
        conn.execute(
            f'INSERT INTO "{name}_rtree" VALUES (?, ?, ?, ?, ?)', (oid, minx, maxx, miny, maxy)
        )
    conn.execute(
        "INSERT OR REPLACE INTO sources (name, kind, base_url, path, fields, minx, miny, maxx, maxy, feature_count, built_at) VALUES (?, 'layer', ?, ?, ?, ?, ?, ?, ?, ?, '2026-11-18')",
        (name, BASE, path, json.dumps(fields), *bbox, len(features)),
    )
    conn.commit()
    conn.close()


def write_raster(directory: Path, name, path, values, bbox=COVERAGE, nodata=-32768, scale=1.0):
    height, width = values.shape
    with rasterio.open(
        directory / name,
        "w",
        driver="GTiff",
        width=width,
        height=height,
        count=1,
        dtype=values.dtype,
        nodata=nodata,
        crs="EPSG:4326",
        transform=from_bounds(*bbox, width, height),
    ) as dst:
        dst.scales = (scale,)
        dst.write(values, 1)
    conn = sqlite3.connect(directory / LAYERS_FILE)
    conn.execute(SOURCES_SCHEMA)
    conn.execute(
        "INSERT OR REPLACE INTO sources (name, kind, base_url, path, fields, minx, miny, maxx, maxy, feature_count, built_at) VALUES (?, 'raster', ?, ?, NULL, ?, ?, ?, ?, NULL, 'x')",
        (name, BASE, path, *bbox),
    )
    conn.commit()
    conn.close()


def meters_east(meters):
    return LON + meters / (111_320.0 * np.cos(np.radians(LAT)))


@pytest.fixture
def gis(tmp_path):
    write_layer(
        tmp_path,
        "sites",
        LAYER,
        ["NAME", "STATUS", "YEAR"],
        [
            (3, {"NAME": "near", "STATUS": "ACTIVE", "YEAR": 1987}, Point(meters_east(100), LAT)),
            (1, {"NAME": "closed", "STATUS": "CLOSED", "YEAR": None}, Point(meters_east(50), LAT)),
            (2, {"NAME": "far", "STATUS": "ACTIVE", "YEAR": 2001}, Point(meters_east(900), LAT)),
            (
                4,
                {"NAME": "zone", "STATUS": "ACTIVE", "YEAR": 2010},
                box(LON - 0.001, LAT - 0.001, LON + 0.001, LAT + 0.001),
            ),
        ],
    )
    return LocalGIS(tmp_path)


def client(gis, handler=None):
    """An ArcGISClient on the local copy; the server fails the test unless handled."""

    def server(request):
        if handler is None:
            raise AssertionError(f"unexpected server request {request.url}")
        return handler(request)

    api = ArcGISClient(BASE, service="test", local_gis=gis)
    api._client = httpx.AsyncClient(transport=httpx.MockTransport(server))
    return api


class TestLocalLayers:
    @pytest.mark.asyncio
    async def test_within_distance_in_object_id_order(self, gis):
        found = await client(gis).query_near(LAYER, LAT, LON, 500, ("NAME", "YEAR"))

        assert found == [
            {"NAME": "closed", "YEAR": None},
            {"NAME": "near", "YEAR": 1987},  # ints and NULLs come back as stored
            {"NAME": "zone", "YEAR": 2010},
        ]

    @pytest.mark.asyncio
    async def test_where_and_geometry(self, gis):
        found = await client(gis).query_near(
            LAYER, LAT, LON, 500, ("NAME",), geometry=True, where="STATUS IN ('ACTIVE')"
        )

        assert [f["NAME"] for f in found] == ["near", "zone"]
        assert found[0]["geometry"].equals(Point(meters_east(100), LAT))

    @pytest.mark.asyncio
    async def test_distance_zero_is_containing(self, gis):
        found = await client(gis).query_near(LAYER, LAT, LON, out_fields=("NAME",))

        assert found == [{"NAME": "zone"}]

    @pytest.mark.asyncio
    async def test_all_fields(self, gis):
        found = await client(gis).query_near(LAYER, LAT, LON)

        assert found == [{"NAME": "zone", "STATUS": "ACTIVE", "YEAR": 2010}]

    @pytest.mark.asyncio
    async def test_box(self, gis):
        found = await client(gis).query_box(LAYER, LAT, LON, 200, ("NAME",), where="YEAR > 1990")

        assert [f["NAME"] for f in found] == ["zone"]
        assert "geometry" in found[0]

    @pytest.mark.asyncio
    async def test_outside_the_copy_asks_the_server(self, gis):
        requests = []

        def server(request):
            requests.append(request)
            return httpx.Response(200, json={"features": [{"attributes": {"NAME": "remote"}}]})

        found = await client(gis, server).query_near(LAYER, 28.59, -81.4, 5000, ("NAME",))

        assert found == [{"NAME": "remote"}]
        assert len(requests) == 1

    @pytest.mark.asyncio
    async def test_uncopied_layer_asks_the_server(self, gis):
        def server(request):
            return httpx.Response(200, json={"features": []})

        assert await client(gis, server).query_near("Other/MapServer/1", LAT, LON, 100) == []

    @pytest.mark.asyncio
    async def test_missing_field_asks_the_server(self, gis):
        def server(request):
            return httpx.Response(200, json={"features": [{"attributes": {"OWNER": "x"}}]})

        found = await client(gis, server).query_near(LAYER, LAT, LON, 100, ("OWNER",))

        assert found == [{"OWNER": "x"}]

    @pytest.mark.asyncio
    async def test_bad_where_asks_the_server(self, gis):
        def server(request):
            return httpx.Response(200, json={"features": []})

        api = client(gis, server)
        assert await api.query_near(LAYER, LAT, LON, 100, where="NOPE = 1") == []

    @pytest.mark.asyncio
    async def test_rebuild_is_picked_up(self, gis, tmp_path):
        api = client(gis)
        assert len(await api.query_near(LAYER, LAT, LON, 500, ("NAME",))) == 3

        write_layer(
            tmp_path, "more", "Svc/MapServer/1", ["NAME"], [(1, {"NAME": "new"}, Point(LON, LAT))]
        )
        # A different mtime, as a rebuild would give it
        stat = (tmp_path / LAYERS_FILE).stat()
        import os

        os.utime(tmp_path / LAYERS_FILE, ns=(stat.st_atime_ns, stat.st_mtime_ns + 10**9))

        assert await api.query_near("Svc/MapServer/1", LAT, LON, 10, ("NAME",)) == [{"NAME": "new"}]


class TestLocalRasters:
    @pytest.fixture
    def raster_gis(self, tmp_path):
        values = np.full((20, 20), 1234, dtype="int16")  # 12.34 m
        values[0:10, :] = -32768  # northern half: no data
        write_raster(tmp_path, "dem.tif", "Dem/ImageServer", values, scale=0.01)
        return LocalGIS(tmp_path)

    @pytest.mark.asyncio
    async def test_samples_with_scale_and_nodata(self, raster_gis):
        values = await client(raster_gis).sample_many(
            "Dem/ImageServer", [(28.45, -81.4), (28.55, -81.4)]
        )

        assert values[0] == pytest.approx(12.34)
        assert values[1] is None

    @pytest.mark.asyncio
    async def test_points_outside_ask_the_server(self, raster_gis):
        def server(request):
            return httpx.Response(200, json={"samples": [{"locationId": 0, "value": "7"}]})

        api = client(raster_gis, server)
        assert await api.sample("Dem/ImageServer", 30.0, -81.4) == 7.0
