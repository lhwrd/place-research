"""Tests for the good/fair/poor thresholds."""

import pytest

from app.services import ratings
from app.services.noise import NoiseEstimate
from app.services.ratings import FAIR, GOOD, POOR

MILE = 1609.344


@pytest.mark.parametrize(
    "score,level", [(None, None), (85, GOOD), (70, GOOD), (55, FAIR), (12, POOR)]
)
def test_walk_score(score, level):
    assert ratings.walk_score(score) == level


@pytest.mark.parametrize("db,level", [(45, GOOD), (55, FAIR), (65, POOR)])
def test_noise(db, level):
    assert ratings.noise_level(NoiseEstimate(road_db=db, rail_db=None, aircraft_db=None)) == level


def test_noise_unmeasured():
    assert ratings.noise_level(None) is None


@pytest.mark.parametrize(
    "data,level",
    [
        ({"flood_zone": "AE", "in_sfha": True}, POOR),
        ({"flood_zone": "X", "flood_risk": "0.2 PCT ANNUAL CHANCE FLOOD HAZARD"}, FAIR),
        ({"flood_zone": "X", "flood_risk": "AREA OF MINIMAL FLOOD HAZARD"}, GOOD),
        ({"flood_zone": "Not mapped"}, None),
        ({}, None),
    ],
)
def test_flood_zone(data, level):
    assert ratings.flood_zone(data) == level


@pytest.mark.parametrize("miles,level", [(0.1, POOR), (0.3, FAIR), (2, GOOD), (None, None)])
def test_highway(miles, level):
    assert ratings.highway(miles * MILE if miles is not None else None) == level


@pytest.mark.parametrize(
    "data,level",
    [
        ({"incidents_within_1mi": 0}, GOOD),
        ({"incidents_within_1mi": 2, "nearest_incident_m": 1200}, FAIR),
        ({"incidents_within_1mi": 1, "nearest_incident_m": 200}, POOR),
        ({"incidents_within_1mi": 1, "nearest_incident_m": 1200, "verified_within_1mi": 1}, POOR),
        ({}, None),
    ],
)
def test_sinkhole_reports(data, level):
    assert ratings.sinkhole_reports(data) == level


@pytest.mark.parametrize("relative,level", [(2.0, GOOD), (-0.5, GOOD), (-1.5, FAIR), (-3.5, POOR)])
def test_elevation(relative, level):
    assert ratings.elevation({"relative_ft": relative}) == level


@pytest.mark.parametrize("zone,level", [(None, GOOD), ("A", POOR), ("B", POOR), ("D", FAIR)])
def test_evacuation_zone(zone, level):
    assert ratings.evacuation_zone({"evacuation_zone": zone}) == level


@pytest.mark.parametrize(
    "data,level",
    [
        ({"in_wetland": True}, POOR),
        ({"in_wetland": False, "nearest_wetland_m": 40}, FAIR),
        ({"in_wetland": False, "nearest_wetland_m": 400}, GOOD),
        ({"in_wetland": False, "nearest_wetland_m": None}, GOOD),
    ],
)
def test_wetlands(data, level):
    assert ratings.wetlands(data) == level


@pytest.mark.parametrize(
    "data,level",
    [
        ({"sites_within_half_mi": 0}, GOOD),
        ({"sites_within_half_mi": 2, "sites_within_quarter_mi": 0}, FAIR),
        ({"sites_within_half_mi": 2, "sites_within_quarter_mi": 1}, POOR),
        ({"sites_within_half_mi": 1, "superfund_within_half_mi": 1}, POOR),
    ],
)
def test_contamination(data, level):
    assert ratings.contamination(data) == level


def test_fireworks_and_launches():
    assert ratings.fireworks({"fireworks": [{"distance_m": 2 * MILE}]}) == POOR
    assert ratings.fireworks({"fireworks": [{"distance_m": 5 * MILE}]}) == FAIR
    assert ratings.fireworks({"fireworks": []}) is None
    assert ratings.launches({"launch_site": {"distance_m": 20 * MILE}}) == FAIR
    assert ratings.launches({"launch_site": {"distance_m": 60 * MILE}}) is None


@pytest.mark.parametrize(
    "shown,level",
    [
        ([{"technology": "Fiber", "max_down_mbps": 1000}], GOOD),
        ([{"technology": "Cable", "max_down_mbps": 1000}], FAIR),
        ([{"technology": "DSL", "max_down_mbps": 50}], POOR),
        ([], POOR),
    ],
)
def test_internet(shown, level):
    assert ratings.internet({"providers": shown}, shown) == level


def test_drive_and_nearby_minutes():
    assert [ratings.drive_minutes(m) for m in (10, 25, 45, None)] == [GOOD, FAIR, POOR, None]
    assert [ratings.nearby_minutes(m) for m in (5, 15, 25)] == [GOOD, FAIR, POOR]
