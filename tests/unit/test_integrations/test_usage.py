"""Tests for API usage recording."""

from unittest.mock import AsyncMock, patch

import httpx
import pytest

from app.integrations import usage
from app.integrations.arcgis_api import ArcGISClient
from app.integrations.base_client import BaseAPIClient
from app.integrations.usage import billing


def _request(method, url, **kwargs):
    return httpx.Request(method, url, **kwargs)


@pytest.mark.parametrize(
    "request_,expected",
    [
        (
            _request("GET", "https://maps.googleapis.com/maps/api/geocode/json?address=x&key=k"),
            ("Geocoding", 1),
        ),
        (
            _request(
                "GET",
                "https://maps.googleapis.com/maps/api/distancematrix/json",
                params={"origins": "1,2", "destinations": "3,4|5,6|7,8", "key": "k"},
            ),
            ("Distance Matrix", 3),
        ),
        (
            _request(
                "GET",
                "https://maps.googleapis.com/maps/api/distancematrix/json",
                params={"origins": "1,2", "destinations": "3,4", "departure_time": "now"},
            ),
            ("Distance Matrix Advanced", 1),
        ),
        (
            _request("GET", "https://maps.googleapis.com/maps/api/streetview/metadata?key=k"),
            (None, 1),  # free
        ),
        (
            _request("POST", "https://places.googleapis.com/v1/places:searchNearby"),
            ("Places Nearby Search Pro", 1),
        ),
        (
            _request("POST", "https://places.googleapis.com/v1/places:searchText"),
            ("Places Text Search Pro", 1),
        ),
        (
            _request("GET", "https://places.googleapis.com/v1/places/ChIJabc"),
            ("Place Details Pro", 1),
        ),
        (_request("GET", "https://api.census.gov/data/2024/acs/acs5?key=k"), (None, 1)),
    ],
)
def test_billing(request_, expected):
    assert billing(request_) == expected


class _Client(BaseAPIClient):
    def _get_service_name(self):
        return "test_service"

    async def validate_api_key(self):
        return True


def _serve(client, handler):
    """Answer the client's requests with handler, keeping the hooks its own client has."""
    real = client.client
    client._client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler), event_hooks=real.event_hooks
    )


@pytest.fixture
def recorded(db):
    with patch("app.db.get_database", return_value=db):
        yield db


@pytest.mark.asyncio
async def test_records_each_response_without_the_query_string(recorded):
    client = _Client(base_url="https://maps.googleapis.com/maps/api")
    _serve(client, lambda request: httpx.Response(200, json={}))

    await client._make_request(
        "GET", "distancematrix/json", params={"destinations": "1,2|3,4", "key": "SECRET"}
    )

    [call] = recorded.list_api_calls()
    assert call["service"] == "test_service"
    assert call["host"] == "maps.googleapis.com"
    assert call["endpoint"] == "/maps/api/distancematrix/json"
    assert (call["method"], call["status"]) == ("GET", 200)
    assert (call["sku"], call["units"]) == ("Distance Matrix", 2)
    assert call["duration_ms"] >= 0 and call["at"]
    assert "SECRET" not in str(call)


@pytest.mark.asyncio
async def test_errors_and_retries_are_recorded(recorded):
    responses = [httpx.Response(503), httpx.Response(200, json={"features": []})]
    client = ArcGISClient("https://gis.test/arcgis/rest/services", service="Test GIS")
    _serve(client, lambda request: responses.pop(0))

    with patch("app.integrations.base_client.asyncio.sleep", new_callable=AsyncMock):
        await client.query_near("Layer/MapServer/0", 29.0, -81.0)

    calls = recorded.list_api_calls()
    assert [c["status"] for c in calls] == [503, 200]
    assert {c["service"] for c in calls} == {"Test GIS"}
    assert calls[0]["sku"] is None


@pytest.mark.asyncio
async def test_a_recording_failure_does_not_fail_the_request(recorded):
    client = _Client(base_url="https://api.test")
    _serve(client, lambda request: httpx.Response(200, json={"ok": True}))

    with patch.object(recorded, "record_api_call", side_effect=RuntimeError("disk full")):
        assert await client._make_request("GET", "thing") == {"ok": True}


def test_hooks_cover_request_and_response():
    hooks = usage.usage_hooks(lambda: "x")
    assert set(hooks) == {"request", "response"}
