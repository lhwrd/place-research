"""Turn a stored property's provider data into display-ready sections for the web UI.

Providers' raw data is kept in the database as-is; formatting lives here so it can change
without re-enriching anything.
"""

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from app.services import noise, ratings
from app.services.noise import NoiseEstimate
from app.services.zillow_listing import ListingDetails, parse_listing_details

METERS_PER_MILE = 1609.344


@dataclass
class Row:
    """One labelled value, rated ratings.GOOD/FAIR/POOR or unrated (None)."""

    label: str
    value: str
    level: Optional[str] = None


Rows = List[Row]


@dataclass
class DriveTime:
    name: str
    minutes: Optional[float]
    miles: Optional[float]
    level: Optional[str] = None

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
    hazards: Rows = field(default_factory=list)
    internet_summary: Optional[Row] = None
    internet: List[Dict[str, Any]] = field(default_factory=list)
    # The county property appraiser's record (Florida); unrated, so not in the scorecard
    parcel: Rows = field(default_factory=list)
    parcel_note: Optional[str] = None
    # What the rent buys: rent against the area, the owner, the electric utility. Unrated
    renting: Rows = field(default_factory=list)
    # What the Zillow listing says: description, highlights, rental terms. Unrated
    description: Optional[str] = None
    highlights: List[str] = field(default_factory=list)
    listing: Rows = field(default_factory=list)

    def scorecard(self) -> Dict[str, Any]:
        """
        Counts of rated data points by level, and the labels of the poor ones.

        Only the property's own data points count. Drive times and nearby places are rated
        too, but they depend on which places you've added, so a far-off favorite (a theme
        park, an outlet mall) would otherwise outweigh a flood zone.
        """
        rated = [
            *self.surroundings,
            *self.hazards,
            *([self.internet_summary] if self.internet_summary else []),
        ]
        counts = {level: sum(1 for r in rated if r.level == level) for level in ratings.LEVELS}
        return {
            "counts": counts,
            "total": sum(counts.values()),
            "poor": [r.label for r in rated if r.level == ratings.POOR],
        }


def build_view(
    enrichment: Dict[str, Dict[str, Any]],
    walk_scores: Optional[Dict[str, Any]] = None,
    listing: Optional[Dict[str, Any]] = None,
) -> PropertyView:
    """
    Build the detail-page view from {provider name: data}.

    Args:
        walk_scores: Scores fetched for this page view (app.services.walk_score); they
            aren't part of the stored enrichment
        listing: The property's row: its "price" (monthly rent) and "beds", to set
            against the area's rents, and its "listing_json" from Zillow
    """
    view = PropertyView()
    details = parse_listing_details((listing or {}).get("listing_json"))
    view.description = details.description
    view.highlights = details.highlights
    view.listing = listing_rows(details)
    data = lambda name: enrichment.get(name) or {}  # noqa: E731

    walk = walk_scores or {}

    highway = data("highway_provider")
    rail = data("railroad_provider")
    airports = data("airport_provider").get("airports")
    view.noise = noise_estimate(highway, rail, airports)
    nearest_airport = airports[0] if airports else None
    local_noise = data("local_noise_sources_provider")
    flood = data("flood_zone_provider")
    air = data("air_quality_provider")
    odors = data("odor_sources_provider")
    beach = (data("beach_parking_provider").get("sites") or [None])[0]
    malls = data("malls_provider")
    healthy_mall = (malls.get("healthy") or [None])[0]
    food = data("food_drink_provider")
    roads = data("road_traffic_provider")
    crowds = data("event_traffic_provider")
    view.surroundings = _rows(
        (
            "Walk score",
            _score_text(walk.get("walk_score"), walk.get("description")),
            ratings.walk_score(walk.get("walk_score")),
        ),
        (
            "Bike score",
            _score_text(walk.get("bike_score"), walk.get("bike_description")),
            ratings.bike_score(walk.get("bike_score")),
        ),
        (
            "Transit score",
            _score_text(walk.get("transit_score"), walk.get("transit_description")),
            ratings.transit_score(walk.get("transit_score")),
        ),
        ("Noise", noise_text(view.noise), ratings.noise_level(view.noise)),
        ("Noise by source", noise_sources_text(view.noise)),
        ("Fireworks", fireworks_text(local_noise), ratings.fireworks(local_noise)),
        ("Rocket launches", launch_text(local_noise), ratings.launches(local_noise)),
        ("Flood zone", flood_zone_text(flood), ratings.flood_zone(flood)),
        (
            "Nearest highway",
            _with_name(
                _miles_text(highway.get("highway_distance_m")), highway.get("nearest_highway_name")
            ),
            ratings.highway(highway.get("highway_distance_m")),
        ),
        (
            "Nearest railroad",
            _miles_text(rail.get("railroad_distance_m")),
            ratings.railroad(rail.get("railroad_distance_m")),
        ),
        (
            "Nearest airport",
            _with_name(
                _miles_text(nearest_airport["distance_m"]),
                f"{nearest_airport['code']}, {nearest_airport['name']}",
            )
            if nearest_airport
            else None,
        ),
        ("Air quality", air_quality_text(air), ratings.air_quality(air)),
        ("Odor sources", odor_sources_text(odors), ratings.odor_sources(odors)),
        ("Road traffic", road_traffic_text(roads), ratings.road_traffic(roads)),
        (
            "Tourist traffic",
            _nearby_names_text(crowds.get("attractions")),
            ratings.attractions(crowds),
        ),
        ("Event venues", _nearby_names_text(crowds.get("venues")), ratings.venues(crowds)),
        ("Food & drink", food_drink_text(food), ratings.food_drink(food)),
        (
            "Nearest beach parking",
            beach_parking_text(beach),
            ratings.beach_minutes(beach.get("drive_minutes")) if beach else None,
        ),
        (
            "Nearest healthy mall",
            healthy_mall_text(healthy_mall),
            ratings.mall_minutes(healthy_mall.get("drive_minutes")) if healthy_mall else None,
        ),
        ("Dying malls nearby", dying_malls_text(malls), ratings.dying_malls(malls)),
    )

    view.drive_times = drive_times(data("distance_provider"))
    view.nearby_places = [
        {
            "name": p.get("name"),
            "type": p.get("type"),
            "address": p.get("address"),
            "minutes": p.get("drive_minutes"),
            "miles": p.get("drive_miles"),
            "level": ratings.nearby_minutes(p.get("drive_minutes")),
        }
        for p in data("places_nearby_provider").get("places_nearby", [])
        if p.get("name")
    ]

    sinkholes = data("sinkhole_provider")
    elevation = data("elevation_provider")
    evacuation = data("evacuation_zone_provider")
    wetlands = data("wetlands_provider")
    contamination = data("contamination_provider")
    waters = data("impaired_waters_provider")
    view.hazards = _rows(
        ("Sinkhole geology", sinkhole_text(sinkholes), ratings.sinkhole_geology(sinkholes)),
        (
            "Sinkhole reports",
            sinkhole_reports_text(sinkholes),
            ratings.sinkhole_reports(sinkholes),
        ),
        ("Elevation", elevation_text(elevation), ratings.elevation(elevation)),
        (
            "Evacuation zone",
            evacuation_zone_text(evacuation),
            ratings.evacuation_zone(evacuation),
        ),
        ("Wetlands", wetlands_text(wetlands), ratings.wetlands(wetlands)),
        (
            "Contamination sites",
            contamination_text(contamination),
            ratings.contamination(contamination),
        ),
        ("Impaired waters", impaired_waters_text(waters), ratings.impaired_waters(waters)),
    )

    broadband = data("broadband_provider")
    view.internet = internet_providers(broadband)
    summary = internet_summary_text(broadband)
    if summary:
        view.internet_summary = Row("Internet", summary, ratings.internet(broadband, view.internet))

    view.parcel, view.parcel_note = parcel_section(data("parcel_provider"))

    census = data("census_provider")
    view.renting = _rows(
        ("Rent vs area", rent_text(listing or {}, census)),
        ("Owner", owner_text(data("parcel_provider"))),
        ("Electricity", electricity_text(data("electric_utility_provider"))),
    )
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


def odor_sources_text(data: Dict[str, Any]) -> Optional[str]:
    """E.g. "Iron Bridge WRF (wastewater treatment plant) 0.4 mi · +1 more"."""
    if "sources" not in data:
        return None
    sources = data["sources"]
    if not sources:
        return "None in range"
    shown = [
        f"{s.get('name') or 'Unnamed'} ({s['type']}) {_feet_or_miles(s['distance_m'])}"
        for s in sources[:3]
    ]
    more = (data.get("source_count") or len(sources)) - len(shown)
    return " · ".join(shown + ([f"+{more} more"] if more > 0 else []))


def beach_parking_text(site: Optional[Dict[str, Any]]) -> Optional[str]:
    """E.g. "58 min · 52.3 mi (Lori Wilson Park, Cocoa Beach · Atlantic · 1.50/hr)"."""
    if not site or site.get("drive_minutes") is None:
        return None
    hours, minutes = divmod(int(site["drive_minutes"]), 60)
    drive = f"{hours} hr {minutes} min" if hours else f"{minutes} min"
    if site.get("drive_miles") is not None:
        drive += f" · {float(site['drive_miles']):.1f} mi"
    place = ", ".join(dict.fromkeys(p for p in (site.get("name"), site.get("beach")) if p))
    # The fee is the posted rate ("1.50/hr") or just "yes"
    fee = site.get("fee") and ("paid parking" if site["fee"] == "yes" else f"parking {site['fee']}")
    return f"{drive} ({' · '.join(p for p in (place, site.get('coast'), fee) if p)})"


def healthy_mall_text(mall: Optional[Dict[str, Any]]) -> Optional[str]:
    """E.g. "14 min · 8.2 mi (Altamonte Mall, Altamonte Springs · healthy)"."""
    if not mall or mall.get("drive_minutes") is None:
        return None
    hours, minutes = divmod(int(mall["drive_minutes"]), 60)
    drive = f"{hours} hr {minutes} min" if hours else f"{minutes} min"
    if mall.get("drive_miles") is not None:
        drive += f" · {float(mall['drive_miles']):.1f} mi"
    place = ", ".join(p for p in (mall.get("name"), mall.get("city")) if p)
    return f"{drive} ({' · '.join(p for p in (place, mall.get('status')) if p)})"


def dying_malls_text(data: Dict[str, Any]) -> Optional[str]:
    """E.g. "Volusia Mall 0.8 mi (dead: Sears gone ...)"; None if none in range."""
    declining = data.get("declining") or []
    if not declining:
        return None
    return " · ".join(
        f"{m['name']} {_miles(m['straight_line_m'])} "
        f"({m['status']}{': ' + m['note'] if m.get('note') else ''})"
        for m in declining
    )


def food_drink_text(data: Dict[str, Any]) -> Optional[str]:
    """E.g. "6 within a 10-min walk · 20 within 0.9 mi (nearest Prato, 400 ft)"."""
    if "places" not in data:
        return None
    places = data["places"]
    radius = _miles(data.get("radius_m") or 0)
    if not places:
        return f"None within {radius}"
    walkable = data.get("walkable_count") or 0
    nearest = places[0]
    closest = f"nearest {nearest.get('name') or 'unnamed'}, {_feet_or_miles(nearest['distance_m'])}"
    # With all 20 returned there are more beyond the last, so its distance is the measure
    reach = _feet_or_miles(places[-1]["distance_m"]) if data.get("capped") else radius
    if walkable == len(places) and data.get("capped"):
        return (
            f"{walkable}+ within a 10-min walk · the closest {walkable} within {reach} ({closest})"
        )
    return f"{walkable or 'None'} within a 10-min walk · {len(places)} within {reach} ({closest})"


def road_traffic_text(data: Dict[str, Any]) -> Optional[str]:
    """E.g. "On a counted road: 24,500 vehicles a day (Fairbanks Ave to Park Ave)"."""
    if "roads" not in data:
        return None
    if not data["roads"]:
        return "No counted road within 650 ft (a local street)"
    fronting = [r for r in data["roads"] if r["distance_m"] <= ratings.FRONTING_ROAD_M]
    road = max(fronting, key=lambda r: r["vehicles_per_day"]) if fronting else data["roads"][0]
    between = " to ".join(s for s in (road.get("from_street"), road.get("to_street")) if s)
    count = f"{road['vehicles_per_day']:,} vehicles a day" + (f" ({between})" if between else "")
    if fronting:
        return f"On a counted road: {count}"
    return f"Nearest counted road {_feet_or_miles(road['distance_m'])} away: {count}"


def _nearby_names_text(places: Optional[List[Dict[str, Any]]]) -> Optional[str]:
    """E.g. "Kia Center 0.8 mi, Camping World Stadium 1.9 mi"; None if none in range."""
    return ", ".join(f"{p['name']} {_miles(p['distance_m'])}" for p in (places or [])[:3]) or None


def listing_rows(details: ListingDetails) -> Rows:
    """The listing's terms and facts, Zillow's at-a-glance summary first."""
    glance = dict(details.at_a_glance)
    # The hero already shows the type, and the fees row is more specific than Zillow's total
    glance.pop("Type", None)
    if details.fees:
        glance.pop("Deposit & fees", None)
    listed = [details.listed_by, details.contact_phone]
    return _rows(
        ("Status", details.status if details.status != "For rent" else None),
        *glance.items(),
        ("Lease", details.lease_term),
        ("Fees", " · ".join(f"{name} {fee}" for name, fee in details.fees) or None),
        ("Appliances", ", ".join(details.appliances) or None),
        ("Flooring", ", ".join(details.flooring) or None),
        (
            "Rent Zestimate",
            _money(details.rent_zestimate) and f"{_money(details.rent_zestimate)}/mo",
        ),
        ("Zestimate", _money(details.zestimate)),
        ("On Zillow", _days(details.days_on_zillow)),
        ("Listed by", " · ".join(p for p in listed if p) or None),
    )


def _days(days: Optional[int]) -> Optional[str]:
    if days is None:
        return None
    return "Listed today" if days == 0 else f"{days} day{'s' if days != 1 else ''}"


# Above this a listing's price is a sale price, not a month's rent
MAX_MONTHLY_RENT = 20_000


def rent_text(listing: Dict[str, Any], census: Dict[str, Any]) -> Optional[str]:
    """E.g. "$2,400 asking · 30% above the tract's 3-bedroom median of $1,850 (...)"."""
    tract = census.get("tract") or {}
    by_bedrooms = tract.get("median_gross_rent_by_bedrooms") or {}
    beds = listing.get("beds")
    size = str(min(int(beds), 5)) if beds is not None else None
    if size in by_bedrooms:
        median = by_bedrooms[size]
        kind = "studio" if size == "0" else f"{size}{'+' if size == '5' else ''}-bedroom"
    else:
        median, kind = tract.get("median_gross_rent"), None
    if not median:
        return None

    year = census.get("acs_year")
    source = (f"ACS {year - 4}–{year}, " if year else "") + "rent plus utilities"
    what = f"the tract's {kind + ' ' if kind else ''}median of {_money(median)} ({source})"
    price = listing.get("price")
    if not price or price > MAX_MONTHLY_RENT:
        return f"Tract {kind + ' ' if kind else ''}median {_money(median)} ({source})"
    difference = round(100 * (price - median) / median)
    if difference == 0:
        return f"{_money(price)} asking · level with {what}"
    return f"{_money(price)} asking · {abs(difference)}% {'above' if difference > 0 else 'below'} {what}"


def owner_text(data: Dict[str, Any]) -> Optional[str]:
    """E.g. "Progress Residential Borrower 12 LLC · company · tax bill to Scottsdale, AZ"."""
    name = data.get("owner_name")
    if not data.get("found") or not name:
        return None
    parts = [_title_name(name), data.get("owner_type")]
    if data.get("homestead"):
        parts.append("homesteaded (the owner's own home)")
    elif data.get("owner_city") or data.get("owner_state"):
        parts.append("tax bill to " + ", ".join(
            p for p in (data.get("owner_city"), data.get("owner_state")) if p
        ))  # fmt: skip
    bought = next(
        (s for s in data.get("recent_sales") or [] if s.get("arms_length") and s.get("year")),
        None,
    )
    if bought:
        month = MONTHS[bought["month"] - 1] + " " if bought.get("month") else ""
        parts.append(f"bought {month}{bought['year']}")
    return " · ".join(p for p in parts if p)


def electricity_text(data: Dict[str, Any]) -> Optional[str]:
    """E.g. "Orlando Utilities Comm (municipal) · 13.2¢/kWh average residential, 2025"."""
    utilities = data.get("utilities") or []
    if not utilities:
        return None

    def rate(utility: Dict[str, Any]) -> Optional[str]:
        cents = utility.get("residential_cents_per_kwh")
        return f"{cents:.1f}¢/kWh" if cents else None

    first = utilities[0]
    text = _title_name(first.get("name") or "Unknown utility")
    if first.get("type"):
        text += f" ({first['type']})"
    if rate(first):
        year = f", {first['rate_year']}" if first.get("rate_year") else ""
        text += f" · {rate(first)} average residential{year}"
    others = [
        _title_name(u["name"]) + (f" ({rate(u)})" if rate(u) else "")
        for u in utilities[1:]
        if u.get("name")
    ]
    return text + (f" · or {', '.join(others)}" if others else "")


KEEP_UPPER = {"LLC", "LLP", "LP", "INC", "II", "III", "IV", "USA", "FL", "REIT"}
KEEP_LOWER = {"OF", "AND", "THE", "AT"}


def _title_name(name: str) -> str:
    """Tax roll and utility names come in capitals: "WP1 HOMES LLC" -> "WP1 Homes LLC"."""
    words = [
        w if w.strip(",.") in KEEP_UPPER or any(c.isdigit() for c in w)
        else w.lower() if w in KEEP_LOWER and i
        else w.title()
        for i, w in enumerate(name.split())
    ]  # fmt: skip
    return " ".join(words)


def fireworks_text(data: Dict[str, Any]) -> Optional[str]:
    """E.g. "EPCOT 3.6 mi, Disney's Hollywood Studios 4.2 mi"; None if none within range."""
    venues = data.get("fireworks") or []
    return ", ".join(f"{v['name']} {_miles(v['distance_m'])}" for v in venues[:3]) or None


def launch_text(data: Dict[str, Any]) -> Optional[str]:
    site = data.get("launch_site")
    if not site:
        return None
    miles = float(site["distance_m"]) / METERS_PER_MILE
    # Booster landing sonic booms rattle windows across Brevard; launches are heard further
    effect = "sonic booms likely" if miles <= 30 else "launches audible"
    return f"{miles:.0f} mi from the Cape · {effect}"


def sinkhole_text(data: Dict[str, Any]) -> Optional[str]:
    """E.g. "Most favorable to sinkhole formation"."""
    favorability = data.get("favorability")
    return f"{favorability} to sinkhole formation" if favorability else None


def sinkhole_reports_text(data: Dict[str, Any]) -> Optional[str]:
    """E.g. "3 within 1 mi (1 verified) · nearest 0.30 mi, 2008" or "None within 1 mi"."""
    count = data.get("incidents_within_1mi")
    if count is None:
        return None
    if count == 0:
        return "None within 1 mi"
    text = f"{count} within 1 mi"
    if data.get("verified_within_1mi"):
        text += f" ({data['verified_within_1mi']} verified)"
    if data.get("nearest_incident_m") is not None:
        text += f" · nearest {_miles(data['nearest_incident_m'])}"
        if data.get("nearest_incident_year"):
            text += f", {data['nearest_incident_year']}"
    return text


def elevation_text(data: Dict[str, Any]) -> Optional[str]:
    """E.g. "82 ft · 3.5 ft below surrounding ground"."""
    elevation = data.get("elevation_ft")
    if elevation is None:
        return None
    text = f"{elevation:.0f} ft"
    relative = data.get("relative_ft")
    if relative is not None:
        if abs(relative) < 1:
            text += " · level with surroundings"
        else:
            side = "below" if relative < 0 else "above"
            text += f" · {abs(relative):.1f} ft {side} surrounding ground"
    return text


def evacuation_zone_text(data: Dict[str, Any]) -> Optional[str]:
    if "evacuation_zone" not in data:
        return None
    zone = data["evacuation_zone"]
    if not zone:
        return "None"
    return f"Zone {zone}" + (" (evacuates first)" if zone == "A" else "")


def wetlands_text(data: Dict[str, Any]) -> Optional[str]:
    """E.g. "Freshwater Forested/Shrub Wetland 140 ft away"."""
    if "in_wetland" not in data:
        return None
    if data["in_wetland"]:
        return f"On a mapped wetland ({data.get('nearest_wetland_type')})"
    if data.get("nearest_wetland_m") is None:
        return "None within 500 m"
    return f"{data['nearest_wetland_type']} {_feet_or_miles(data['nearest_wetland_m'])} away"


def contamination_text(data: Dict[str, Any]) -> Optional[str]:
    """E.g. "2 within ½ mi · nearest Fera Cleaners (dry cleaner), 640 ft"."""
    count = data.get("sites_within_half_mi")
    if count is None:
        return None
    if count == 0:
        return "None within ½ mi"
    sites = data.get("sites") or []
    text = f"{count} open within ½ mi"
    if sites:
        nearest = sites[0]
        text += (
            f" · nearest {nearest.get('name') or 'unnamed'} ({nearest.get('category')}), "
            f"{_feet_or_miles(nearest['distance_m'])}"
        )
    if data.get("superfund_within_half_mi"):
        text += " · includes Superfund"
    return text


def impaired_waters_text(data: Dict[str, Any]) -> Optional[str]:
    """E.g. "Lake Eola (nutrients)"."""
    if "impaired_waters" not in data:
        return None
    waters = data["impaired_waters"]
    if not waters:
        return "None nearby"

    def issues(parameters: List[str]) -> str:
        # "Nutrients (Chlorophyll-a)" and "Nutrients (Total Phosphorus)" -> "nutrients"
        names = []
        for p in parameters:
            name = re.sub(r"\s*\(.*\)", "", p).strip().lower()
            if name and name not in names:
                names.append(name)
        return ", ".join(names)

    return "; ".join(f"{w['name']} ({issues(w.get('parameters') or [])})" for w in waters[:3])


def internet_summary_text(data: Dict[str, Any]) -> Optional[str]:
    """E.g. "Fiber available · 3 wired providers · up to 8,000 Mbps"."""
    if "providers" not in data:
        return None
    if not data["providers"]:
        return "No wired or fixed wireless providers listed"
    # Describe the providers that are listed, not ones reaching a sliver of the block
    shown = internet_providers(data)
    if not shown:
        return "No provider serves most of this block"
    wired = len({p["name"] for p in shown if p.get("technology") in WIRED_TECHNOLOGIES})
    parts = [
        "Fiber available" if any(p.get("technology") == "Fiber" for p in shown) else "No fiber",
        f"{wired} wired provider{'' if wired == 1 else 's'}",
        f"up to {max(p['max_down_mbps'] for p in shown):,.0f} Mbps",
    ]
    return " · ".join(parts)


WIRED_TECHNOLOGIES = {"Fiber", "Cable", "DSL"}


def internet_providers(data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Providers covering at least a quarter of the block, fastest first."""
    return [
        p
        for p in data.get("providers") or []
        if p.get("coverage_pct") is None or p["coverage_pct"] >= 25
    ]


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
                level=ratings.drive_minutes(minutes),
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
        ("Tract homes rented", _unit(tract.get("renter_pct"), "%")),
        (
            "Tract households without children",
            _unit(tract.get("households_without_children_pct"), "%"),
        ),
        ("Tract median household income", _money(tract.get("median_household_income"))),
        ("Tract median rent", _money(tract.get("median_gross_rent"))),
    )

    # Race & ethnicity: largest first, and leave out groups with nobody in them
    race = sorted((tract.get("race_ethnicity") or {}).items(), key=lambda kv: -kv[1])
    distributions = [
        Distribution("Age", list((tract.get("age_groups") or {}).items())),
        Distribution("Race & ethnicity", [(k, v) for k, v in race if v > 0]),
        Distribution("Education (25+)", list((tract.get("education") or {}).items())),
    ]
    return rows, [d for d in distributions if d.items]


MONTHS = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()


def parcel_section(data: Dict[str, Any]) -> Tuple[Rows, Optional[str]]:
    """The appraiser's record as rows, and a note when it may be the wrong parcel."""
    if not data.get("found"):
        return [], None

    year, effective = data.get("year_built"), data.get("effective_year_built")
    built = str(year) if year else None
    if built and effective and effective != year:
        built += f" (effective {effective}, after updates)"

    lot_text = None
    if data.get("lot_acres"):
        lot_text = f"{data['lot_acres']:g} ac ({data['lot_sqft']:,} sqft)"

    value = _money(data.get("just_value"))
    if value and data.get("land_value"):
        value += f" (land {_money(data['land_value'])})"

    units = data.get("residential_units")
    rows = _rows(
        ("Use", data.get("use")),
        ("Year built", built),
        (
            "Living area",
            f"{data['living_area_sqft']:,} sqft" if data.get("living_area_sqft") else None,
        ),
        ("Lot", lot_text),
        ("Units", f"{units} residential units" if units and units > 1 else None),
        ("Construction quality", data.get("quality")),
        ("Just (market) value", value),
        ("Taxable value", _money(data.get("taxable_value"))),
        ("Homestead", "Yes, owner-occupied" if data.get("homestead") else "No"),
        ("Recent sales", "; ".join(sale_text(s) for s in data.get("recent_sales") or []) or None),
        (
            "Parcel",
            _join(
                f"{data['county']} County" if data.get("county") else None,
                data.get("parcel_id"),
                f"{data['assessment_year']} roll" if data.get("assessment_year") else None,
            ),
        ),
    )

    note = None
    if data.get("match") == "nearest":
        address = data.get("situs_address")
        note = "No parcel matched this address, so this is the parcel nearest the map pin" + (
            f" ({address})." if address else "."
        )
    return rows, note


def sale_text(sale: Dict[str, Any]) -> str:
    """E.g. "Mar 2025 · $410,000" or "Nov 2025 · $100 (not arm's length)"."""
    month = sale.get("month")
    when = (
        f"{MONTHS[month - 1]} {sale['year']}" if month and 1 <= month <= 12 else str(sale["year"])
    )
    text = f"{when} · {_money(sale.get('price')) or 'price not recorded'}"
    if not sale.get("arms_length"):
        text += " (not arm's length)"
    elif sale.get("vacant_land"):
        text += " (land only)"
    return text


def _money(value: Any) -> Optional[str]:
    return f"${int(value):,}" if value else None


def _rows(*items: Tuple[Any, ...]) -> Rows:
    """Rows from (label, value) or (label, value, level), skipping empty values."""
    return [
        Row(item[0], str(item[1]), item[2] if len(item) > 2 else None)
        for item in items
        if item[1] is not None and item[1] != ""
    ]


def _miles_text(meters: Any) -> Optional[str]:
    return f"{float(meters) / METERS_PER_MILE:.2f} mi" if meters is not None else None


def _miles(meters: Any) -> str:
    return f"{float(meters) / METERS_PER_MILE:.1f} mi"


def _feet_or_miles(meters: Any) -> str:
    """Feet under a quarter mile ("640 ft"), miles past it ("0.4 mi")."""
    meters = float(meters)
    if meters < METERS_PER_MILE / 4:
        return f"{meters * 3.28084:,.0f} ft"
    return f"{meters / METERS_PER_MILE:.1f} mi"


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
