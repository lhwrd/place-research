from unittest.mock import AsyncMock, patch

import httpx
import pytest

from app.services.enrichment.base_provider import ProviderCategory
from app.services.enrichment.providers.census import CensusProvider

DATA = {
    "acs_year": 2024,
    "state": "Colorado",
    "city": {"name": "Boulder", "type": "incorporated", "geoid": "0807850", "population": 105000},
    "county": {"name": "Boulder County", "geoid": "08013", "population": 330000},
    "tract": {"name": "Census Tract 122.06", "geoid": "08013012206", "population": 1000},
}


@pytest.fixture
def provider():
    with patch("app.services.enrichment.providers.census.CensusAPIClient"):
        provider = CensusProvider()
    provider.api_client.get_demographics = AsyncMock(return_value=DATA)
    return provider


def test_metadata(provider):
    metadata = provider.metadata

    assert metadata.name == "census_provider"
    assert metadata.category == ProviderCategory.DEMOGRAPHICS
    assert metadata.enabled is True
    assert metadata.requires_api_key is True


@pytest.mark.asyncio
async def test_enrich_success(provider):
    result = await provider.enrich(latitude=40.0, longitude=-105.0, address="1 Main St")

    assert result.success is True
    assert result.data == DATA
    assert result.api_calls_made == 5
    provider.api_client.get_demographics.assert_awaited_once_with(40.0, -105.0)


@pytest.mark.asyncio
async def test_enrich_failure_redacts_key(provider):
    request = httpx.Request("GET", "https://api.census.gov/data/2024/acs/acs5?key=secret123")
    provider.api_client.get_demographics.side_effect = httpx.ConnectError(
        f"failed {request.url}", request=request
    )

    result = await provider.enrich(latitude=40.0, longitude=-105.0, address="1 Main St")

    assert result.success is False
    assert result.data == {}
    assert "secret123" not in result.error_message


@pytest.mark.asyncio
async def test_enrich_missing_key(provider):
    provider.api_client.get_demographics.side_effect = ValueError("CENSUS_API_KEY is not set")

    result = await provider.enrich(latitude=40.0, longitude=-105.0, address="1 Main St")

    assert result.success is False
    assert result.error_message == "CENSUS_API_KEY is not set"
