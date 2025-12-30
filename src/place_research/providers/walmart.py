import logging
import os
from dataclasses import dataclass
from typing import TYPE_CHECKING

import googlemaps

from place_research.interfaces import DisplayableResult, ProviderNameMixin

if TYPE_CHECKING:
    from ..models import Place


@dataclass
class WalmartResult(DisplayableResult):
    """Walmart result for a specific place."""

    distance_km: float | None
    duration_m: float | None
    distance_category: str | None
    duration_category: str | None
    rating: float | None

    def display(self):
        """Display Walmart result in a human-readable way."""
        return (
            f"Walmart Supercenter\n"
            f"Distance: {self.distance_km} km ({self.distance_category})\n"
            f"Duration: {self.duration_m} min ({self.duration_category})\n"
            f"Rating: {self.rating} / 5\n"
        )

    def to_dict(self):
        """Convert Walmart result to a dictionary."""
        return {
            "distance_km": self.distance_km,
            "duration_m": self.duration_m,
            "distance_category": self.distance_category,
            "duration_category": self.duration_category,
            "rating": self.rating,
        }


def categorize_distance(distance_km: float | None) -> str:
    """Categorize distance into predefined categories.

    Args:
        distance_km (float | None): Distance in kilometers.

    Returns:
        str: Distance category.
    """
    if distance_km is None:
        return "Unknown"
    if distance_km < 7:
        return "Very Close"
    elif distance_km < 15:
        return "Close"
    elif distance_km < 30:
        return "Far"
    else:
        return "Very Far"


def categorize_duration(duration_m: float | None) -> str:
    """Categorize duration into predefined categories.

    Args:
        duration_m (float | None): Duration in minutes.

    Returns:
        str: Duration category.
    """
    if duration_m is None:
        return "Unknown"
    if duration_m < 7:
        return "Very Quick"
    elif duration_m < 15:
        return "Quick"
    elif duration_m < 30:
        return "Slow"
    else:
        return "Very Slow"


class WalmartProvider(ProviderNameMixin):
    """Walmart provider for fetching place data."""

    def __init__(self):

        # Get Google Maps API key from environment, config, or provider config
        self.api_key = os.getenv("GOOGLE_MAPS_API_KEY")
        self.logger = logging.getLogger(__name__)

        if not self.api_key:
            self.logger.error(
                "Google Maps API key missing. Set GOOGLE_MAPS_API_KEY envvar or config.json"
            )

    def fetch_place_data(self, place: "Place") -> WalmartResult:
        """
        Fetch nearest Walmart Supercenter data for the given place.
        """

        gmaps = googlemaps.Client(key=self.api_key, queries_per_second=5)
        coordinates = (place.latitude, place.longitude)

        # Find nearest Walmart Supercenter
        nearest_walmarts = gmaps.places_nearby(  # type: ignore
            location=coordinates,
            keyword="Walmart Supercenter",
            rank_by="distance",
        )

        results = nearest_walmarts.get("results", [])
        if not results:
            self.logger.error("No Walmart Supercenter found nearby.")
            return WalmartResult(
                distance_km=None,
                duration_m=None,
                distance_category="Unknown",
                duration_category="Unknown",
                rating=None,
            )

        walmart = results[0]

        lat = walmart["geometry"]["location"]["lat"]
        lng = walmart["geometry"]["location"]["lng"]

        # Get distance and duration from the Place to the walmart
        matrix_result = gmaps.distance_matrix(  # type: ignore
            origins=coordinates, destinations=(lat, lng), mode="driving"
        )

        if not matrix_result.get("rows"):
            self.logger.error("No rows found in distance matrix response.")
            return WalmartResult(
                distance_km=None,
                duration_m=None,
                distance_category="Unknown",
                duration_category="Unknown",
                rating=None,
            )

        elements = matrix_result["rows"][0]["elements"]
        if not elements:
            self.logger.error("No elements found in distance matrix response.")
            return WalmartResult(
                distance_km=None,
                duration_m=None,
                distance_category="Unknown",
                duration_category="Unknown",
                rating=None,
            )

        element = elements[0]
        if element["status"] != "OK":
            self.logger.error(
                "Failed to get valid route from Google Maps API: %s", element
            )
            raise ValueError("Invalid route data from Google Maps API.")

        # Extract distance and duration information
        walmart_distance_km = round(
            element["distance"]["value"] / 1000, 1
        )  # Convert to km
        walmart_duration_m = round(
            element["duration"]["value"] / 60, 1
        )  # Convert to minutes

        # Categorize distance and duration
        walmart_distance_category = categorize_distance(walmart_distance_km)
        walmart_duration_category = categorize_duration(walmart_duration_m)

        # Get Walmart rating
        walmart_rating = walmart.get("rating", 0.0)

        return WalmartResult(
            distance_km=walmart_distance_km,
            duration_m=walmart_duration_m,
            distance_category=walmart_distance_category,
            duration_category=walmart_duration_category,
            rating=walmart_rating,
        )
