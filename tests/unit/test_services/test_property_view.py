"""Tests for formatting stored provider data for the web UI."""

from app.services.property_view import (
    DriveTime,
    build_view,
    flood_zone_text,
    noise_estimate,
    noise_sources_text,
    noise_text,
)


def values(rows):
    return {r.label: r.value for r in rows}


def pairs(rows):
    return [(r.label, r.value) for r in rows]


def levels(rows):
    return {r.label: r.level for r in rows}


def test_build_view_formats_every_provider():
    view = build_view(
        walk_scores={
            "walk_score": 45,
            "description": "Car-Dependent",
            "bike_score": 60,
            "bike_description": "Bikeable",
            "transit_score": None,
            "transit_description": None,
        },
        enrichment={
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
        },
    )

    assert pairs(view.surroundings) == [
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
    assert view.drive_times == [
        DriveTime("Mom", 15, 6.14, "good"),
        DriveTime("Work", None, None, None),
    ]
    assert levels(view.surroundings) == {
        "Walk score": "fair",
        "Bike score": "fair",
        "Noise": "fair",  # 56 dB
        "Noise by source": None,
        "Flood zone": "poor",
        "Nearest highway": "good",
        "Nearest railroad": "good",
        "Nearest airport": None,
        "Air quality": "good",
    }
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
    assert values(view.census) == {
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

    assert "City" not in values(view.census)
    assert values(view.census)["County population"] == "330,000"


def test_air_quality_without_aqi():
    view = build_view({"air_quality_provider": {"category": "Moderate"}})
    assert values(view.surroundings)["Air quality"] == "Moderate"


def test_odor_sources():
    def view(data):
        return build_view({"odor_sources_provider": data}).surroundings

    assert view({}) == []
    assert pairs(view({"source_count": 0, "sources": []})) == [("Odor sources", "None in range")]

    sources = [
        {"name": "Iron Bridge WRF", "kind": "wastewater_plant",
         "type": "wastewater treatment plant", "distance_m": 300},
        {"name": "ORANGE COUNTY LF", "kind": "landfill", "type": "landfill", "distance_m": 3200},
        {"name": None, "kind": "asphalt_plant", "type": "asphalt plant", "distance_m": 1500},
        {"name": "Fourth", "kind": "landfill", "type": "landfill", "distance_m": 4500},
    ]  # fmt: skip
    rows = view({"source_count": 5, "sources": sources})
    assert pairs(rows) == [
        (
            "Odor sources",
            "Iron Bridge WRF (wastewater treatment plant) 984 ft · ORANGE COUNTY LF (landfill) "
            "2.0 mi · Unnamed (asphalt plant) 0.9 mi · +2 more",
        )
    ]
    assert rows[0].level == "poor"


def test_beach_parking():
    def view(sites):
        return build_view({"beach_parking_provider": {"sites": sites}}).surroundings

    assert view([]) == []
    site = {"name": "Lori Wilson Park", "beach": "Cocoa Beach", "coast": "Atlantic",
            "fee": "1.50/hr", "drive_minutes": 58, "drive_miles": 52.31}  # fmt: skip
    rows = view([site, {"name": "Farther", "drive_minutes": 70}])
    assert pairs(rows) == [
        (
            "Nearest beach parking",
            "58 min · 52.3 mi (Lori Wilson Park, Cocoa Beach · Atlantic · parking 1.50/hr)",
        )
    ]
    assert rows[0].level == "fair"

    # A park named for its beach isn't repeated; "yes" is a fee of unknown size
    site = {"name": "Siesta Beach", "beach": "Siesta Beach", "coast": "Gulf", "fee": "yes",
            "drive_minutes": 135, "drive_miles": 131}  # fmt: skip
    rows = view([site])
    assert rows[0].value == "2 hr 15 min · 131.0 mi (Siesta Beach · Gulf · paid parking)"
    assert rows[0].level == "poor"


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
    """Just the number where Walk Score sends no description."""
    view = build_view({}, {"walk_score": 47, "bike_score": 62})

    assert pairs(view.surroundings) == [("Walk score", "47"), ("Bike score", "62")]


class TestHazardsAndInternet:
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

        assert values(view.hazards) == {
            "Sinkhole geology": "Most favorable to sinkhole formation",
            "Sinkhole reports": "3 within 1 mi (1 verified) · nearest 0.3 mi, 2008",
            "Elevation": "82 ft · 3.5 ft below surrounding ground",
            "Evacuation zone": "None",
            "Wetlands": "Freshwater Forested/Shrub Wetland 144 ft away",
            "Contamination sites": "2 open within ½ mi · nearest Fera Cleaners (PFAS), 643 ft",
            "Impaired waters": "Lake Eola (nutrients, mercury)",
        }
        surroundings = values(view.surroundings)
        assert surroundings["Fireworks"] == "EPCOT 3.6 mi"
        assert surroundings["Rocket launches"] == "12 mi from the Cape · sonic booms likely"
        assert view.internet_summary.value == "No fiber · 1 wired provider · up to 1,000 Mbps"
        assert [p["name"] for p in view.internet] == ["Spectrum"]

    def test_levels_and_scorecard(self):
        view = build_view(
            {
                "sinkhole_provider": {"favorability": "Most favorable", "incidents_within_1mi": 0},
                "elevation_provider": {"elevation_ft": 82.0, "relative_ft": -1.5},
                "evacuation_zone_provider": {"evacuation_zone": "A"},
                "contamination_provider": {"sites_within_half_mi": 0},
                "broadband_provider": {
                    "providers": [
                        {
                            "name": "Spectrum",
                            "technology": "Cable",
                            "max_down_mbps": 1000.0,
                            "max_up_mbps": 35.0,
                            "coverage_pct": 100,
                        }
                    ],
                },  # fmt: skip
                "distance_provider": {
                    "distances": [
                        {
                            "location_name": "Work",
                            "status": "OK",
                            "duration_minutes": 45,
                            "distance_miles": 30,
                        }
                    ]
                },  # fmt: skip
                "places_nearby_provider": {
                    "places_nearby": [{"name": "Publix", "drive_minutes": 4, "drive_miles": 1}]
                },
                "census_provider": {"county": {"name": "Orange County", "population": 1}},
            }
        )

        assert levels(view.hazards) == {
            "Sinkhole geology": "poor",
            "Sinkhole reports": "good",
            "Elevation": "fair",
            "Evacuation zone": "poor",
            "Contamination sites": "good",
        }
        assert view.internet_summary.level == "fair"  # fast cable, no fiber
        assert all(r.level is None for r in view.census)  # demographics are never rated
        # Rated, but left out of the scorecard
        assert view.drive_times[0].level == "poor"
        assert view.nearby_places[0]["level"] == "good"
        assert view.scorecard() == {
            "counts": {"good": 2, "fair": 2, "poor": 2},
            "total": 6,
            "poor": ["Sinkhole geology", "Evacuation zone"],
        }

    def test_missing_providers_add_nothing(self):
        view = build_view({})
        assert view.hazards == [] and view.internet_summary is None and view.internet == []

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
                "broadband_provider": {"providers": []},
            }
        )

        assert values(view.hazards) == {
            "Sinkhole reports": "None within 1 mi",
            "Elevation": "100 ft · level with surroundings",
            "Evacuation zone": "Zone A (evacuates first)",
            "Wetlands": "On a mapped wetland (Freshwater Emergent Wetland)",
            "Contamination sites": "None within ½ mi",
            "Impaired waters": "None nearby",
        }
        assert view.internet_summary.value == "No wired or fixed wireless providers listed"


def test_scores_saved_by_earlier_versions_are_not_shown():
    """Walk Score's terms don't allow storing scores; only ones fetched for this view count."""
    view = build_view({"walk_score_provider": {"walk_score": 47}})

    assert view.surroundings == []


class TestParcel:
    RECORD = {
        "found": True,
        "match": "address",
        "county": "Orange",
        "parcel_id": "242229582203011",
        "assessment_year": 2026,
        "situs_address": "1216 VIRGINIA DR, Orlando",
        "use": "Single family",
        "year_built": 1955,
        "effective_year_built": 1980,
        "living_area_sqft": 2376,
        "lot_sqft": 12333,
        "lot_acres": 0.28,
        "residential_units": 1,
        "quality": "Average",
        "just_value": 636740,
        "land_value": 374400,
        "taxable_value": 561740,
        "homestead": True,
        "recent_sales": [
            {"year": 2025, "month": 11, "price": 100, "arms_length": False, "vacant_land": False},
            {"year": 2025, "month": 3, "price": 410000, "arms_length": True, "vacant_land": False},
        ],
    }

    def test_rows(self):
        view = build_view({"parcel_provider": self.RECORD})
        assert pairs(view.parcel) == [
            ("Use", "Single family"),
            ("Year built", "1955 (effective 1980, after updates)"),
            ("Living area", "2,376 sqft"),
            ("Lot", "0.28 ac (12,333 sqft)"),
            ("Construction quality", "Average"),
            ("Just (market) value", "$636,740 (land $374,400)"),
            ("Taxable value", "$561,740"),
            ("Homestead", "Yes, owner-occupied"),
            ("Recent sales", "Nov 2025 · $100 (not arm's length); Mar 2025 · $410,000"),
            ("Parcel", "Orange County, 242229582203011, 2026 roll"),
        ]
        assert view.parcel_note is None

    def test_unrated_and_not_in_scorecard(self):
        view = build_view({"parcel_provider": self.RECORD})
        assert all(r.level is None for r in view.parcel)
        assert view.scorecard()["total"] == 0

    def test_vacant_lot_and_multiple_units(self):
        record = {"found": True, "use": "Multi-family, under 10 units", "residential_units": 2,
                  "year_built": 1950, "effective_year_built": 1950, "homestead": False}  # fmt: skip
        assert pairs(build_view({"parcel_provider": record}).parcel) == [
            ("Use", "Multi-family, under 10 units"),
            ("Year built", "1950"),
            ("Units", "2 residential units"),
            ("Homestead", "No"),
        ]

    def test_nearest_parcel_is_flagged(self):
        view = build_view({"parcel_provider": {**self.RECORD, "match": "nearest"}})
        assert view.parcel_note == (
            "No parcel matched this address, so this is the parcel nearest the map pin "
            "(1216 VIRGINIA DR, Orlando)."
        )

    def test_not_found_or_missing(self):
        assert build_view({"parcel_provider": {"found": False}}).parcel == []
        assert build_view({}).parcel == []
