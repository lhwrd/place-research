"""Baserow table schema: field names shared by the sync code and scripts/baserow_setup.py.

Field names are the contract with Baserow. Renaming one here without renaming it in Baserow
(or re-running the setup script) breaks the sync, so treat them like a database migration.
"""

from typing import Any, Dict, List


class Status:
    """Values of the Properties.Status single select."""

    NEW = "New"
    ENRICHING = "Enriching"
    ENRICHED = "Enriched"
    ERROR = "Error"
    RE_ENRICH = "Re-enrich"

    # Rows in these states are picked up by the webhook handler and the sweep
    ACTIONABLE = (NEW, RE_ENRICH)
    ALL = (NEW, ENRICHING, ENRICHED, ERROR, RE_ENRICH)


class PropertyFields:
    """Field names in the Properties table."""

    ADDRESS = "Address"  # primary field
    ZILLOW_URL = "Zillow URL"
    ZILLOW_ID = "Zillow ID"
    STATUS = "Status"
    ERROR = "Error"
    PHOTOS = "Photos"
    LISTING_JSON = "Listing JSON"

    PRICE = "Price"
    BEDS = "Beds"
    BATHS = "Baths"
    SQFT = "Sqft"
    LOT_ACRES = "Lot (acres)"
    YEAR_BUILT = "Year built"
    PROPERTY_TYPE = "Property type"
    LATITUDE = "Latitude"
    LONGITUDE = "Longitude"

    WALK_SCORE = "Walk score"
    BIKE_SCORE = "Bike score"
    TRANSIT_SCORE = "Transit score"
    FLOOD_ZONE = "Flood zone"
    RAIL_DISTANCE_MI = "Rail distance (mi)"
    HIGHWAY_DISTANCE_MI = "Highway distance (mi)"
    ROAD_NOISE = "Road noise"
    AVG_TEMP = "Avg temp"
    AVG_PRECIP = "Avg precip"
    AIR_QUALITY = "Air quality"
    DRIVE_TIMES = "Drive times"
    NEARBY_PLACES = "Nearby places"
    LAST_ENRICHED = "Last enriched"

    # Owned by the user; the backend never writes these
    NOTES = "Notes"
    RATING = "Rating"
    VISITED = "Visited"


class LocationFields:
    """Field names in the Locations table (drive-time destinations)."""

    NAME = "Name"  # primary field
    ADDRESS = "Address"
    TYPE = "Type"
    ACTIVE = "Active"
    PRIORITY = "Priority"


class SettingsFields:
    """Field names in the single-row Settings table."""

    NAME = "Name"  # primary field
    AMENITY_TYPES = "Amenity types"
    PREFERRED_PLACES = "Preferred places"


def _number(name: str, decimals: int = 0) -> Dict[str, Any]:
    return {
        "name": name,
        "type": "number",
        "number_decimal_places": decimals,
        "number_negative": True,
    }


SELECT_COLORS = ["light-blue", "light-orange", "light-green", "light-red", "light-purple"]


def _select(name: str, values: List[str]) -> Dict[str, Any]:
    options = [
        {"value": v, "color": SELECT_COLORS[i % len(SELECT_COLORS)]} for i, v in enumerate(values)
    ]
    return {"name": name, "type": "single_select", "select_options": options}


# Field definitions in Baserow's field-create API format. Primary fields are not listed:
# every table gets one on creation and the setup script renames it.
PROPERTY_FIELD_DEFS: List[Dict[str, Any]] = [
    {"name": PropertyFields.ZILLOW_URL, "type": "url"},
    {"name": PropertyFields.ZILLOW_ID, "type": "text"},
    _select(PropertyFields.STATUS, list(Status.ALL)),
    {"name": PropertyFields.ERROR, "type": "long_text"},
    {"name": PropertyFields.PHOTOS, "type": "file"},
    {"name": PropertyFields.LISTING_JSON, "type": "long_text"},
    _number(PropertyFields.PRICE),
    _number(PropertyFields.BEDS),
    _number(PropertyFields.BATHS, 1),
    _number(PropertyFields.SQFT),
    _number(PropertyFields.LOT_ACRES, 2),
    _number(PropertyFields.YEAR_BUILT),
    {"name": PropertyFields.PROPERTY_TYPE, "type": "text"},
    _number(PropertyFields.LATITUDE, 6),
    _number(PropertyFields.LONGITUDE, 6),
    _number(PropertyFields.WALK_SCORE),
    _number(PropertyFields.BIKE_SCORE),
    _number(PropertyFields.TRANSIT_SCORE),
    {"name": PropertyFields.FLOOD_ZONE, "type": "text"},
    _number(PropertyFields.RAIL_DISTANCE_MI, 2),
    _number(PropertyFields.HIGHWAY_DISTANCE_MI, 2),
    {"name": PropertyFields.ROAD_NOISE, "type": "text"},
    _number(PropertyFields.AVG_TEMP, 1),
    _number(PropertyFields.AVG_PRECIP, 1),
    {"name": PropertyFields.AIR_QUALITY, "type": "text"},
    {"name": PropertyFields.DRIVE_TIMES, "type": "long_text"},
    {"name": PropertyFields.NEARBY_PLACES, "type": "long_text"},
    {
        "name": PropertyFields.LAST_ENRICHED,
        "type": "date",
        "date_include_time": True,
        "date_format": "US",
    },
    {"name": PropertyFields.NOTES, "type": "long_text"},
    {"name": PropertyFields.RATING, "type": "rating", "max_value": 5},
    {"name": PropertyFields.VISITED, "type": "boolean"},
]

LOCATION_FIELD_DEFS: List[Dict[str, Any]] = [
    {"name": LocationFields.ADDRESS, "type": "text"},
    _select(LocationFields.TYPE, ["Family", "Friend", "Work", "Other"]),
    {"name": LocationFields.ACTIVE, "type": "boolean"},
    _number(LocationFields.PRIORITY),
]

SETTINGS_FIELD_DEFS: List[Dict[str, Any]] = [
    {"name": SettingsFields.AMENITY_TYPES, "type": "long_text"},
    {"name": SettingsFields.PREFERRED_PLACES, "type": "long_text"},
]
