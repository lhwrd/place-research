"""Turn a stored property's provider data into display-ready sections for the web UI.

Providers' raw data is kept in the database as-is; formatting lives here so it can change
without re-enriching anything.
"""

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from app.services import noise
from app.services.noise import NoiseEstimate

METERS_PER_MILE = 1609.344

Rows = List[Tuple[str, str]]


@dataclass
class DriveTime:
    name: str
    minutes: Optional[float]
    miles: Optional[float]

    @property
    def available(self) -> bool:
        return self.minutes is not None


@dataclass
class Distribution:
    """A labelled set of percentages, e.g. a tract's age groups."""

    title: str
    items: List[Tuple[str, float]]


@dataclass
class PropertyView:
    surroundings: Rows = field(default_factory=list)
    drive_times: List[DriveTime] = field(default_factory=list)
    nearby_places: List[Dict[str, Any]] = field(default_factory=list)
    census: Rows = field(default_factory=list)
    distributions: List[Distribution] = field(default_factory=list)
    acs_year: Optional[int] = None
    noise: Optional[NoiseEstimate] = None


def build_view(enrichment: Dict[str, Dict[str, Any]]) -> PropertyView:
    """Build the detail-page view from {provider name: data}."""
    view = PropertyView()
    data = lambda name: enrichment.get(name) or {}  # noqa: E731

    walk = data("walk_score_provider")

    highway = data("highway_provider")
    rail = data("railroad_provider")
    airports = data("airport_provider").get("airports")
    view.noise = noise_estimate(highway, rail, airports)
    nearest_airport = airports[0] if airports else None
    view.surroundings = _rows(
        ("Walk score", _score_text(walk.get("walk_score"), walk.get("description"))),
        ("Bike score", _score_text(walk.get("bike_score"), walk.get("bike_description"))),
        (
            "Transit score",
            _score_text(walk.get("transit_score"), walk.get("transit_description")),
        ),
        ("Noise", noise_text(view.noise)),
        ("Noise by source", noise_sources_text(view.noise)),
        ("Flood zone", flood_zone_text(data("flood_zone_provider"))),
        (
            "Nearest highway",
            _with_name(
                _miles_text(highway.get("highway_distance_m")), highway.get("nearest_highway_name")
            ),
        ),
        ("Nearest railroad", _miles_text(rail.get("railroad_distance_m"))),
        (
            "Nearest airport",
            _with_name(
                _miles_text(nearest_airport["distance_m"]),
                f"{nearest_airport['code']}, {nearest_airport['name']}",
            )
            if nearest_airport
            else None,
        ),
        ("Air quality", air_quality_text(data("air_quality_provider"))),
    )

    view.drive_times = drive_times(data("distance_provider"))
    view.nearby_places = [
        {
            "name": p.get("name"),
            "type": p.get("type"),
            "address": p.get("address"),
            "minutes": p.get("drive_minutes"),
            "miles": p.get("drive_miles"),
        }
        for p in data("places_nearby_provider").get("places_nearby", [])
        if p.get("name")
    ]

    census = data("census_provider")
    view.acs_year = census.get("acs_year")
    view.census, view.distributions = census_sections(census)
    return view


def noise_estimate(
    highway: Dict[str, Any], rail: Dict[str, Any], airports: Optional[List[Dict[str, Any]]]
) -> Optional[NoiseEstimate]:
    """Noise from stored distances, or None if no provider has measured anything yet."""
    if "highway_distances_m" in highway:
        road = noise.loudest(noise.ROAD_LEVELS, highway["highway_distances_m"])
    else:  # enriched before per-class distances were stored
        road = highway.get("road_noise_level_db")

    rail_db = None
    if rail.get("railroad_distance_m") is not None:
        rail_db = noise.loudest(
            noise.RAIL_LEVELS,
            # Enriched before main lines were told apart: assume the nearest track is one
            {
                "mainline": rail.get("mainline_distance_m", rail["railroad_distance_m"]),
                "other": rail["railroad_distance_m"],
            },  # fmt: skip
        )

    aircraft = None
    if airports is not None:
        levels = [
            noise.source_level(noise.AIRPORT_LEVELS[a["category"]], a["distance_m"])
            for a in airports
            if a.get("category") in noise.AIRPORT_LEVELS
        ]
        # Measured, nothing within range: as quiet as it gets
        aircraft = round(max(levels), 1) if levels else noise.AMBIENT_DB

    if road is None and rail_db is None and aircraft is None:
        return None
    return NoiseEstimate(road_db=road, rail_db=rail_db, aircraft_db=aircraft)


def noise_text(estimate: Optional[NoiseEstimate]) -> Optional[str]:
    """E.g. "Moderate · 57 dB, mostly road"."""
    if estimate is None or estimate.total_db is None:
        return None
    text = f"{estimate.category} · {estimate.total_db:.0f} dB"
    return f"{text}, mostly {estimate.main_source}" if estimate.main_source else text


def noise_sources_text(estimate: Optional[NoiseEstimate]) -> Optional[str]:
    """E.g. "Road 57 · Rail 49 · Aircraft 41 dB"; sources not measured are left out."""
    if estimate is None:
        return None
    parts = [
        f"{label} {db:.0f}"
        for label, db in (
            ("Road", estimate.road_db),
            ("Rail", estimate.rail_db),
            ("Aircraft", estimate.aircraft_db),
        )
        if db is not None
    ]
    return " · ".join(parts) + " dB" if parts else None


def flood_zone_text(data: Dict[str, Any]) -> Optional[str]:
    """E.g. "AE (high-risk SFHA, BFE 7 ft)" or "X (0.2% annual chance flood hazard)"."""
    zone = data.get("flood_zone")
    if not zone:
        return None

    details = []
    if data.get("flood_risk"):
        # FEMA subtypes are upper case with "PCT" for percent
        details.append(re.sub(r"\s*pct\b", "%", data["flood_risk"].lower()))
    if data.get("in_sfha"):
        details.append("high-risk SFHA")
    if data.get("base_flood_elevation_ft") is not None:
        details.append(f"BFE {data['base_flood_elevation_ft']:g} ft")
    return f"{zone} ({', '.join(details)})" if details else zone


def air_quality_text(data: Dict[str, Any]) -> Optional[str]:
    parts = []
    if data.get("aqi") is not None:
        parts.append(f"AQI {data['aqi']}")
    if data.get("category"):
        parts.append(str(data["category"]))
    return " ".join(parts) or None


def drive_times(data: Dict[str, Any]) -> List[DriveTime]:
    times = []
    for d in data.get("distances", []):
        ok = d.get("status") == "OK"
        minutes = (
            (d.get("duration_in_traffic_minutes") or d.get("duration_minutes")) if ok else None
        )
        times.append(
            DriveTime(
                name=d.get("location_name") or "Unknown",
                minutes=minutes,
                miles=d.get("distance_miles") if ok else None,
            )
        )
    return times


def census_sections(data: Dict[str, Any]) -> Tuple[Rows, List[Distribution]]:
    city = data.get("city") or {}
    county = data.get("county") or {}
    tract = data.get("tract") or {}

    city_name = city.get("name")
    if city_name and city.get("type") == "CDP":
        city_name = f"{city_name} (CDP)"

    rows = _rows(
        ("City", city_name),
        ("City population", _count(city.get("population"))),
        ("County", _join(county.get("name"), data.get("state"))),
        ("County population", _count(county.get("population"))),
        ("Census tract", tract.get("geoid")),
        ("Tract population", _count(tract.get("population"))),
        ("Tract median age", _unit(tract.get("median_age"), "")),
        ("Bachelor's or higher", _unit(tract.get("bachelors_or_higher_pct"), "%")),
    )

    # Race & ethnicity: largest first, and leave out groups with nobody in them
    race = sorted((tract.get("race_ethnicity") or {}).items(), key=lambda kv: -kv[1])
    distributions = [
        Distribution("Age", list((tract.get("age_groups") or {}).items())),
        Distribution("Race & ethnicity", [(k, v) for k, v in race if v > 0]),
        Distribution("Education (25+)", list((tract.get("education") or {}).items())),
    ]
    return rows, [d for d in distributions if d.items]


def _rows(*pairs: Tuple[str, Any]) -> Rows:
    return [(label, str(value)) for label, value in pairs if value is not None and value != ""]


def _miles_text(meters: Any) -> Optional[str]:
    return f"{float(meters) / METERS_PER_MILE:.2f} mi" if meters is not None else None


def _score_text(score: Any, description: Optional[str]) -> Optional[str]:
    """E.g. "47 · Car-Dependent"; just the score if there's no description."""
    if score is None:
        return None
    return f"{score} · {description}" if description else str(score)


def _with_name(text: Optional[str], name: Optional[str]) -> Optional[str]:
    return f"{text} ({name})" if text and name else text


def _unit(value: Any, unit: str) -> Optional[str]:
    """One decimal at most: 72.34 -> "72.3", 38.0 -> "38"."""
    return f"{round(float(value), 1):g}{unit}" if value is not None else None


def _count(value: Any) -> Optional[str]:
    return f"{int(value):,}" if value is not None else None


def _join(*parts: Optional[str]) -> Optional[str]:
    return ", ".join(p for p in parts if p) or None
