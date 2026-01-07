import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.exceptions.external_api import ExternalAPIError
from app.integrations.air_quality_api import AirQualityAPIClient


@pytest.fixture
def mock_settings():
    with patch("app.integrations.air_quality_api.settings") as mock:
        mock.airnow_api_key = "test_api_key"
        yield mock


@pytest.fixture
def client(mock_settings):
    return AirQualityAPIClient()


class TestAirQualityAPIClient:
    def test_init(self, client):
        assert client.base_url == "https://www.airnowapi.org"
        assert client.api_key == "test_api_key"
        assert client.timeout == 10.0
        assert client.rate_limit_per_second == 1.0

    def test_get_service_name(self, client):
        assert client._get_service_name() == "air_quality"

    def test_get_auth_headers(self, client):
        assert client._get_auth_headers() == {}

    @pytest.mark.asyncio
    async def test_validate_api_key_success(self, client):
        mock_data = [{"AQI": 50}]
        client._make_request = AsyncMock(return_value=mock_data)

        result = await client.validate_api_key()

        assert result is True
        client._make_request.assert_called_once_with(
            method="GET",
            endpoint="aq/forecast/latLong/",
            params={
                "API_KEY": "test_api_key",
                "latitude": "34.0522",
                "longitude": "-118.2437",
                "format": "application/json",
                "distance": 25,
            },
        )

    @pytest.mark.asyncio
    async def test_validate_api_key_empty_response(self, client):
        client._make_request = AsyncMock(return_value=None)

        result = await client.validate_api_key()

        assert result is False

    @pytest.mark.asyncio
    async def test_validate_api_key_api_error(self, client):
        client._make_request = AsyncMock(
            side_effect=ExternalAPIError(service="air_quality", message="API Error")
        )

        result = await client.validate_api_key()

        assert result is False

    @pytest.mark.asyncio
    async def test_get_air_quality_success(self, client):
        mock_data = [{"AQI": 75, "Category": "Moderate"}]
        client._make_request = AsyncMock(return_value=mock_data)

        result = await client.get_air_quality(40.7128, -74.0060, distance=30)

        assert result == {"AQI": 75, "Category": "Moderate"}
        client._make_request.assert_called_once_with(
            method="GET",
            endpoint="aq/forecast/latLong/",
            params={
                "API_KEY": "test_api_key",
                "latitude": "40.7128",
                "longitude": "-74.006",
                "format": "application/json",
                "distance": 30,
            },
        )

    @pytest.mark.asyncio
    async def test_get_air_quality_default_distance(self, client):
        mock_data = [{"AQI": 100}]
        client._make_request = AsyncMock(return_value=mock_data)

        result = await client.get_air_quality(34.0522, -118.2437)

        assert result == {"AQI": 100}
        assert client._make_request.call_args[1]["params"]["distance"] == 50

    @pytest.mark.asyncio
    async def test_get_air_quality_api_error(self, client):
        client._make_request = AsyncMock(side_effect=ExternalAPIError("air_quality", "API Error"))

        result = await client.get_air_quality(40.7128, -74.0060)

        assert result == {}

    @pytest.mark.asyncio
    async def test_get_air_quality_empty_response(self, client):
        client._make_request = AsyncMock(return_value=[])

        result = await client.get_air_quality(40.7128, -74.0060)

        assert result == {}

    @pytest.mark.asyncio
    async def test_get_air_quality_none_response(self, client):
        client._make_request = AsyncMock(return_value=None)

        result = await client.get_air_quality(40.7128, -74.0060)

        assert result == {}
