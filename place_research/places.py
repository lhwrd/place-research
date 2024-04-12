"""Representation of a Place """

import logging
from googlemaps import Client

logger = logging.getLogger(__name__)


def get_lat_lng(gmaps: Client, address: str) -> tuple[float, float]:
    """Get the latitude and longitude of an address as tuple"""
    geocode_result = gmaps.geocode(address)  # type: ignore
    return (
        geocode_result[0]["geometry"]["location"]["lat"],
        geocode_result[0]["geometry"]["location"]["lng"],
    )


def get_place_details(gmaps: Client, place_id: str):
    """Get details about a place"""
    place_details = gmaps.place(place_id=place_id)  # type: ignore
    place_details = place_details.get("result")
    return {
        "name": place_details.get("name"),
        "address": place_details.get("formatted_address"),
        "rating": place_details.get("rating"),
        "user_ratings_total": place_details.get("user_ratings_total"),
        "url": place_details.get("url"),
    }


def search_places_nearby(
    gmaps: Client,
    location,
    radius: int,
    keyword: str | None = None,
    place_type: str | None = None,
):
    """Search for operational places nearby a given address."""
    lat, lng = get_lat_lng(gmaps, location)
    places = gmaps.places_nearby(  # type: ignore
        location=(lat, lng), radius=radius, keyword=keyword, type=place_type
    )
    return [
        get_place_details(gmaps, place["place_id"])
        # place
        for place in places["results"]
        if place.get("business_status") == "OPERATIONAL"
    ]


def search_multiple_places(
    gmaps: Client,
    subject_address: str,
    search_radius: int,
    search_terms: list[dict],
) -> list[dict]:
    """Search for multiple places by name or type within a certain radius of a subject address."""
    results = []
    # Search for each term in the list
    for term in search_terms:
        keyword = term.get("keyword")
        place_type = term.get("type")
        search_term = keyword or place_type

        logger.info("Searching for %s near %s", search_term, subject_address)

        result = search_places_nearby(
            gmaps,
            subject_address,
            search_radius,
            keyword=keyword,
            place_type=place_type,
        )

        # Add the term to each result
        for place in result:
            place["search_term"] = keyword or place_type

        results.extend(result)

    return results
