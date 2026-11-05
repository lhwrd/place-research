"""Tests for mapping listing facts and enrichment results onto Baserow fields."""

from datetime import datetime, timezone

from app.integrations.baserow_schema import PropertyFields as F
from app.services.baserow_mapper import enrichment_fields, listing_fields
from app.services.zillow_listing import ListingFacts

NOW = datetime(2026, 11, 5, 12, 0, tzinfo=timezone.utc)


def _ok(data):
    return {"success": True, "data": data}


def test_listing_fields_skips_missing_values():
    fields = listing_fields(ListingFacts(price=425000, beds=3, sqft=None))

    assert fields == {F.PRICE: 425000, F.BEDS: 3}


def test_enrichment_fields_maps_every_provider():
    enrichment_data = {
        "walk_score_provider": _ok({"walk_score": 45, "bike_score": 60, "transit_score": None}),
        "flood_zone_provider": _ok({"flood_zone": "AE", "flood_risk": "High"}),
        "railroad_provider": _ok({"railroad_distance_m": 1609.344}),
        "highway_provider": _ok({"highway_distance_m": 3218.688, "road_noise_category": "Quiet"}),
        "annual_average_climate_provider": _ok(
            {"annual_average_temperature": 72.34, "annual_average_precipitation": 51.06}
        ),
        "air_quality_provider": _ok({"AQI": 31, "Category": {"Number": 1, "Name": "Good"}}),
        "distance_provider": _ok(
            {
                "distances": [
                    {
                        "location_name": "Mom",
                        "status": "OK",
                        "duration_minutes": 12,
                        "duration_in_traffic_minutes": 15,
                        "distance_miles": 6.14,
                    },
                    {"location_name": "Work", "status": "ERROR"},
                ]
            }
        ),
        "places_nearby_provider": _ok(
            {
                "places_nearby": [
                    {"name": "Publix", "type": "Grocery store"},
                    {"name": "Riverside Park"},
                    {"type": "No name"},
                ]
            }
        ),
    }

    fields = enrichment_fields(enrichment_data, 29.12345678, -81.0123456, NOW)

    assert fields == {
        F.LATITUDE: 29.123457,
        F.LONGITUDE: -81.012346,
        F.LAST_ENRICHED: NOW.isoformat(),
        F.WALK_SCORE: 45,
        F.BIKE_SCORE: 60,
        F.FLOOD_ZONE: "AE (High)",
        F.RAIL_DISTANCE_MI: 1.0,
        F.HIGHWAY_DISTANCE_MI: 2.0,
        F.ROAD_NOISE: "Quiet",
        F.AVG_TEMP: 72.3,
        F.AVG_PRECIP: 51.1,
        F.AIR_QUALITY: "AQI 31 Good",
        F.DRIVE_TIMES: "Mom: 15 min (6.1 mi)\nWork: unavailable",
        F.NEARBY_PLACES: "Publix (Grocery store)\nRiverside Park",
    }


def test_failed_and_empty_providers_leave_fields_untouched():
    enrichment_data = {
        "walk_score_provider": {"success": False, "data": {"walk_score": 99}},
        "flood_zone_provider": _ok({}),
        "distance_provider": _ok({"distances": []}),
    }

    fields = enrichment_fields(enrichment_data, 1.0, 2.0, NOW)

    assert set(fields) == {F.LATITUDE, F.LONGITUDE, F.LAST_ENRICHED}


def test_air_quality_with_string_category():
    fields = enrichment_fields(
        {"air_quality_provider": _ok({"Category": "Moderate"})}, 1.0, 2.0, NOW
    )
    assert fields[F.AIR_QUALITY] == "Moderate"
