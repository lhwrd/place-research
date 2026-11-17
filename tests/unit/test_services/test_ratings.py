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


@pytest.mark.parametrize(
    "data,level",
    [
        ({}, None),
        ({"sources": []}, GOOD),
        ({"sources": [{"kind": "landfill", "distance_m": 2 * MILE}]}, FAIR),
        ({"sources": [{"kind": "landfill", "distance_m": 1 * MILE}]}, POOR),
        # A mile is close for a landfill but not for a paper mill, and vice versa at three
        ({"sources": [{"kind": "paper_mill", "distance_m": 3 * MILE}]}, POOR),
        ({"sources": [{"kind": "wastewater_plant", "distance_m": 0.8 * MILE}]}, FAIR),
        (
            {
                "sources": [
                    {"kind": "transfer_station", "distance_m": 0.4 * MILE},
                    {"kind": "wastewater_plant", "distance_m": 0.3 * MILE},
                ]
            },
            POOR,
        ),
        ({"sources": [{"kind": "something_new", "distance_m": 10}]}, FAIR),
    ],
)
def test_odor_sources(data, level):
    assert ratings.odor_sources(data) == level


@pytest.mark.parametrize(
    "data,level",
    [
        ({}, None),
        ({"places": [], "walkable_count": 0, "capped": False}, POOR),
        ({"places": [{}], "walkable_count": 1, "capped": False}, POOR),
        ({"places": [{}], "walkable_count": 2, "capped": False}, FAIR),
        ({"places": [{}], "walkable_count": 0, "capped": True}, FAIR),  # 20 a short drive away
        ({"places": [{}], "walkable_count": 8, "capped": True}, GOOD),
    ],
)
def test_food_drink(data, level):
    assert ratings.food_drink(data) == level


@pytest.mark.parametrize(
    "roads,level",
    [
        (None, None),
        ([], GOOD),  # no counted road: a local street
        ([(20, 3000)], GOOD),
        ([(20, 7800)], FAIR),
        ([(20, 24000)], POOR),
        ([(20, 3000), (45, 16000)], POOR),  # a corner lot: the busier road counts
        ([(120, 24000)], GOOD),  # a block back from it
        ([(120, 63000)], FAIR),
    ],
)
def test_road_traffic(roads, level):
    data = (
        {}
        if roads is None
        else {"roads": [{"distance_m": d, "vehicles_per_day": v} for d, v in roads]}
    )
    assert ratings.road_traffic(data) == level


def test_attractions_and_venues():
    def at(key, miles):
        return {key: [{"distance_m": miles * MILE}]}

    assert [ratings.attractions(at("attractions", m)) for m in (1, 3)] == [POOR, FAIR]
    assert [ratings.venues(at("venues", m)) for m in (0.3, 1)] == [POOR, FAIR]
    assert ratings.attractions({"attractions": []}) is None and ratings.venues({}) is None


def test_beach_minutes():
    assert [ratings.beach_minutes(m) for m in (None, 30, 31, 60, 61)] == [
        None, GOOD, FAIR, FAIR, POOR,
    ]  # fmt: skip


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
