"""Tests for the Open-Meteo air quality client."""

from unittest.mock import AsyncMock

import pytest

from app.exceptions.external_api import ExternalAPIError
from app.integrations.air_quality_api import AirQualityAPIClient, aqi_category


@pytest.fixture
def client():
    return AirQualityAPIClient()


def _response(us_aqi, pm2_5=7.9, ozone=56.0):
    return {
        "current": {"time": "2026-11-06T09:00", "us_aqi": us_aqi, "pm2_5": pm2_5, "ozone": ozone}
    }


class TestAirQualityAPIClient:
    def test_init(self, client):
        assert client.base_url == "https://air-quality-api.open-meteo.com"
        assert client.api_key is None
        assert client._get_auth_headers() == {}
        assert client._get_service_name() == "air_quality"

    @pytest.mark.asyncio
    async def test_get_air_quality_success(self, client):
        client._make_request = AsyncMock(return_value=_response(42))

        result = await client.get_air_quality(latitude=29.13, longitude=-80.98)

        assert result == {"aqi": 42, "category": "Good", "pm2_5": 7.9, "ozone": 56.0}
        client._make_request.assert_awaited_once_with(
            method="GET",
            endpoint="v1/air-quality",
            params={"latitude": 29.13, "longitude": -80.98, "current": "us_aqi,pm2_5,ozone"},
        )

    @pytest.mark.asyncio
    async def test_get_air_quality_api_error(self, client):
        client._make_request = AsyncMock(
            side_effect=ExternalAPIError(service="air_quality", message="boom")
        )
        assert await client.get_air_quality(latitude=1.0, longitude=2.0) == {}

    @pytest.mark.asyncio
    @pytest.mark.parametrize("response", [{}, {"current": {}}, _response(None)])
    async def test_get_air_quality_no_data(self, client, response):
        client._make_request = AsyncMock(return_value=response)
        assert await client.get_air_quality(latitude=1.0, longitude=2.0) == {}

    @pytest.mark.asyncio
    async def test_validate_api_key(self, client):
        client._make_request = AsyncMock(return_value=_response(30))
        assert await client.validate_api_key() is True

        client._make_request = AsyncMock(return_value={})
        assert await client.validate_api_key() is False


@pytest.mark.parametrize(
    "aqi,expected",
    [
        (None, None),
        (0, "Good"),
        (50, "Good"),
        (51, "Moderate"),
        (150, "Unhealthy for Sensitive Groups"),
        (200, "Unhealthy"),
        (300, "Very Unhealthy"),
        (301, "Hazardous"),
    ],
)
def test_aqi_category(aqi, expected):
    assert aqi_category(aqi) == expected
