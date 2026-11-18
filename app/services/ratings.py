"""Good / fair / poor ratings for the data points on the property page.

Each function takes a provider's stored data and returns GOOD, FAIR, POOR, or None when
there's nothing to rate. Thresholds are judgment calls for renting in Central Florida,
kept here in one place so they're easy to tune; changing them needs no re-enrich.

Demographics (the census section) are deliberately never rated.
"""

from typing import Any, Dict, Optional

from app.services.noise import NoiseEstimate

GOOD, FAIR, POOR = "good", "fair", "poor"
LEVELS = (GOOD, FAIR, POOR)

METERS_PER_MILE = 1609.344

Level = Optional[str]


def _bands(value: Optional[float], good_at: float, fair_at: float) -> Level:
    """Higher is better: >= good_at is GOOD, >= fair_at FAIR, else POOR."""
    if value is None:
        return None
    return GOOD if value >= good_at else FAIR if value >= fair_at else POOR


def _distance(meters: Optional[float], poor_within_mi: float, fair_within_mi: float) -> Level:
    """Farther is better."""
    if meters is None:
        return None
    miles = float(meters) / METERS_PER_MILE
    return POOR if miles < poor_within_mi else FAIR if miles < fair_within_mi else GOOD


# Location


def walk_score(score: Optional[float]) -> Level:
    return _bands(score, 70, 40)


def bike_score(score: Optional[float]) -> Level:
    return _bands(score, 70, 40)


def transit_score(score: Optional[float]) -> Level:
    return _bands(score, 50, 25)


def noise_level(estimate: Optional[NoiseEstimate]) -> Level:
    """Under 50 dB is quiet; 60+ is a busy road's worth."""
    if estimate is None or estimate.total_db is None:
        return None
    return POOR if estimate.total_db >= 60 else FAIR if estimate.total_db >= 50 else GOOD


def fireworks(data: Dict[str, Any]) -> Level:
    """Venues are only stored within 10 miles; within 3 the nightly show is loud."""
    venues = data.get("fireworks") or []
    if not venues:
        return None
    return _distance(venues[0]["distance_m"], 3, 10)


def launches(data: Dict[str, Any]) -> Level:
    """Sonic booms from booster landings reach about 30 miles; farther, it's a curiosity."""
    site = data.get("launch_site")
    if not site:
        return None
    return FAIR if float(site["distance_m"]) / METERS_PER_MILE <= 30 else None


def flood_zone(data: Dict[str, Any]) -> Level:
    zone = data.get("flood_zone")
    if not zone or zone == "Not mapped":
        return None
    if data.get("in_sfha"):
        return POOR
    if "0.2" in str(data.get("flood_risk") or ""):
        return FAIR
    return GOOD


def highway(meters: Optional[float]) -> Level:
    return _distance(meters, 0.2, 0.5)


def railroad(meters: Optional[float]) -> Level:
    return _distance(meters, 0.25, 0.5)


def air_quality(data: Dict[str, Any]) -> Level:
    aqi = data.get("aqi")
    if aqi is None:
        return None
    return GOOD if aqi <= 50 else FAIR if aqi <= 100 else POOR


# Miles within which each kind of odor source (odor_sources provider) is rated poor rather
# than fair: roughly where the smell goes from an occasional whiff to a regular nuisance
ODOR_STRONG_WITHIN_MI = {
    "paper_mill": 4,
    "landfill": 1.5,
    "rendering_plant": 1.5,
    "fertilizer_plant": 1.5,
    "sugar_mill": 1.5,
    "animal_feeding": 1,
    "biosolids": 0.5,
    "wastewater_plant": 0.5,
    "waste_to_energy": 0.5,
    "composting": 0.5,
    "debris_landfill": 0.5,
    "asphalt_plant": 0.5,
    "citrus_plant": 0.5,
    "transfer_station": 0.25,
    "petroleum_terminal": 0.25,
    "small_wastewater_plant": 0.1,
}


def odor_sources(data: Dict[str, Any]) -> Level:
    """Sources are only stored within the range their kind of smell carries."""
    if "sources" not in data:
        return None
    sources = data["sources"]
    if not sources:
        return GOOD
    strong = any(
        float(s["distance_m"]) / METERS_PER_MILE < ODOR_STRONG_WITHIN_MI.get(s.get("kind"), 0)
        for s in sources
    )
    return POOR if strong else FAIR


def food_drink(data: Dict[str, Any]) -> Level:
    """Good is a choice of places on foot; poor is a drive to anything."""
    if "places" not in data:
        return None
    walkable = data.get("walkable_count") or 0
    if walkable >= 8:
        return GOOD
    # Capped means at least 20 within the mile and a half searched
    return FAIR if walkable >= 2 or data.get("capped") else POOR


# A counted road within this many meters of the map pin is the one out front
FRONTING_ROAD_M = 50


def road_traffic(data: Dict[str, Any]) -> Level:
    """Vehicles a day on the road out front; a busy road a block away is only fair."""
    if "roads" not in data:
        return None
    roads = data["roads"]
    fronting = [r for r in roads if r["distance_m"] <= FRONTING_ROAD_M]
    if fronting:
        busiest = max(r["vehicles_per_day"] for r in fronting)
        return POOR if busiest >= 15_000 else FAIR if busiest >= 5_000 else GOOD
    return FAIR if any(r["vehicles_per_day"] >= 25_000 for r in roads) else GOOD


def attractions(data: Dict[str, Any]) -> Level:
    """Attractions are only stored within 5 miles; within 2 the daily traffic is yours too."""
    places = data.get("attractions") or []
    return _distance(places[0]["distance_m"], 2, 5) if places else None


def venues(data: Dict[str, Any]) -> Level:
    """Venues are only stored within 3 miles; within half a mile event nights block you in."""
    places = data.get("venues") or []
    return _distance(places[0]["distance_m"], 0.5, 3) if places else None


# Hazards


def sinkhole_geology(data: Dict[str, Any]) -> Level:
    return {
        "Least favorable": GOOD,
        "Favorable": FAIR,
        "More favorable": POOR,
        "Most favorable": POOR,
    }.get(data.get("favorability"))


def sinkhole_reports(data: Dict[str, Any]) -> Level:
    count = data.get("incidents_within_1mi")
    if count is None:
        return None
    if count == 0:
        return GOOD
    nearest = data.get("nearest_incident_m")
    close = nearest is not None and nearest < METERS_PER_MILE / 4
    return POOR if close or data.get("verified_within_1mi") else FAIR


def elevation(data: Dict[str, Any]) -> Level:
    """Sitting below the ground around it is what floods houses outside flood zones."""
    relative = data.get("relative_ft")
    if relative is None:
        return None
    return POOR if relative <= -3 else FAIR if relative <= -1 else GOOD


def evacuation_zone(data: Dict[str, Any]) -> Level:
    if "evacuation_zone" not in data:
        return None
    zone = data["evacuation_zone"]
    return GOOD if not zone else POOR if zone in ("A", "B") else FAIR


def wetlands(data: Dict[str, Any]) -> Level:
    if "in_wetland" not in data:
        return None
    if data["in_wetland"]:
        return POOR
    nearest = data.get("nearest_wetland_m")
    return FAIR if nearest is not None and nearest < 100 else GOOD


def contamination(data: Dict[str, Any]) -> Level:
    count = data.get("sites_within_half_mi")
    if count is None:
        return None
    if data.get("superfund_within_half_mi") or data.get("sites_within_quarter_mi"):
        return POOR
    return FAIR if count else GOOD


def impaired_waters(data: Dict[str, Any]) -> Level:
    if "impaired_waters" not in data:
        return None
    return FAIR if data["impaired_waters"] else GOOD


# Internet and drive times


def internet(data: Dict[str, Any], shown: list) -> Level:
    """Fiber is good; fast cable is fair; anything slower is poor for working from home."""
    if "providers" not in data:
        return None
    if any(p.get("technology") == "Fiber" for p in shown):
        return GOOD
    fastest = max((p["max_down_mbps"] for p in shown), default=0)
    return FAIR if fastest >= 300 else POOR


def drive_minutes(minutes: Optional[float]) -> Level:
    if minutes is None:
        return None
    return GOOD if minutes <= 15 else FAIR if minutes <= 30 else POOR


def beach_minutes(minutes: Optional[float]) -> Level:
    """A beach inside half an hour is an after-work trip; past an hour it's a day out."""
    if minutes is None:
        return None
    return GOOD if minutes <= 30 else FAIR if minutes <= 60 else POOR


def emergency_room(data: Dict[str, Any]) -> Level:
    """Minutes count in a heart attack or a stroke: within ten is good, past twenty poor."""
    if "ers" not in data:
        return None
    if not data["ers"]:
        return POOR
    minutes = data["ers"][0]["drive_minutes"]
    return GOOD if minutes <= 10 else FAIR if minutes <= 20 else POOR


# Sirens: a source this close is heard on most of its calls (poor) or some of them (fair)
FIRE_STATION_MI = (0.25, 0.5)
ER_MI = (0.5, 1.0)
HELIPORT_MI = (0.5, 1.0)
# Heliports that see regular traffic; private and corporate pads mostly don't
BUSY_HELIPORTS = {"hospital", "public", "tours"}


def sirens(data: Dict[str, Any], ers: Dict[str, Any]) -> Level:
    """Fire stations, ERs and busy helipads close by. ers is the emergency room data."""
    if "fire_stations" not in data:
        return None
    miles = lambda m: float(m) / METERS_PER_MILE  # noqa: E731
    fire = [miles(s["distance_m"]) for s in data["fire_stations"]]
    er = [miles(e["straight_line_m"]) for e in ers.get("ers") or []]
    pads = [miles(h["distance_m"]) for h in data.get("heliports") or []]
    busy = [
        miles(h["distance_m"])
        for h in data.get("heliports") or []
        if h.get("category") in BUSY_HELIPORTS
    ]

    def within(distances: list, limit: float) -> bool:
        return any(d <= limit for d in distances)

    if within(fire, FIRE_STATION_MI[0]) or within(er, ER_MI[0]) or within(busy, HELIPORT_MI[0]):
        return POOR
    if within(fire, FIRE_STATION_MI[1]) or within(er, ER_MI[1]) or within(pads, HELIPORT_MI[1]):
        return FAIR
    return GOOD


# Industry: right next door, anything is a neighbor you hear; heavy industry and big
# distribution centers carry further
INDUSTRY_ADJACENT_M = 100  # about 330 ft: the next lot or across the street
BIG_WAREHOUSE_SQFT = 100_000


def industry(data: Dict[str, Any]) -> Level:
    if "parcels" not in data:
        return None
    parcels = data["parcels"]
    if not parcels:
        return GOOD
    if any(
        p["kind"] == "heavy"
        or (p["kind"] == "warehouse" and (p.get("building_sqft") or 0) >= BIG_WAREHOUSE_SQFT)
        or (p["kind"] != "vacant" and p["distance_m"] <= INDUSTRY_ADJACENT_M)
        for p in parcels
    ):
        return POOR
    return FAIR


def vacant_homes(other_vacant_pct: Optional[float]) -> Level:
    """Homes empty and not for rent or sale; a few percent is normal turnover."""
    if other_vacant_pct is None:
        return None
    return GOOD if other_vacant_pct < 3 else FAIR if other_vacant_pct < 6 else POOR


def emergency_vet(data: Dict[str, Any]) -> Level:
    """A blocked cat or a swallowed lily can't wait for morning: the nearest 24-hour vet
    within a quarter hour is good; past half an hour, or none at all, is poor."""
    if "vets" not in data:
        return None
    minutes = next((v["drive_minutes"] for v in data["vets"] if v.get("open_24_hours")), None)
    if minutes is None:
        return POOR
    return GOOD if minutes <= 15 else FAIR if minutes <= 30 else POOR


def nearby_minutes(minutes: Optional[float]) -> Level:
    """Errands (groceries, pharmacy, ...) should be closer than a commute."""
    if minutes is None:
        return None
    return GOOD if minutes <= 10 else FAIR if minutes <= 20 else POOR
