"""Tests for the bundled-list BeachParkingProvider (Distance Matrix mocked)."""

from unittest.mock import AsyncMock

import pandas as pd
import pytest

from app.services.enrichment.providers.beach_parking import (
    BEACH_PARKING_CSV,
    MAX_BEACHES,
    BeachParkingProvider,
)

LAT, LON = 28.5, -81.4
# Degrees of longitude per mile at this latitude
MILE = 1 / 60.7


def _sites(*rows):
    """rows: (name, beach, miles east of the property[, fee])."""
    return pd.DataFrame(
        [
            {"name": name, "beach": beach, "county": "Brevard", "coast": "Atlantic",
             "address": "", "spaces": "" if i % 2 else 20, "fee": fee[0] if fee else "",
             "latitude": LAT, "longitude": LON + miles * MILE}
            for i, (name, beach, miles, *fee) in enumerate(rows)
        ]
    )  # fmt: skip


def _provider(sites, drive_minutes):
    """drive_minutes: per candidate, nearest (straight line) first; None is unreachable."""
    provider = BeachParkingProvider(sites=sites)
    provider.api_client.distance_matrix = AsyncMock(
        return_value=[
            {"destination_index": i, "status": "OK", "duration_minutes": m, "distance_miles": m}
            if m is not None
            else {"destination_index": i, "status": "ZERO_RESULTS"}
            for i, m in enumerate(drive_minutes)
        ]
    )
    return provider


@pytest.mark.asyncio
async def test_shortest_drive_wins_over_shortest_line():
    sites = _sites(
        ("Playalinda Lot 1", "Canaveral Seashore", 40),  # nearest, but a long way round
        ("Playalinda Lot 2", "Canaveral Seashore", 40.5),  # same beach: not looked up
        ("Lori Wilson Park", "Cocoa Beach", 48, "1.50/hr"),
        ("No Road", "Island", 50),
    )
    provider = _provider(sites, [75, 55, None])

    result = await provider.enrich(LAT, LON, "x")

    assert result.success and result.api_calls_made == 1
    destinations = provider.api_client.distance_matrix.call_args.kwargs["destinations"]
    assert len(destinations) == 3
    assert [s["name"] for s in result.data["sites"]] == ["Lori Wilson Park", "Playalinda Lot 1"]
    nearest = result.data["sites"][0]
    assert (nearest["drive_minutes"], nearest["beach"], nearest["fee"]) == (
        55,
        "Cocoa Beach",
        "1.50/hr",
    )
    assert nearest["straight_line_m"] == pytest.approx(48 * 1609.344, rel=0.01)
    assert result.data["sites"][1]["spaces"] == 20 and nearest["spaces"] == 20


@pytest.mark.asyncio
async def test_compares_only_the_nearest_few_beaches():
    sites = _sites(*((f"Access {i}", f"Beach {i}", 30 + i) for i in range(MAX_BEACHES + 3)))
    provider = _provider(sites, range(40, 40 + MAX_BEACHES))

    result = await provider.enrich(LAT, LON, "x")

    assert [s["name"] for s in result.data["sites"]] == [f"Access {i}" for i in range(MAX_BEACHES)]


@pytest.mark.asyncio
async def test_no_beach_in_range_makes_no_call():
    provider = _provider(_sites(("Far", "Far Beach", 400)), [])

    result = await provider.enrich(LAT, LON, "x")

    assert result.success and result.data == {"sites": []} and result.api_calls_made == 0
    provider.api_client.distance_matrix.assert_not_called()


@pytest.mark.asyncio
async def test_failures():
    provider = _provider(_sites(("A", "Beach", 10)), [None])
    assert (await provider.enrich(LAT, LON, "x")).success is False

    provider.api_client.distance_matrix = AsyncMock(side_effect=RuntimeError("quota"))
    result = await provider.enrich(LAT, LON, "x")
    assert result.success is False and result.error_message == "quota" and result.data == {}


def test_bundled_list():
    sites = pd.read_csv(BEACH_PARKING_CSV, keep_default_na=False)

    assert len(sites) > 1000
    assert set(sites["coast"]) == {"Gulf", "Atlantic"}
    assert (
        sites["latitude"].between(24, 31.1).all() and sites["longitude"].between(-88, -79.9).all()
    )
    # The default provider reads it: Cocoa Beach is the closest beach to Orlando
    nearest = BeachParkingProvider().candidates(28.5384, -81.3789)
    assert len(nearest) == MAX_BEACHES and nearest[0]["county"] in ("Brevard", "Volusia")
