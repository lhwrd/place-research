"""Tests for the emergency vet provider."""

from unittest.mock import AsyncMock, patch

import pytest

from app.services.enrichment.providers.emergency_vet import (
    MAX_24_HOUR,
    MAX_LIMITED_HOURS,
    EmergencyVetProvider,
    emergency_vets,
)

LAT, LON = 28.55, -81.37
# ~1 m of latitude, in degrees
M = 1 / 110_950
MILE = 1609.344


def _vet(name, miles, open_24_hours=None, **extra):
    place = {"name": name, "address": f"{name} St", "latitude": LAT + miles * MILE * M,
             "longitude": LON, **extra}  # fmt: skip
    if open_24_hours is not None:
        place["open_24_hours"] = open_24_hours
    return place


@pytest.fixture
def provider():
    with (
        patch("app.services.enrichment.providers.emergency_vet.GooglePlacesAPI"),
        patch("app.services.enrichment.providers.emergency_vet.GoogleMapsAPI"),
    ):
        return EmergencyVetProvider()


def test_keeps_24_hour_vets_and_limited_hours_ers_only():
    found = [
        _vet("Main Street Animal Clinic", 0.5, open_24_hours=False),  # general practice
        _vet("BluePearl Pet Hospital", 6, open_24_hours=True),
        _vet("Pet ER of Winter Park", 2, open_24_hours=False),
        _vet("VEG 24/7 Animal Hospital", 4),  # no hours listed; the name says so
        _vet("Urgent Pet Care", 3, open_24_hours=False),
        _vet("Closed Emergency Vet", 1, open_24_hours=True, business_status="CLOSED_PERMANENTLY"),
        _vet("Bergen Veterinary", 1),  # "er" inside a word isn't an ER
        {"name": "No location", "latitude": None, "longitude": None, "open_24_hours": True},
    ]

    vets = emergency_vets(LAT, LON, found)

    assert [(v["name"], v["open_24_hours"]) for v in vets] == [
        ("VEG 24/7 Animal Hospital", True),
        ("BluePearl Pet Hospital", True),
        ("Pet ER of Winter Park", False),
        ("Urgent Pet Care", False),
    ]
    assert vets[0]["straight_line_m"] == pytest.approx(4 * MILE, rel=0.01)


def test_limits_the_drive_times_looked_up():
    found = [_vet(f"Emergency Vet {i}", i, open_24_hours=True) for i in range(1, 6)]
    found += [_vet(f"Urgent Care {i}", i, open_24_hours=False) for i in range(1, 6)]

    vets = emergency_vets(LAT, LON, found)

    assert sum(v["open_24_hours"] for v in vets) == MAX_24_HOUR
    assert sum(not v["open_24_hours"] for v in vets) == MAX_LIMITED_HOURS


@pytest.mark.asyncio
async def test_sorts_by_drive_time(provider):
    provider.places_api.text_search = AsyncMock(
        return_value=[
            _vet("Across The Lake Emergency", 3, open_24_hours=True),
            _vet("Highway Pet Emergency", 5, open_24_hours=True),
        ]
    )
    provider.maps_api.distance_matrix = AsyncMock(
        return_value=[
            {"destination_index": 0, "status": "OK", "duration_minutes": 25, "distance_miles": 9},
            {"destination_index": 1, "status": "OK", "duration_minutes": 11, "distance_miles": 6},
        ]
    )

    result = await provider.enrich(LAT, LON, "x")

    assert result.success and result.api_calls_made == 2
    vets = result.data["vets"]
    assert [(v["name"], v["drive_minutes"]) for v in vets] == [
        ("Highway Pet Emergency", 11),
        ("Across The Lake Emergency", 25),
    ]
    assert "latitude" not in vets[0]
    search = provider.places_api.text_search.call_args.kwargs
    assert search["included_type"] == "veterinary_care"
    assert search["opening_hours"] is True and search["merge_departments"] is False


@pytest.mark.asyncio
async def test_none_in_range_skips_drive_times(provider):
    provider.places_api.text_search = AsyncMock(
        return_value=[_vet("Country Animal Clinic", 8, open_24_hours=False)]
    )
    provider.maps_api.distance_matrix = AsyncMock()

    result = await provider.enrich(LAT, LON, "x")

    assert result.success and result.api_calls_made == 1
    assert result.data == {"vets": [], "radius_m": round(30 * MILE)}
    provider.maps_api.distance_matrix.assert_not_called()


@pytest.mark.asyncio
async def test_search_failure(provider):
    provider.places_api.text_search = AsyncMock(side_effect=RuntimeError("quota"))

    result = await provider.enrich(LAT, LON, "x")

    assert not result.success and result.error_message == "quota"
