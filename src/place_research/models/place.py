from datetime import datetime
import os
from typing import Any, Optional
from uuid import uuid4

import googlemaps
from pydantic import BaseModel, Field

from place_research.models.results import EnrichmentResult


class Place(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    created_at: str = Field(default=datetime.now().isoformat())
    updated_at: str = Field(default=datetime.now().isoformat())
    address: str
    latitude: float = 0.0
    longitude: float = 0.0
    city: Optional[str] = None
    county: Optional[str] = None
    state: Optional[str] = None

    # Attributes
    enrichments: Optional[EnrichmentResult] = None

    def model_post_init(self, __context: Any) -> None:
        """Reverse geocode the place's coordinates."""
        gmaps_api_key = os.getenv("GOOGLE_MAPS_API_KEY")

        gmaps = googlemaps.Client(key=gmaps_api_key)

        geocode_result = gmaps.geocode(self.address)  # type: ignore
        if not geocode_result:
            raise ValueError(f"Geocoding failed for address: {self.address}")
        geocode_result = geocode_result[0]

        self.latitude = geocode_result["geometry"]["location"]["lat"]
        self.longitude = geocode_result["geometry"]["location"]["lng"]

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
