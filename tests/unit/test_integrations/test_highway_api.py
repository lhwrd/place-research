from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.integrations.highway_api import HighwayAPIClient


@pytest.fixture
def highway_client():
    """Fixture to provide a HighwayAPIClient instance."""
    return HighwayAPIClient()


@pytest.mark.asyncio
async def test_init(highway_client):
    """Test HighwayAPIClient initialization."""
    assert highway_client.base_url == "https://overpass-api.de/api/interpreter"
    assert highway_client.api_key is None
    assert highway_client.timeout == 40.0
    assert highway_client.rate_limit_per_second == 10.0


def test_get_service_name(highway_client):
    """Test service name is correctly returned."""
    assert highway_client._get_service_name() == "highway_api"


@pytest.mark.asyncio
async def test_fetch_nearby_highways_success(highway_client):
    """Test successful highway fetch."""
    mock_response = MagicMock()
    mock_response.json.return_value = {"elements": [{"type": "way", "id": 123}]}
    mock_response.raise_for_status = MagicMock()

    with patch.object(highway_client.client, "post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_response

        result = await highway_client.fetch_nearby_highways(40.7128, -74.0060, 5.0)

        assert result == {"elements": [{"type": "way", "id": 123}]}
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        assert "data" in call_args.kwargs
        assert "around:8046.7" in call_args.kwargs["data"]["data"]


@pytest.mark.asyncio
async def test_fetch_nearby_highways_http_error(highway_client):
    """Test highway fetch with HTTP error."""
    mock_response = MagicMock()
    mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "Error", request=MagicMock(), response=MagicMock()
    )

    with patch.object(highway_client.client, "post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_response

        with pytest.raises(httpx.HTTPStatusError):
            await highway_client.fetch_nearby_highways(40.7128, -74.0060)


@pytest.mark.asyncio
async def test_validate_api_key_success(highway_client):
    """Test successful API validation."""
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()

    with patch.object(highway_client.client, "get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_response

        result = await highway_client.validate_api_key()

        assert result is True
        mock_get.assert_called_once_with(highway_client.base_url)


@pytest.mark.asyncio
async def test_validate_api_key_http_error(highway_client):
    """Test API validation with HTTP error."""
    with patch.object(highway_client.client, "get", new_callable=AsyncMock) as mock_get:
        mock_get.side_effect = httpx.HTTPError("Error")

        result = await highway_client.validate_api_key()

        assert result is False


@pytest.mark.asyncio
async def test_validate_api_key_request_error(highway_client):
    """Test API validation with request error."""
    with patch.object(highway_client.client, "get", new_callable=AsyncMock) as mock_get:
        mock_get.side_effect = httpx.RequestError("Error")

        result = await highway_client.validate_api_key()

        assert result is False


def _response(status_code, payload=None):
    response = MagicMock()
    response.status_code = status_code
    response.json.return_value = payload
    if status_code >= 400:
        response.raise_for_status.side_effect = httpx.HTTPStatusError(
            str(status_code), request=MagicMock(), response=response
        )
    return response


@pytest.mark.asyncio
async def test_fetch_nearby_highways_retries_when_busy(highway_client):
    """502/429/timeouts are retried with backoff, as Overpass asks."""
    ok = _response(200, {"elements": []})

    with (
        patch.object(highway_client.client, "post", new_callable=AsyncMock) as mock_post,
        patch("app.integrations.highway_api.asyncio.sleep", new_callable=AsyncMock) as sleep,
    ):
        mock_post.side_effect = [_response(502), httpx.ReadTimeout("slow"), _response(429), ok]

        result = await highway_client.fetch_nearby_highways(40.7, -74.0)

    assert result == {"elements": []}
    assert mock_post.call_count == 4
    assert [c.args[0] for c in sleep.await_args_list] == [2.0, 4.0, 8.0]


@pytest.mark.asyncio
async def test_fetch_nearby_highways_gives_up_after_max_attempts(highway_client):
    with (
        patch.object(highway_client.client, "post", new_callable=AsyncMock) as mock_post,
        patch("app.integrations.highway_api.asyncio.sleep", new_callable=AsyncMock),
    ):
        mock_post.return_value = _response(502)

        with pytest.raises(httpx.HTTPStatusError):
            await highway_client.fetch_nearby_highways(40.7, -74.0)

    assert mock_post.call_count == 4


@pytest.mark.asyncio
async def test_fetch_nearby_highways_does_not_retry_client_errors(highway_client):
    with (
        patch.object(highway_client.client, "post", new_callable=AsyncMock) as mock_post,
        patch("app.integrations.highway_api.asyncio.sleep", new_callable=AsyncMock) as sleep,
    ):
        mock_post.return_value = _response(400)

        with pytest.raises(httpx.HTTPStatusError):
            await highway_client.fetch_nearby_highways(40.7, -74.0)

    assert mock_post.call_count == 1
    sleep.assert_not_called()
