"""Map listing facts and enrichment results onto Baserow Properties fields.

Only fields with data are returned, so a provider that fails on a re-enrich leaves the
row's previous value in place instead of blanking it.
"""

from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from app.integrations.baserow_schema import PropertyFields as F
from app.services.zillow_listing import ListingFacts

METERS_PER_MILE = 1609.344


def listing_fields(facts: ListingFacts) -> Dict[str, Any]:
    """Baserow fields for the listing facts parsed from the page."""
    return _without_none(
        {
            F.PRICE: facts.price,
            F.BEDS: facts.beds,
            F.BATHS: facts.baths,
            F.SQFT: facts.sqft,
            F.LOT_ACRES: facts.lot_acres,
            F.YEAR_BUILT: facts.year_built,
            F.PROPERTY_TYPE: facts.property_type,
        }
    )


def enrichment_fields(
    enrichment_data: Dict[str, Dict[str, Any]],
    latitude: float,
    longitude: float,
    enriched_at: datetime,
) -> Dict[str, Any]:
    """
    Baserow fields for an enrichment run.

    Args:
        enrichment_data: The "enrichment_data" dict from EnrichmentOrchestrator, keyed by
            provider name, each with "data" and "success"
        latitude: Geocoded latitude
        longitude: Geocoded longitude
        enriched_at: Timestamp to record as "Last enriched"
    """
    fields: Dict[str, Any] = {
        F.LATITUDE: round(latitude, 6),
        F.LONGITUDE: round(longitude, 6),
        F.LAST_ENRICHED: enriched_at.isoformat(),
    }
    for provider_name, mapper in _PROVIDER_MAPPERS.items():
        result = enrichment_data.get(provider_name) or {}
        if result.get("success") and result.get("data"):
            fields.update(_without_none(mapper(result["data"])))
    return fields


def _walk_score(data: Dict[str, Any]) -> Dict[str, Any]:
    return {
        F.WALK_SCORE: data.get("walk_score"),
        F.BIKE_SCORE: data.get("bike_score"),
        F.TRANSIT_SCORE: data.get("transit_score"),
    }


def _flood_zone(data: Dict[str, Any]) -> Dict[str, Any]:
    zone, risk = data.get("flood_zone"), data.get("flood_risk")
    if not zone:
        return {}
    return {F.FLOOD_ZONE: f"{zone} ({risk})" if risk else zone}


def _railroad(data: Dict[str, Any]) -> Dict[str, Any]:
    return {F.RAIL_DISTANCE_MI: _miles(data.get("railroad_distance_m"))}


def _highway(data: Dict[str, Any]) -> Dict[str, Any]:
    return {
        F.HIGHWAY_DISTANCE_MI: _miles(data.get("highway_distance_m")),
        F.ROAD_NOISE: data.get("road_noise_category"),
    }


def _climate(data: Dict[str, Any]) -> Dict[str, Any]:
    return {
        F.AVG_TEMP: _rounded(data.get("annual_average_temperature"), 1),
        F.AVG_PRECIP: _rounded(data.get("annual_average_precipitation"), 1),
    }


def _air_quality(data: Dict[str, Any]) -> Dict[str, Any]:
    aqi = data.get("aqi")
    category = data.get("category")
    parts = []
    if aqi is not None:
        parts.append(f"AQI {aqi}")
    if category:
        parts.append(str(category))
    return {F.AIR_QUALITY: " ".join(parts) or None}


def _drive_times(data: Dict[str, Any]) -> Dict[str, Any]:
    lines: List[str] = []
    for d in data.get("distances", []):
        name = d.get("location_name") or "Unknown"
        if d.get("status") == "OK":
            minutes = d.get("duration_in_traffic_minutes") or d.get("duration_minutes")
            lines.append(f"{name}: {_fmt(minutes)} min ({_fmt(d.get('distance_miles'), 1)} mi)")
        else:
            lines.append(f"{name}: unavailable")
    return {F.DRIVE_TIMES: "\n".join(lines) or None}


def _nearby_places(data: Dict[str, Any]) -> Dict[str, Any]:
    lines = [
        f"{p.get('name')} ({p.get('type')})" if p.get("type") else str(p.get("name"))
        for p in data.get("places_nearby", [])
        if p.get("name")
    ]
    return {F.NEARBY_PLACES: "\n".join(lines) or None}


_PROVIDER_MAPPERS: Dict[str, Callable[[Dict[str, Any]], Dict[str, Any]]] = {
    "walk_score_provider": _walk_score,
    "flood_zone_provider": _flood_zone,
    "railroad_provider": _railroad,
    "highway_provider": _highway,
    "annual_average_climate_provider": _climate,
    "air_quality_provider": _air_quality,
    "distance_provider": _drive_times,
    "places_nearby_provider": _nearby_places,
}


def _miles(meters: Any) -> Optional[float]:
    return round(float(meters) / METERS_PER_MILE, 2) if meters is not None else None


def _rounded(value: Any, places: int) -> Optional[float]:
    return round(float(value), places) if value is not None else None


def _fmt(value: Any, places: int = 0) -> str:
    if value is None:
        return "?"
    return f"{float(value):.{places}f}"


def _without_none(values: Dict[str, Any]) -> Dict[str, Any]:
    return {k: v for k, v in values.items() if v is not None}
