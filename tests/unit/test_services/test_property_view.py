"""Tests for formatting stored provider data for the web UI."""

from app.services.property_view import (
    DriveTime,
    build_view,
    flood_zone_text,
    noise_estimate,
    noise_sources_text,
    noise_text,
)


def test_build_view_formats_every_provider():
    view = build_view(
        {
            "walk_score_provider": {
                "walk_score": 45,
                "description": "Car-Dependent",
                "bike_score": 60,
                "bike_description": "Bikeable",
                "transit_score": None,
                "transit_description": None,
            },
            "flood_zone_provider": {
                "flood_zone": "AE",
                "flood_risk": None,
                "in_sfha": True,
                "base_flood_elevation_ft": 7.0,
            },
            "railroad_provider": {"railroad_distance_m": 1609.344},
            "highway_provider": {
                "highway_distance_m": 3218.688,
                "nearest_highway_name": "I- 95",
                "highway_distances_m": {"motorway": 3219},
                "road_noise_category": "Quiet",
            },
            "airport_provider": {
                "airports": [
                    {
                        "code": "DAB",
                        "name": "Daytona Beach International Airport",
                        "category": "regional",
                        "distance_m": 9069,
                    },
                ]
            },  # fmt: skip
            "air_quality_provider": {"aqi": 31, "category": "Good"},
            "distance_provider": {
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
            },
            "places_nearby_provider": {
                "places_nearby": [
                    {
                        "name": "Publix",
                        "type": "Grocery store",
                        "address": "1 Rd",
                        "drive_minutes": 7,
                        "drive_miles": 2.4,
                    },  # fmt: skip
                    {"name": "Riverside Park"},
                    {"type": "No name"},
                ]
            },
        }
    )

    assert view.surroundings == [
        ("Walk score", "45 · Car-Dependent"),
        ("Bike score", "60 · Bikeable"),
        ("Noise", noise_text(view.noise)),
        # Passing trains a mile away outweigh the interstate 2 mi away and the airport
        ("Noise by source", "Road 41 · Rail 56 · Aircraft 46 dB"),
        ("Flood zone", "AE (high-risk SFHA, BFE 7 ft)"),
        ("Nearest highway", "2.00 mi (I- 95)"),
        ("Nearest railroad", "1.00 mi"),
        ("Nearest airport", "5.64 mi (DAB, Daytona Beach International Airport)"),
        ("Air quality", "AQI 31 Good"),
    ]
    assert view.noise.main_source == "rail"
    assert noise_text(view.noise).startswith("Moderate · ")
    assert view.drive_times == [DriveTime("Mom", 15, 6.14), DriveTime("Work", None, None)]
    assert not view.drive_times[1].available
    assert [p["name"] for p in view.nearby_places] == ["Publix", "Riverside Park"]
    assert (view.nearby_places[0]["minutes"], view.nearby_places[0]["miles"]) == (7, 2.4)
    assert view.nearby_places[1]["minutes"] is None


def test_empty_enrichment():
    view = build_view({})

    assert view.surroundings == []
    assert view.drive_times == []
    assert view.census == []
    assert view.distributions == []


def test_census():
    view = build_view(
        {
            "census_provider": {
                "acs_year": 2024,
                "state": "Colorado",
                "city": {"name": "Highlands Ranch", "type": "CDP", "population": 103000},
                "county": {"name": "Douglas County", "population": 380000},
                "tract": {
                    "geoid": "08035014133",
                    "population": 4210,
                    "median_age": 38.2,
                    "age_groups": {"Under 18": 25.1, "18-54": 46.0, "55+": 28.9},
                    "race_ethnicity": {
                        "White": 78.0,
                        "Black": 0.0,
                        "Asian": 6.5,
                        "Hispanic or Latino": 10.4,
                    },  # fmt: skip
                    "education": {},
                    "bachelors_or_higher_pct": 62.5,
                },
            }
        }
    )

    assert view.acs_year == 2024
    assert dict(view.census) == {
        "City": "Highlands Ranch (CDP)",
        "City population": "103,000",
        "County": "Douglas County, Colorado",
        "County population": "380,000",
        "Census tract": "08035014133",
        "Tract population": "4,210",
        "Tract median age": "38.2",
        "Bachelor's or higher": "62.5%",
    }
    # Largest first, empty groups dropped, empty distributions left out
    assert [(d.title, d.items) for d in view.distributions] == [
        ("Age", [("Under 18", 25.1), ("18-54", 46.0), ("55+", 28.9)]),
        ("Race & ethnicity", [("White", 78.0), ("Hispanic or Latino", 10.4), ("Asian", 6.5)]),
    ]


def test_census_outside_any_city():
    view = build_view(
        {
            "census_provider": {
                "state": "Colorado",
                "city": None,
                "county": {"name": "Boulder County", "population": 330000},
            }
        }  # fmt: skip
    )

    assert "City" not in dict(view.census)
    assert dict(view.census)["County population"] == "330,000"


def test_air_quality_without_aqi():
    view = build_view({"air_quality_provider": {"category": "Moderate"}})
    assert dict(view.surroundings)["Air quality"] == "Moderate"


def test_flood_zone_text():
    assert flood_zone_text(
        {"flood_zone": "X", "flood_risk": "0.2 PCT ANNUAL CHANCE FLOOD HAZARD", "in_sfha": False}
    ) == ("X (0.2% annual chance flood hazard)")
    assert flood_zone_text(
        {"flood_zone": "VE", "in_sfha": True, "base_flood_elevation_ft": 12.5}
    ) == ("VE (high-risk SFHA, BFE 12.5 ft)")
    assert flood_zone_text({"flood_zone": "Not mapped", "in_sfha": None}) == "Not mapped"
    assert flood_zone_text({}) is None


class TestNoiseEstimate:
    def test_nothing_measured(self):
        assert noise_estimate({}, {}, None) is None
        assert noise_text(None) is None
        assert noise_sources_text(None) is None

    def test_highway_next_door(self):
        estimate = noise_estimate({"highway_distances_m": {"motorway": 30}}, {}, None)

        assert noise_text(estimate) == "Very High · 75 dB, mostly road"  # at the reference
        assert noise_sources_text(estimate) == "Road 75 dB"

    def test_older_highway_data_uses_stored_level(self):
        estimate = noise_estimate({"road_noise_level_db": 61.2}, {}, None)

        assert estimate.road_db == 61.2

    def test_rail_main_line_vs_spur(self):
        spur_only = noise_estimate(
            {}, {"railroad_distance_m": 60, "mainline_distance_m": 5000}, None
        )
        main_line = noise_estimate({}, {"railroad_distance_m": 60, "mainline_distance_m": 60}, None)

        assert spur_only.rail_db == 70  # spur at 60 m: 75 - 5
        assert main_line.rail_db == 80  # main line at 60 m: 85 - 5

    def test_older_rail_data_assumes_main_line(self):
        assert noise_estimate({}, {"railroad_distance_m": 60}, None).rail_db == 80

    def test_loudest_airport_wins(self):
        airports = [
            {"category": "general", "distance_m": 1000},  # 58 dB
            {"category": "large", "distance_m": 4000},  # 75 - 12 = 63 dB
        ]
        assert noise_estimate({}, {}, airports).aircraft_db == 63

    def test_no_airport_in_range_is_ambient(self):
        estimate = noise_estimate({}, {}, [])

        assert estimate.aircraft_db == 35
        assert noise_text(estimate) == "Very Low · 35 dB"


def test_scores_without_descriptions():
    """Enriched before descriptions were stored: just the number."""
    view = build_view({"walk_score_provider": {"walk_score": 47, "bike_score": 62}})

    assert view.surroundings == [("Walk score", "47"), ("Bike score", "62")]


class TestHazardsAndSafety:
    def test_build_view_sections(self):
        view = build_view(
            {
                "sinkhole_provider": {
                    "favorability": "Most favorable",
                    "incidents_within_1mi": 3,
                    "verified_within_1mi": 1,
                    "nearest_incident_m": 483,
                    "nearest_incident_year": 2008,
                },
                "elevation_provider": {"elevation_ft": 82.0, "relative_ft": -3.5},
                "evacuation_zone_provider": {"evacuation_zone": None},
                "wetlands_provider": {
                    "in_wetland": False,
                    "nearest_wetland_m": 44,
                    "nearest_wetland_type": "Freshwater Forested/Shrub Wetland",
                },
                "contamination_provider": {
                    "sites_within_half_mi": 2,
                    "superfund_within_half_mi": 0,
                    "sites": [{"name": "Fera Cleaners", "category": "PFAS", "distance_m": 196}],
                },
                "impaired_waters_provider": {
                    "impaired_waters": [
                        {
                            "name": "Lake Eola",
                            "parameters": [
                                "Nutrients (Chlorophyll-a)",
                                "Nutrients (Total Phosphorus)",
                                "Mercury (in fish tissue)",
                            ],
                        }
                    ]
                },  # fmt: skip
                "local_noise_sources_provider": {
                    "fireworks": [{"name": "EPCOT", "distance_m": 5787}],
                    "launch_site": {"name": "Cape Canaveral landing zones", "distance_m": 19521},
                },
                "crime_provider": {
                    "agency": "Orange County Sheriff's Office",
                    "jurisdiction": "county",
                    "reporting": True,
                    "period_start": "01-2025",
                    "period_end": "09-2025",
                    "months": 9,
                    "likely_incomplete": True,
                    "violent_per_100k": 400.0,
                    "state_violent_per_100k": 200.0,
                    "property_per_100k": 1500.0,
                    "state_property_per_100k": None,
                },
                "broadband_provider": {
                    "providers": [
                        {
                            "name": "AT&T Fiber",
                            "technology": "Fiber",
                            "max_down_mbps": 5000.0,
                            "max_up_mbps": 5000.0,
                            "coverage_pct": 10,
                        },
                        {
                            "name": "Spectrum",
                            "technology": "Cable",
                            "max_down_mbps": 1000.0,
                            "max_up_mbps": 35.0,
                            "coverage_pct": 100,
                        },
                    ],
                    "fiber_available": True,
                    "wired_providers": 2,
                    "max_down_mbps": 5000.0,
                },  # fmt: skip
            }
        )

        assert dict(view.hazards) == {
            "Sinkhole geology": "Most favorable to sinkhole formation",
            "Sinkhole reports": "3 within 1 mi (1 verified) · nearest 0.3 mi, 2008",
            "Elevation": "82 ft · 3.5 ft below surrounding ground",
            "Evacuation zone": "None",
            "Wetlands": "Freshwater Forested/Shrub Wetland 144 ft away",
            "Contamination sites": "2 open within ½ mi · nearest Fera Cleaners (PFAS), 643 ft",
            "Impaired waters": "Lake Eola (nutrients, mercury)",
        }
        surroundings = dict(view.surroundings)
        assert surroundings["Fireworks"] == "EPCOT 3.6 mi"
        assert surroundings["Rocket launches"] == "12 mi from the Cape · sonic booms likely"
        assert dict(view.safety) == {
            "Police agency": "Orange County Sheriff's Office",
            "Violent crime": "400 per 100k · 2.0× Florida",
            "Property crime": "1,500 per 100k · reporting looks incomplete",
            "Crime data period": "01-2025 to 09-2025 (9 mo) · agency-wide (county)",
            # Fiber reaches 10% of the block, so it's neither listed nor counted
            "Internet": "No fiber · 1 wired provider · up to 1,000 Mbps",
        }
        assert [p["name"] for p in view.internet] == ["Spectrum"]

    def test_missing_providers_add_nothing(self):
        view = build_view({})
        assert view.hazards == [] and view.safety == [] and view.internet == []

    def test_quiet_results(self):
        view = build_view(
            {
                "sinkhole_provider": {"favorability": None, "incidents_within_1mi": 0},
                "elevation_provider": {"elevation_ft": 100.2, "relative_ft": 0.4},
                "evacuation_zone_provider": {"evacuation_zone": "A"},
                "wetlands_provider": {
                    "in_wetland": True,
                    "nearest_wetland_type": "Freshwater Emergent Wetland",
                },
                "contamination_provider": {"sites_within_half_mi": 0},
                "impaired_waters_provider": {"impaired_waters": []},
                "crime_provider": {"agency": "Orlando Police Department", "reporting": False},
                "broadband_provider": {"providers": []},
            }
        )

        assert dict(view.hazards) == {
            "Sinkhole reports": "None within 1 mi",
            "Elevation": "100 ft · level with surroundings",
            "Evacuation zone": "Zone A (evacuates first)",
            "Wetlands": "On a mapped wetland (Freshwater Emergent Wetland)",
            "Contamination sites": "None within ½ mi",
            "Impaired waters": "None nearby",
        }
        assert dict(view.safety) == {
            "Police agency": "Orlando Police Department",
            "Violent crime": "Agency not reporting to the FBI",
            "Internet": "No wired or fixed wireless providers listed",
        }
