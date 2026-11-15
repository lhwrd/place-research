"""Rough noise-pollution model: road, rail and aircraft noise from distance alone.

Each source starts at a typical level (dB(A)) at a reference distance and fades with
distance, down to a quiet-suburb ambient floor:

- Road traffic is steady, so it's rated by its average level.
- Trains are intermittent but loud, so rail is rated by a train passing (its peak level):
  that's what you hear from inside and what wakes you up, and averaging it over the day
  hides it.
- Roads and railways are long lines of sound, which fade more slowly than a single point:
  about 5 dB per doubling of distance once ground and air absorption are included
  (an ideal line loses 3 dB, a point 6 dB). Airports are treated as points.

Sources are combined the way sound actually adds (energy sum), so two 60 dB sources make
63 dB, not 120. Real exposure also depends on traffic volume, train schedules and horns,
flight paths, terrain and barriers, so treat the result as a comparison between homes,
not a measurement.

Tune the levels here; the UI computes the combined figure from stored distances at
display time, so changes apply without re-enriching.
"""

import math
from dataclasses import dataclass
from typing import Dict, Iterable, Optional, Tuple

AMBIENT_DB = 35.0
LINE_SOURCE_DB_PER_DOUBLING = 5.0  # roads and railways
POINT_SOURCE_DB_PER_DOUBLING = 6.0  # airports

# Source -> (level in dB at the reference distance, reference distance in meters,
#            dB lost per doubling of distance)
ROAD_LEVELS = {
    # Average traffic noise
    "motorway": (75.0, 30.0, LINE_SOURCE_DB_PER_DOUBLING),  # interstates, limited access
    "primary": (65.0, 30.0, LINE_SOURCE_DB_PER_DOUBLING),  # US, state and county highways
}
RAIL_LEVELS = {
    # A train passing (peak level), not the daily average
    "mainline": (85.0, 30.0, LINE_SOURCE_DB_PER_DOUBLING),  # through freight and passenger
    "other": (75.0, 30.0, LINE_SOURCE_DB_PER_DOUBLING),  # spurs, sidings and yards
}
AIRPORT_LEVELS = {
    "large": (75.0, 1000.0, POINT_SOURCE_DB_PER_DOUBLING),  # major commercial airports
    "military": (75.0, 1000.0, POINT_SOURCE_DB_PER_DOUBLING),  # jets, fewer flights
    "regional": (65.0, 1000.0, POINT_SOURCE_DB_PER_DOUBLING),  # scheduled airline service
    "general": (58.0, 1000.0, POINT_SOURCE_DB_PER_DOUBLING),  # business, general aviation
}

CATEGORIES = ((70, "Very High"), (60, "High"), (50, "Moderate"), (40, "Low"))


def level_at(
    level_db: float,
    reference_m: float,
    distance_m: float,
    db_per_doubling: float = POINT_SOURCE_DB_PER_DOUBLING,
) -> float:
    """A source's level at a distance: fades per doubling past the reference, floored."""
    if distance_m > reference_m:
        level_db -= db_per_doubling * math.log2(distance_m / reference_m)
    return max(level_db, AMBIENT_DB)


def source_level(spec: Tuple[float, float, float], distance_m: float) -> float:
    """A source's level at a distance, from its (level, reference distance, dB per doubling)."""
    level_db, reference_m, db_per_doubling = spec
    return level_at(level_db, reference_m, distance_m, db_per_doubling)


def loudest(levels: Dict[str, tuple], distances: Dict[str, Optional[float]]) -> Optional[float]:
    """The loudest of several kinds of the same source, e.g. {"motorway": 900, "primary": 80}."""
    found = [
        source_level(levels[kind], distance)
        for kind, distance in distances.items()
        if distance is not None and kind in levels
    ]
    return round(max(found), 1) if found else None


def combine(levels: Iterable[Optional[float]]) -> Optional[float]:
    """Energy sum of the sources above ambient; ambient if none are; None if no data."""
    known = [level for level in levels if level is not None]
    if not known:
        return None
    audible = [level for level in known if level > AMBIENT_DB]
    if not audible:
        return AMBIENT_DB
    return round(10 * math.log10(sum(10 ** (level / 10) for level in audible)), 1)


def category(db: Optional[float]) -> str:
    if db is None:
        return "Unknown"
    for threshold, name in CATEGORIES:
        if db >= threshold:
            return name
    return "Very Low"


@dataclass
class NoiseEstimate:
    road_db: Optional[float]
    rail_db: Optional[float]
    aircraft_db: Optional[float]

    @property
    def total_db(self) -> Optional[float]:
        return combine([self.road_db, self.rail_db, self.aircraft_db])

    @property
    def category(self) -> str:
        return category(self.total_db)

    @property
    def main_source(self) -> Optional[str]:
        """The loudest source, if it's above ambient."""
        sources = {"road": self.road_db, "rail": self.rail_db, "aircraft": self.aircraft_db}
        name, db = max(
            ((n, d) for n, d in sources.items() if d is not None),
            key=lambda kv: kv[1],
            default=(None, None),
        )
        return name if db is not None and db > AMBIENT_DB else None
