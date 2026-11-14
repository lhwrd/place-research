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
        "flood_zone_provider": _ok(
            {
                "flood_zone": "AE",
                "flood_risk": None,
                "in_sfha": True,
                "base_flood_elevation_ft": 7.0,
            }
        ),
        "railroad_provider": _ok({"railroad_distance_m": 1609.344}),
        "highway_provider": _ok({"highway_distance_m": 3218.688, "road_noise_category": "Quiet"}),
        "annual_average_climate_provider": _ok(
            {"annual_average_temperature": 72.34, "annual_average_precipitation": 51.06}
        ),
        "air_quality_provider": _ok({"aqi": 31, "category": "Good", "pm2_5": 5.0, "ozone": 40.0}),
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
        F.FLOOD_ZONE: "AE (high-risk SFHA, BFE 7 ft)",
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


def test_census_fields():
    data = {
        "acs_year": 2024,
        "state": "Colorado",
        "city": {
            "name": "Highlands Ranch",
            "type": "CDP",
            "geoid": "0836410",
            "population": 103000,
        },  # fmt: skip
        "county": {"name": "Douglas County", "geoid": "08035", "population": 380000},
        "tract": {
            "name": "Census Tract 141.33",
            "geoid": "08035014133",
            "population": 4210,
            "median_age": 38.2,
            "age_groups": {"Under 18": 25.1, "18-24": 20.0, "65+": 12.3},
            "race_ethnicity": {
                "White": 78.0,
                "Black": 0.0,
                "Asian": 6.5,
                "Hispanic or Latino": 10.4,
            },  # fmt: skip
            "education": {"High school / GED": 12.0, "Bachelor's": 40.0},
            "bachelors_or_higher_pct": 62.5,
        },
    }

    fields = enrichment_fields({"census_provider": _ok(data)}, 1.0, 2.0, NOW)

    assert fields[F.CITY] == "Highlands Ranch (CDP)"
    assert fields[F.CITY_POPULATION] == 103000
    assert fields[F.COUNTY] == "Douglas County, Colorado"
    assert fields[F.COUNTY_POPULATION] == 380000
    assert fields[F.CENSUS_TRACT] == "08035014133"
    assert fields[F.TRACT_POPULATION] == 4210
    assert fields[F.TRACT_MEDIAN_AGE] == 38.2
    assert fields[F.TRACT_BACHELORS_PCT] == 62.5
    assert fields[F.TRACT_AGE_GROUPS] == "Under 18: 25.1%\n18-24: 20%\n65+: 12.3%"
    # Largest first, empty groups dropped
    assert fields[F.TRACT_RACE_ETHNICITY] == "White: 78%\nHispanic or Latino: 10.4%\nAsian: 6.5%"
    assert fields[F.TRACT_EDUCATION] == "High school / GED: 12%\nBachelor's: 40%"


def test_census_fields_outside_any_city():
    data = {"state": "Colorado", "city": None,
            "county": {"name": "Boulder County", "population": 330000}, "tract": {}}  # fmt: skip

    fields = enrichment_fields({"census_provider": _ok(data)}, 1.0, 2.0, NOW)

    assert F.CITY not in fields
    assert fields[F.COUNTY_POPULATION] == 330000


def test_air_quality_without_aqi():
    fields = enrichment_fields(
        {"air_quality_provider": _ok({"category": "Moderate"})}, 1.0, 2.0, NOW
    )
    assert fields[F.AIR_QUALITY] == "Moderate"


def test_flood_zone_text():
    def text(**data):
        return enrichment_fields({"flood_zone_provider": _ok(data)}, 1.0, 2.0, NOW)[F.FLOOD_ZONE]

    assert text(flood_zone="X", flood_risk="0.2 PCT ANNUAL CHANCE FLOOD HAZARD", in_sfha=False) == (
        "X (0.2% annual chance flood hazard)"
    )
    assert text(flood_zone="VE", in_sfha=True, base_flood_elevation_ft=12.5) == (
        "VE (high-risk SFHA, BFE 12.5 ft)"
    )
    assert text(flood_zone="Not mapped", in_sfha=None) == "Not mapped"
