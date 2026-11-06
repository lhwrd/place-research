from unittest.mock import AsyncMock, patch

import httpx
import pytest

from app.services.enrichment.base_provider import ProviderCategory
from app.services.enrichment.providers.flood_zone import FloodZoneProvider

ZONE = {
    "flood_zone": "X",
    "flood_risk": "0.2 PCT ANNUAL CHANCE FLOOD HAZARD",
    "in_sfha": False,
    "base_flood_elevation_ft": None,
}


@pytest.fixture
def provider():
    with patch("app.services.enrichment.providers.flood_zone.FemaNfhlAPIClient"):
        provider = FloodZoneProvider()
    provider.api_client.get_flood_zone = AsyncMock(return_value=ZONE)
    return provider


def test_metadata(provider):
    metadata = provider.metadata

    assert metadata.name == "flood_zone_provider"
    assert metadata.category == ProviderCategory.ENVIRONMENTAL
    assert metadata.enabled is True
    assert metadata.version == "2.0.0"
    assert metadata.requires_api_key is False
    assert metadata.cost_per_call == 0.0


@pytest.mark.asyncio
async def test_enrich_success(provider):
    result = await provider.enrich(latitude=29.1, longitude=-80.9, address="1 Main St")

    assert result.success is True
    assert result.data == ZONE
    assert result.api_calls_made == 1
    provider.api_client.get_flood_zone.assert_awaited_once_with(29.1, -80.9)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "error",
    [
        httpx.ConnectError("reset"),
        httpx.ReadTimeout("slow"),
        ValueError("FEMA NFHL query failed: Invalid geometry"),
    ],
)
async def test_enrich_failure(provider, error):
    provider.api_client.get_flood_zone.side_effect = error

    result = await provider.enrich(latitude=29.1, longitude=-80.9, address="1 Main St")

    assert result.success is False
    assert result.data == {}
    assert result.error_message == str(error)


@pytest.mark.asyncio
async def test_validate_config(provider):
    provider.api_client.validate_api_key = AsyncMock(return_value=True)
    assert await provider.validate_config() is True
