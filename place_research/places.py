"""Representation of a Place """

from googlemaps import Client


def get_nearby_places_from_list(
    gmaps: Client, address: str, search_radius: int, seach_nearby: list[str]
):
    """Get nearby places from a list of places"""
    places = []
    geocode_result = gmaps.geocode(address)  # type: ignore
    lat = geocode_result[0]["geometry"]["location"]["lat"]
    lng = geocode_result[0]["geometry"]["location"]["lng"]
    for place in seach_nearby:
        places.append(
            gmaps.places_nearby(location=(lat, lng), radius=search_radius, type=place)  # type: ignore
        )
    return places


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
    gmaps: Client, address: str, search_radius: int, place_type: str
):
    """Search for operational places nearby a given address."""
    places = gmaps.places(location=address, radius=search_radius, type=place_type)  # type: ignore
    return [
        get_place_details(gmaps, place["place_id"])
        # place
        for place in places["results"]
        if place.get("business_status") == "OPERATIONAL"
    ]
