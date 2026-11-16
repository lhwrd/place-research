"""Tests for the generic ArcGIS client, using httpx.MockTransport."""

import json
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from app.integrations.arcgis_api import ArcGISClient


def make_client(*responses):
    requests = []
    queue = list(responses)

    def handler(request):
        requests.append(request)
        return httpx.Response(200, json=queue.pop(0))

    api = ArcGISClient("https://gis.example/arcgis/rest/services", service="test")
    api._client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return api, requests


@pytest.fixture(autouse=True)
def no_backoff_sleep():
    with patch("app.integrations.base_client.asyncio.sleep", new_callable=AsyncMock) as sleep:
        yield sleep


@pytest.mark.asyncio
async def test_query_near_attributes():
    api, requests = make_client({"features": [{"attributes": {"NAME": "a"}}]})

    features = await api.query_near("Svc/MapServer/0", 28.5, -81.4, 800, ("NAME",))

    assert features == [{"NAME": "a"}]
    params = requests[0].url.params
    assert requests[0].url.path == "/arcgis/rest/services/Svc/MapServer/0/query"
    assert params["geometry"] == "-81.4,28.5"
    assert params["distance"] == "800"
    assert params["units"] == "esriSRUnit_Meter"
    assert params["outFields"] == "NAME"
    assert params["f"] == "json"


@pytest.mark.asyncio
async def test_query_containing_point_has_no_distance():
    api, requests = make_client({"features": []})

    assert await api.query_near("Svc/FeatureServer/0", 28.5, -81.4) == []
    assert "distance" not in requests[0].url.params


@pytest.mark.asyncio
async def test_query_near_with_geometry():
    api, requests = make_client(
        {
            "features": [
                {
                    "properties": {"NAME": "pt"},
                    "geometry": {"type": "Point", "coordinates": [-81.4, 28.5]},
                },
                {"properties": {"NAME": "none"}, "geometry": None},
            ]
        }
    )

    features = await api.query_near("Svc/MapServer/0", 28.5, -81.4, 100, geometry=True)

    assert requests[0].url.params["f"] == "geojson"
    assert requests[0].url.params["outSR"] == "4326"
    assert features[0]["NAME"] == "pt"
    assert features[0]["geometry"].x == -81.4
    assert features[1]["geometry"] is None


@pytest.mark.asyncio
async def test_error_body_raises():
    api, _ = make_client({"error": {"code": 400, "message": "Invalid query"}})

    with pytest.raises(ValueError, match="Invalid query"):
        await api.query_near("Svc/MapServer/0", 28.5, -81.4)


@pytest.mark.asyncio
async def test_sample_many_keeps_order_and_nodata():
    api, requests = make_client(
        {
            "samples": [
                {"locationId": 1, "value": "NoData"},
                {"locationId": 0, "value": "24.5"},
                {"locationId": 2, "value": "26"},
            ]
        }
    )

    values = await api.sample_many("Dem/ImageServer", [(28.5, -81.4), (28.6, -81.5), (28.7, -81.6)])

    assert values == [24.5, None, 26.0]
    geometry = json.loads(requests[0].url.params["geometry"])
    assert geometry["points"] == [[-81.4, 28.5], [-81.5, 28.6], [-81.6, 28.7]]
    assert requests[0].url.path.endswith("/Dem/ImageServer/getSamples")


@pytest.mark.asyncio
async def test_sample_outside_raster():
    api, _ = make_client({"samples": []})

    assert await api.sample("Dem/ImageServer", 0, 0) is None
