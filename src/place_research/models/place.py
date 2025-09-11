import os

import googlemaps
from pydantic import BaseModel, Field


class Place(BaseModel):
    id: int = Field(alias="Id")
    created_at: str = Field(alias="CreatedAt")
    updated_at: str = Field(alias="UpdatedAt")
    address: str = Field(alias="Address")
    geolocation: str | None = Field(alias="Geolocation", default="0;0")
    city: str | None = Field(alias="City")
    county: str | None = Field(alias="County")
    state: str | None = Field(alias="State")

    # Attributes
    nearest_railroad: int | None = Field(alias="Nearest Railroad")
    walk_score: int | None = Field(alias="Walk Score")
    walk_description: str | None = Field(alias="Walk Description")
    bike_score: int | None = Field(alias="Bike Score")
    bike_description: str | None = Field(alias="Bike Description")
    walmart_distance_km: float | None = Field(alias="Walmart Distance (km)")
    walmart_duration_m: float | None = Field(alias="Walmart Duration (min)")
    walmart_distance_category: str | None = Field(alias="Walmart Distance Category")
    walmart_duration_category: str | None = Field(alias="Walmart Duration Category")
    walmart_rating: float | None = Field(alias="Walmart Rating")
    highway_distance_m: int | None = Field(alias="Highway Distance (m)")
    nearest_highway_type: str | None = Field(alias="Nearest Highway Type")
    road_noise_level_db: float | None = Field(alias="Road Noise Level (dB)")
    road_noise_category: str | None = Field(alias="Road Noise Category")
    flood_zone: str | None = Field(alias="Flood Zone")
    flood_risk: str | None = Field(alias="Flood Risk")
    air_quality: str | None = Field(alias="Air Quality")
    air_quality_category: str | None = Field(alias="Air Quality Category")
    annual_avg_temp: float | None = Field(alias="Annual Avg Temp")
    annual_avg_precip: float | None = Field(alias="Annual Avg Precip")
    proximity_to_family: dict | None = Field(alias="Proximity to Family")

    class Config:
        validate_by_alias = True
        serialization_by_alias = True

    def reverse_geocode(self) -> None:
        """Reverse geocode the place's coordinates."""
        gmaps_api_key = os.getenv("GOOGLE_MAPS_API_KEY")

        gmaps = googlemaps.Client(key=gmaps_api_key)

        geocode_result = gmaps.geocode(self.address)  # type: ignore
        if not geocode_result:
            raise ValueError(f"Geocoding failed for address: {self.address}")
        geocode_result = geocode_result[0]

        self.geolocation = ";".join(
            [
                str(geocode_result["geometry"]["location"]["lat"]),
                str(geocode_result["geometry"]["location"]["lng"]),
            ]
        )
        # Extract city, county, and state information from geocoding result
        city_name = None
        county_name = None
        state_name = None

        city_candidates = [
            component["long_name"]
            for component in geocode_result["address_components"]
            if "locality" in component["types"]
        ]
        city_name = city_candidates[0] if city_candidates else None

        county_candidates = [
            component["long_name"]
            for component in geocode_result["address_components"]
            if "administrative_area_level_2" in component["types"]
        ]
        county_name = county_candidates[0] if county_candidates else None

        state_candidates = [
            component["long_name"]
            for component in geocode_result["address_components"]
            if "administrative_area_level_1" in component["types"]
        ]
        state_name = state_candidates[0] if state_candidates else None

        # Create City and County objects if we have the necessary information
        if city_name and state_name:
            self.city = city_name

        if county_name and state_name:
            self.county = county_name

        if state_name:
            self.state = state_name
