"""Tests for the noise model."""

import pytest

from app.services import noise
from app.services.noise import NoiseEstimate


def test_level_at_reference_and_doublings():
    assert noise.level_at(75, 30, 10) == 75
    assert noise.level_at(75, 30, 30) == 75
    assert noise.level_at(75, 30, 60) == 69
    assert noise.level_at(75, 30, 120) == 63


def test_level_never_drops_below_ambient():
    assert noise.level_at(65, 30, 1_000_000) == noise.AMBIENT_DB


def test_loudest_kind():
    # Roads fade 5 dB per doubling: interstate at 60 m is 70, US highway at 30 m is 65
    assert noise.loudest(noise.ROAD_LEVELS, {"motorway": 60, "primary": 30}) == 70
    assert noise.loudest(noise.ROAD_LEVELS, {"primary": None, "unknown": 5}) is None
    assert noise.loudest(noise.ROAD_LEVELS, {}) is None


def test_combine_adds_sound_energy():
    assert noise.combine([60, 60]) == pytest.approx(63.0, abs=0.05)
    assert noise.combine([70, 50]) == pytest.approx(70.0, abs=0.05)
    assert noise.combine([60, None]) == 60


def test_combine_ignores_ambient_sources():
    # Three quiet sources shouldn't add up to "Low"
    assert noise.combine([35, 35, 35]) == noise.AMBIENT_DB
    assert noise.combine([35, 50]) == 50
    assert noise.combine([None, None]) is None


@pytest.mark.parametrize(
    "db,name",
    [(None, "Unknown"), (75, "Very High"), (70, "Very High"), (65, "High"),
     (55, "Moderate"), (45, "Low"), (35, "Very Low")],
)  # fmt: skip
def test_category(db, name):
    assert noise.category(db) == name


def test_estimate():
    estimate = NoiseEstimate(road_db=57, rail_db=60, aircraft_db=None)

    assert estimate.total_db == pytest.approx(61.8, abs=0.05)
    assert estimate.category == "High"
    assert estimate.main_source == "rail"


def test_estimate_all_quiet_has_no_main_source():
    estimate = NoiseEstimate(road_db=35, rail_db=None, aircraft_db=35)

    assert estimate.main_source is None
    assert estimate.category == "Very Low"


def test_point_and_line_sources_fade_differently():
    assert noise.level_at(75, 30, 60) == 69  # point source (default): 6 dB per doubling
    assert noise.level_at(75, 30, 60, noise.LINE_SOURCE_DB_PER_DOUBLING) == 70


@pytest.mark.parametrize(
    "miles,expected",
    [
        (0.05, "Very High"),
        (0.11, "Very High"),  # close enough to feel it
        (0.5, "High"),  # still clearly heard from inside
        (1.0, "Moderate"),
        (3.0, "Low"),  # far tracks fade
    ],
)
def test_living_near_a_main_line(miles, expected):
    rail = noise.loudest(noise.RAIL_LEVELS, {"mainline": miles * 1609.344})

    assert noise.category(rail) == expected


def test_spur_is_quieter_than_main_line():
    spur = noise.loudest(noise.RAIL_LEVELS, {"other": 300})
    main = noise.loudest(noise.RAIL_LEVELS, {"mainline": 300})

    assert main - spur == pytest.approx(10)
