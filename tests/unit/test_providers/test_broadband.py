"""Tests for the FCC broadband build script and provider."""

import importlib.util
import zipfile
from pathlib import Path
from unittest.mock import AsyncMock

import httpx
import pandas as pd
import pytest

from app.services.enrichment.providers.broadband import BroadbandProvider

SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "build_broadband.py"
spec = importlib.util.spec_from_file_location("build_broadband", SCRIPT)
build_broadband = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build_broadband)

BLOCK = "120950189021048"
OTHER_BLOCK = "120950189021049"


def _rows(*rows):
    """FCC availability rows: (location, brand, tech, down, up, bus/res, block)."""
    return pd.DataFrame(
        [
            {
                "frn": "0001", "provider_id": 1, "brand_name": brand, "location_id": loc,
                "technology": tech, "max_advertised_download_speed": down,
                "max_advertised_upload_speed": up, "low_latency": 1,
                "business_residential_code": code, "state_usps": "FL", "block_geoid": block,
                "h3_res8_id": "88",
            }
            for loc, brand, tech, down, up, code, block in rows
        ]
    )  # fmt: skip


@pytest.fixture
def fcc_files(tmp_path):
    cable = _rows(
        (1, "Spectrum", 40, 1000, 35, "X", BLOCK),
        (2, "Spectrum", 40, 1000, 35, "R", BLOCK),
        (3, "Spectrum", 40, 500, 20, "R", BLOCK),
        (4, "Spectrum", 40, 1000, 35, "R", BLOCK),
        (9, "Spectrum", 40, 300, 10, "R", OTHER_BLOCK),
    )
    fiber = _rows(
        (1, "AT&T Fiber", 50, 5000, 5000, "R", BLOCK),
        (5, "AT&T Fiber", 50, 5000, 5000, "B", BLOCK),  # business only: not counted
    )
    satellite = _rows((1, "Starlink", 61, 220, 25, "X", BLOCK))

    cable_csv = tmp_path / "cable.csv"
    cable.to_csv(cable_csv, index=False)
    fiber_zip = tmp_path / "fiber.zip"
    with zipfile.ZipFile(fiber_zip, "w") as z:
        z.writestr("bdc_12_FiberToThePremises.csv", fiber.to_csv(index=False))
        z.writestr("readme.txt", "not data")
    satellite_csv = tmp_path / "satellite.csv"
    satellite.to_csv(satellite_csv, index=False)
    return [cable_csv, fiber_zip, satellite_csv]


def test_build_rolls_up_to_blocks(tmp_path, fcc_files):
    output = tmp_path / "out" / "broadband.parquet"

    build_broadband.build(output, fcc_files, include_satellite=False)

    table = pd.read_parquet(output)
    block = table[table["block_geoid"] == BLOCK].set_index("brand_name")
    assert set(block.index) == {"Spectrum", "AT&T Fiber"}  # satellite skipped
    assert block.loc["Spectrum", "max_down"] == 1000
    assert block.loc["Spectrum", "locations"] == 4
    assert block.loc["AT&T Fiber", "locations"] == 1
    # Locations 1-4 are residential in the block (5 is business-only)
    assert (block["block_locations"] == 4).all()


def test_build_can_keep_satellite(tmp_path, fcc_files):
    output = tmp_path / "broadband.parquet"
    build_broadband.build(output, fcc_files, include_satellite=True)
    assert "Starlink" in set(pd.read_parquet(output)["brand_name"])


@pytest.fixture
def provider(tmp_path, fcc_files):
    output = tmp_path / "broadband.parquet"
    build_broadband.build(output, fcc_files, include_satellite=False)
    provider = BroadbandProvider(broadband_data=pd.read_parquet(output))
    provider.census_client.get_block_geoid = AsyncMock(return_value=BLOCK)
    return provider


@pytest.mark.asyncio
async def test_lookup(provider):
    result = await provider.enrich(28.5383, -81.3792, "x")

    assert result.success
    data = result.data
    assert data["block_geoid"] == BLOCK
    assert data["fiber_available"] is True
    assert data["wired_providers"] == 2
    assert data["max_down_mbps"] == 5000
    first, second = data["providers"]
    assert (first["name"], first["technology"], first["coverage_pct"]) == (
        "AT&T Fiber",
        "Fiber",
        25,
    )
    assert (second["name"], second["technology"], second["coverage_pct"]) == (
        "Spectrum",
        "Cable",
        100,
    )


@pytest.mark.asyncio
async def test_block_not_in_file(provider):
    provider.census_client.get_block_geoid = AsyncMock(return_value="129999999999999")

    data = (await provider.enrich(0, 0, "x")).data

    assert data["providers"] == []
    assert data["fiber_available"] is False
    assert data["max_down_mbps"] is None


@pytest.mark.asyncio
async def test_geocoder_error(provider):
    provider.census_client.get_block_geoid = AsyncMock(side_effect=httpx.ConnectError("down"))

    result = await provider.enrich(0, 0, "x")

    assert not result.success


def test_requires_path(monkeypatch):
    from app.services.enrichment.providers import broadband

    monkeypatch.setattr(broadband.settings, "broadband_path", None)
    monkeypatch.setattr(BroadbandProvider, "_shared_blocks", None)
    with pytest.raises(ValueError, match="BROADBAND_PATH"):
        BroadbandProvider()
