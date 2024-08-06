"""Representation of a Place """

from googlemaps import Client
from flask import current_app as app

def get_lat_lng(gmaps: Client, address: str) -> tuple[float, float]:
    """Get the latitude and longitude of an address as tuple"""
    app.logger.info("Getting lat/lng for %s", address)
    geocode_result = gmaps.geocode(address)  # type: ignore
    return (
        geocode_result[0]["geometry"]["location"]["lat"],
        geocode_result[0]["geometry"]["location"]["lng"],
    )


def get_place_details(gmaps: Client, place_id: str):
    """Get details about a place"""
    app.logger.info("Getting details for place %s", place_id)
    place_details = gmaps.place(place_id=place_id)  # type: ignore
    place_details = place_details.get("result")
    # logger.debug(place_details)
    return {
        "name": place_details.get("name"),
        "address": place_details.get("formatted_address"),
        "rating": place_details.get("rating"),
        "user_ratings_total": place_details.get("user_ratings_total"),
        "url": place_details.get("url"),
        "location": place_details.get("geometry").get("location"),
    }


def search_places_nearby(
    gmaps: Client,
    location: tuple[float, float],
    radius: int | None = None,
    keyword: str | None = None,
    place_type: str | None = None,
    number_of_places: int = 3,
):
    """Search for operational places nearby a given address."""
    app.logger.info("Searching for places near %s within %s meters", location, radius)
    places = gmaps.places_nearby(  # type: ignore
        location=location,
        # radius=radius,
        keyword=keyword,
        type=place_type,
        rank_by="distance",
    )
    app.logger.debug("Found %s places", len(places["results"]))

    # Filter for only operational places
    places = [
        place
        for place in places["results"]
        if place.get("business_status") == "OPERATIONAL"
    ]

    # Take the first number_of_places
    places = places[:number_of_places]

    return places


def search_multiple_places(
    gmaps: Client,
    subject_address: str,
    search_terms: list[dict],
) -> list[dict]:
    """Search for multiple places by name or type within a certain radius of a subject address."""
    location = get_lat_lng(gmaps, subject_address)
    results = []
    # Search for each term in the list
    for term in search_terms:
        keyword = term.get("keyword")
        place_type = term.get("type")
        search_term = keyword or place_type

        app.logger.info("Searching for %s near %s", search_term, subject_address)

        result = search_places_nearby(
            gmaps,
            location,
            keyword=keyword,
            place_type=place_type,
        )

        # Add the term to each result
        for place in result:
            place["search_term"] = keyword or place_type

        results.extend(result)

    return results
