"""Tests for the FEMA NFHL client, using httpx.MockTransport."""

from unittest.mock import AsyncMock, patch

import httpx
import pytest

from app.integrations.fema_nfhl_api import NOT_MAPPED, FemaNfhlAPIClient

X_SHADED = {
    "FLD_ZONE": "X",
    "ZONE_SUBTY": "0.2 PCT ANNUAL CHANCE FLOOD HAZARD",
    "SFHA_TF": "F",
    "STATIC_BFE": -9999.0,
}
AE = {"FLD_ZONE": "AE", "ZONE_SUBTY": None, "SFHA_TF": "T", "STATIC_BFE": 7.0}
X_MINIMAL = {
    "FLD_ZONE": "X",
    "ZONE_SUBTY": "AREA OF MINIMAL FLOOD HAZARD",
    "SFHA_TF": "F",
    "STATIC_BFE": -9999.0,
}


def _features(*zones):
    return {"features": [{"attributes": z} for z in zones]}


def make_client(*responses):
    """Client whose requests get the given responses (or exceptions) in order."""
    requests = []
    queue = list(responses)

    def handler(request):
        requests.append(request)
        item = queue.pop(0)
        if isinstance(item, Exception):
            raise item
        if isinstance(item, httpx.Response):
            return item
        return httpx.Response(200, json=item)

    api = FemaNfhlAPIClient()
    api._client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return api, requests


@pytest.fixture(autouse=True)
def no_backoff_sleep():
    with patch("app.integrations.base_client.asyncio.sleep", new_callable=AsyncMock) as sleep:
        yield sleep


@pytest.mark.asyncio
async def test_query_parameters():
    api, requests = make_client(_features(X_SHADED))

    await api.get_flood_zone(latitude=29.135898, longitude=-80.98285)

    request = requests[0]
    assert request.url.path == "/arcgis/rest/services/public/NFHL/MapServer/28/query"
    params = request.url.params
    assert params["geometry"] == "-80.98285,29.135898"  # x (lon), y (lat)
    assert params["geometryType"] == "esriGeometryPoint"
    assert params["inSR"] == "4326"
    assert params["returnGeometry"] == "false"
    assert params["f"] == "json"


@pytest.mark.asyncio
async def test_moderate_zone():
    api, _ = make_client(_features(X_SHADED))

    assert await api.get_flood_zone(29.1, -80.9) == {
        "flood_zone": "X",
        "flood_risk": "0.2 PCT ANNUAL CHANCE FLOOD HAZARD",
        "in_sfha": False,
        "base_flood_elevation_ft": None,
    }


@pytest.mark.asyncio
async def test_riskiest_overlapping_zone_wins():
    api, _ = make_client(_features(X_MINIMAL, AE, X_SHADED))

    result = await api.get_flood_zone(29.1, -80.9)

    assert result == {
        "flood_zone": "AE",
        "flood_risk": None,
        "in_sfha": True,
        "base_flood_elevation_ft": 7.0,
    }


@pytest.mark.asyncio
async def test_unmapped_area():
    api, _ = make_client({"features": []})

    result = await api.get_flood_zone(29.1, -80.9)

    assert result["flood_zone"] == NOT_MAPPED
    assert result["in_sfha"] is None


@pytest.mark.asyncio
async def test_arcgis_error_body():
    api, _ = make_client({"error": {"code": 400, "message": "Invalid geometry"}})

    with pytest.raises(ValueError, match="Invalid geometry"):
        await api.get_flood_zone(29.1, -80.9)


@pytest.mark.asyncio
async def test_retries_connection_resets(no_backoff_sleep):
    api, requests = make_client(
        httpx.ConnectError("reset"), httpx.Response(503), _features(X_SHADED)
    )

    result = await api.get_flood_zone(29.1, -80.9)

    assert result["flood_zone"] == "X"
    assert len(requests) == 3
    assert no_backoff_sleep.await_count == 2


@pytest.mark.asyncio
async def test_gives_up_after_retries():
    api, _ = make_client(*[httpx.ConnectError("reset")] * 4)

    with pytest.raises(httpx.ConnectError):
        await api.get_flood_zone(29.1, -80.9)


@pytest.mark.asyncio
async def test_validate_api_key():
    api, _ = make_client(_features(X_MINIMAL))
    assert await api.validate_api_key() is True

    api, _ = make_client({"features": []})
    assert await api.validate_api_key() is False
