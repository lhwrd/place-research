"""Tests for the Baserow API client, using httpx.MockTransport."""

import json

import httpx
import pytest

from app.exceptions import APIKeyInvalidError, ExternalAPIError
from app.integrations.baserow_api import BaserowAPI

FIELDS = [
    {"id": 1, "name": "Address", "type": "text"},
    {"id": 2, "name": "Zillow ID", "type": "text"},
    {
        "id": 3,
        "name": "Status",
        "type": "single_select",
        "select_options": [{"id": 30, "value": "New"}, {"id": 31, "value": "Enriched"}],
    },
]


def make_client(handler):
    """BaserowAPI whose HTTP calls go to handler; records each request."""
    requests = []

    def record(request: httpx.Request):
        requests.append(request)
        return handler(request)

    api = BaserowAPI(base_url="https://baserow.test", api_token="tok")
    api._client = httpx.AsyncClient(transport=httpx.MockTransport(record))
    return api, requests


def fields_or(handler):
    def route(request):
        if "/fields/" in request.url.path:
            return httpx.Response(200, json=FIELDS)
        return handler(request)

    return route


@pytest.mark.asyncio
async def test_auth_header_and_field_names():
    api, requests = make_client(lambda r: httpx.Response(200, json={"id": 5, "Address": "1 Main"}))

    row = await api.get_row(837, 5)

    assert row["Address"] == "1 Main"
    assert requests[0].headers["Authorization"] == "Token tok"
    assert requests[0].url.path == "/api/database/rows/table/837/5/"
    assert requests[0].url.params["user_field_names"] == "true"


@pytest.mark.asyncio
async def test_list_rows_paginates_and_filters_by_field_id():
    pages = {
        "1": {"results": [{"id": 1}], "next": "https://baserow.test/next"},
        "2": {"results": [{"id": 2}], "next": None},
    }
    api, requests = make_client(
        fields_or(lambda r: httpx.Response(200, json=pages[r.url.params["page"]]))
    )

    rows = await api.list_rows(837, equals={"Zillow ID": "123"}, include=["id", "Status"])

    assert [r["id"] for r in rows] == [1, 2]
    row_requests = [r for r in requests if "/rows/" in r.url.path]
    assert len(row_requests) == 2
    assert row_requests[0].url.params["filter__field_2__equal"] == "123"
    assert row_requests[0].url.params["include"] == "id,Status"


@pytest.mark.asyncio
async def test_fields_are_cached():
    api, requests = make_client(fields_or(lambda r: httpx.Response(500)))

    await api.get_fields(837)
    await api.get_fields(837)

    assert len(requests) == 1


@pytest.mark.asyncio
async def test_select_option_id():
    api, _ = make_client(fields_or(lambda r: httpx.Response(500)))

    assert await api.select_option_id(837, "Status", "Enriched") == 31
    with pytest.raises(ValueError):
        await api.select_option_id(837, "Status", "Bogus")
    with pytest.raises(ValueError):
        await api.select_option_id(837, "Nope", "New")


@pytest.mark.asyncio
async def test_create_and_update_send_json():
    api, requests = make_client(lambda r: httpx.Response(200, json={"id": 9}))

    await api.create_row(837, {"Address": "1 Main"})
    await api.update_row(837, 9, {"Status": 31})

    assert requests[0].method == "POST"
    assert json.loads(requests[0].content) == {"Address": "1 Main"}
    assert requests[1].method == "PATCH"
    assert requests[1].url.path == "/api/database/rows/table/837/9/"
    assert json.loads(requests[1].content) == {"Status": 31}


@pytest.mark.asyncio
async def test_upload_file_is_multipart():
    api, requests = make_client(lambda r: httpx.Response(200, json={"name": "abc.jpg"}))

    result = await api.upload_file(b"\xff\xd8", "photo.jpg", "image/jpeg")

    assert result == {"name": "abc.jpg"}
    assert requests[0].url.path == "/api/user-files/upload-file/"
    assert requests[0].headers["Content-Type"].startswith("multipart/form-data")
    assert b'filename="photo.jpg"' in requests[0].content


@pytest.mark.asyncio
async def test_baserow_error_body_is_parsed():
    api, _ = make_client(
        lambda r: httpx.Response(
            404, json={"error": "ERROR_ROW_DOES_NOT_EXIST", "detail": "Row 5 does not exist."}
        )
    )

    with pytest.raises(ExternalAPIError) as exc_info:
        await api.get_row(837, 5)

    assert exc_info.value.details["api_status_code"] == 404
    assert "ERROR_ROW_DOES_NOT_EXIST" in exc_info.value.message


@pytest.mark.asyncio
async def test_permission_denied_is_auth_error():
    api, _ = make_client(lambda r: httpx.Response(401, json={"error": "ERROR_INVALID_TOKEN"}))

    with pytest.raises(APIKeyInvalidError):
        await api.get_row(837, 5)
