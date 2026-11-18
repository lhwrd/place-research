"""Tests for the bundled-list MallsProvider (Distance Matrix mocked)."""

from unittest.mock import AsyncMock

import pandas as pd
import pytest

from app.services.enrichment.providers.malls import MALLS_CSV, MAX_HEALTHY, MallsProvider

LAT, LON = 28.5, -81.4
# Degrees of longitude per mile at this latitude
MILE = 1 / 60.7


def _malls(*rows):
    """rows: (name, status, miles east of the property)."""
    return pd.DataFrame(
        [
            {"name": name, "city": "Town", "kind": "enclosed", "status": status,
             "note": "Sears gone" if status == "dead" else "",
             "latitude": LAT, "longitude": LON + miles * MILE}
            for name, status, miles in rows
        ]
    )  # fmt: skip


def _provider(malls, drive_minutes):
    """drive_minutes: per healthy mall, nearest (straight line) first; None is unreachable."""
    provider = MallsProvider(malls=malls)
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
async def test_healthy_by_drive_and_declining_by_distance():
    malls = _malls(
        ("Dead Mall", "dead", 0.8),
        ("Rebuild", "redeveloping", 1),  # left out of both
        ("Near Healthy", "healthy", 5),
        ("Struggling Far", "struggling", 4),  # past the neighborhood radius
        ("Thriving", "thriving", 6),
        ("No Road", "healthy", 7),
    )
    provider = _provider(malls, [25, 12, None])

    result = await provider.enrich(LAT, LON, "x")

    assert result.success and result.api_calls_made == 1
    assert len(provider.api_client.distance_matrix.call_args.kwargs["destinations"]) == 3
    assert [m["name"] for m in result.data["healthy"]] == ["Thriving", "Near Healthy"]
    assert result.data["healthy"][0]["drive_minutes"] == 12
    [dead] = result.data["declining"]
    assert (dead["name"], dead["note"]) == ("Dead Mall", "Sears gone")
    assert dead["straight_line_m"] == pytest.approx(0.8 * 1609.344, rel=0.01)


@pytest.mark.asyncio
async def test_compares_only_the_nearest_few():
    malls = _malls(*((f"Mall {i}", "healthy", 2 + i) for i in range(MAX_HEALTHY + 2)))
    provider = _provider(malls, range(10, 10 + MAX_HEALTHY))

    result = await provider.enrich(LAT, LON, "x")

    assert [m["name"] for m in result.data["healthy"]] == [f"Mall {i}" for i in range(MAX_HEALTHY)]


@pytest.mark.asyncio
async def test_no_healthy_mall_in_range_makes_no_call():
    provider = _provider(_malls(("Far", "healthy", 200), ("Dead", "dead", 1)), [])

    result = await provider.enrich(LAT, LON, "x")

    assert result.success and result.api_calls_made == 0
    assert result.data["healthy"] == [] and [m["name"] for m in result.data["declining"]] == [
        "Dead"
    ]
    provider.api_client.distance_matrix.assert_not_called()


@pytest.mark.asyncio
async def test_failures():
    provider = _provider(_malls(("A", "healthy", 3)), [None])
    assert (await provider.enrich(LAT, LON, "x")).success is False

    provider.api_client.distance_matrix = AsyncMock(side_effect=RuntimeError("quota"))
    result = await provider.enrich(LAT, LON, "x")
    assert result.success is False and result.error_message == "quota" and result.data == {}


def test_bundled_list():
    malls = pd.read_csv(MALLS_CSV, keep_default_na=False)

    assert len(malls) > 50 and malls["name"].is_unique
    assert set(malls["status"]) == {"thriving", "healthy", "struggling", "dead", "redeveloping"}
    assert set(malls["kind"]) <= {"enclosed", "open-air", "outlet"}
    assert (malls["note"] != "").all()
    assert (
        malls["latitude"].between(24, 31.1).all() and malls["longitude"].between(-88, -79.9).all()
    )
    # The default provider reads it: Altamonte Mall is the nearest to its own parking lot
    nearest = MallsProvider().nearby(28.6648, -81.3730)[0]
    assert (nearest["name"], nearest["status"]) == ("Altamonte Mall", "healthy")
