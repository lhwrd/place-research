"""Tests for the bundled-list AirportProvider."""

import pandas as pd
import pytest

from app.services.enrichment.providers import airports
from app.services.enrichment.providers.airports import AirportProvider

# ~111 km per degree of latitude
METERS_PER_DEGREE_LAT = 111_195


def _airports(*rows):
    """rows: (iata, name, category, latitude offset north of 29.0, -81.0)."""
    return pd.DataFrame(
        [
            {"ident": f"K{iata or 'X'}{i}", "iata": iata, "name": name, "category": category,
             "latitude": 29.0 + offset, "longitude": -81.0}
            for i, (iata, name, category, offset) in enumerate(rows)
        ]
    )  # fmt: skip


@pytest.fixture
def provider():
    return AirportProvider(
        airports=_airports(
            ("DAB", "Daytona Beach Intl", "regional", 0.1),  # ~11 km
            ("", "Spruce Creek", "general", -0.05),  # ~5.6 km, no IATA code
            ("MCO", "Orlando Intl", "large", 1.0),  # ~111 km: out of range
        )
    )


@pytest.mark.asyncio
async def test_nearby_airports_closest_first(provider):
    result = await provider.enrich(29.0, -81.0, "x")

    assert result.success
    assert result.api_calls_made == 0
    found = result.data["airports"]
    assert [a["code"] for a in found] == ["KX1", "DAB"]  # ICAO-style ident without IATA
    assert found[0]["category"] == "general"
    assert found[1]["distance_m"] == pytest.approx(0.1 * METERS_PER_DEGREE_LAT, rel=0.001)


@pytest.mark.asyncio
async def test_no_airports_in_range(provider):
    assert (await provider.enrich(45.0, -100.0, "x")).data == {"airports": []}


def test_at_most_five():
    rows = [(f"A{i}", f"Airport {i}", "general", i / 100) for i in range(8)]
    found = AirportProvider(airports=_airports(*rows)).nearby(29.0, -81.0)

    assert [a["code"] for a in found] == ["A0", "A1", "A2", "A3", "A4"]


def test_bundled_list_loads(monkeypatch):
    monkeypatch.setattr(AirportProvider, "_shared_airports", None)

    provider = AirportProvider()
    # Daytona Beach International, ~9 km from Port Orange
    nearest = provider.nearby(29.135898, -80.98285)[0]

    assert airports.AIRPORTS_CSV.exists()
    assert nearest["code"] == "DAB"
    assert set(provider._airports["category"]) == {"large", "military", "regional", "general"}


@pytest.mark.asyncio
async def test_metadata_and_config(provider):
    assert provider.metadata.name == "airport_provider"
    assert provider.metadata.requires_api_key is False
    assert await provider.validate_config() is True
