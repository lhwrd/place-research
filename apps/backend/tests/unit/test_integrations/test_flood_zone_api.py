from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import Response

from app.integrations.flood_zone_api import FloodZoneAPIClient


@pytest.fixture
def mock_settings():
    with patch("app.integrations.flood_zone_api.settings") as mock:
        mock.national_flood_data_api_key = "test-api-key"
        yield mock


@pytest.fixture
def flood_client(mock_settings):
    return FloodZoneAPIClient()


@pytest.mark.asyncio
async def test_init(flood_client):
    assert flood_client.base_url == "https://api.nationalflooddata.com/v3/data"
    assert flood_client.api_key == "test-api-key"
    assert flood_client.timeout == 30.0
    assert flood_client.rate_limit_per_second == 5.0


def test_get_service_name(flood_client):
    assert flood_client._get_service_name() == "flood_zone_api"


def test_get_auth_headers(flood_client):
    headers = flood_client._get_auth_headers()
    assert headers == {"x-api-key": "test-api-key"}


@pytest.mark.asyncio
async def test_validate_api_key_success(flood_client):
    mock_response = MagicMock(spec=Response)
    mock_response.status_code = 200
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock()
    mock_client.is_closed = False

    flood_client._client = mock_client

    result = await flood_client.validate_api_key()

    assert result is True
    mock_client.get.assert_called_once()


@pytest.mark.asyncio
async def test_validate_api_key_unauthorized(flood_client):
    mock_response = MagicMock(spec=Response)
    mock_response.status_code = 401

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock()
    mock_client.is_closed = False

    flood_client._client = mock_client

    result = await flood_client.validate_api_key()

    assert result is False


@pytest.mark.asyncio
async def test_fetch_flood_zone_data_success(flood_client):
    expected_data = {"flood_zone": "AE", "flood_risk": "High"}
    return_value = {
        "result": {
            "flood.s_fld_haz_ar": [
                {
                    "fld_zone": "AE",
                    "zone_subty": "High",
                }
            ]
        }
    }
    mock_response = MagicMock(spec=Response)
    mock_response.status_code = 200
    mock_response.json = MagicMock(return_value=return_value)
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock()
    mock_client.is_closed = False

    flood_client._client = mock_client

    result = await flood_client.fetch_flood_zone_data(40.7128, -74.0060, "123 Main St")

    assert result == expected_data
    mock_client.get.assert_called_once_with(
        flood_client.base_url,
        params={
            "lat": "40.7128",
            "lon": "-74.006",
            "address": "123 Main St",
            "searchtype": "addresscoord",
        },
        headers={"x-api-key": "test-api-key"},
    )
