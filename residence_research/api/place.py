from __future__ import annotations

import requests
import googlemaps
import os
from dataclasses import dataclass
from typing import Literal


@dataclass
class Place:
    formatted_address: str
    latitude: float
    longitude: float
    place_id: str

    @classmethod
    def place_from_address(gmaps: googlemaps.Client, address: str) -> Place:
        result = gmaps.geocode(address)
        return Place(
            formatted_address=result[0]["formatted_address"],
            latitude=result[0]["geometry"]["location"]["lat"],
            longitude=result[0]["geometry"]["location"]["lng"],
            place_id=result[0]["place_id"],
        )


@dataclass
class DistanceData:
    text: str
    value: float


@dataclass
class Distance:
    origin: Place
    destination: Place
    distance: dict
    duration: dict


@dataclass
class Store:
    name: str
    place_id: str
    rating: float
    user_ratings_total: int
    distance: Distance = None
    # types: list[str]


def get_driving_distance(
    gmaps: googlemaps.Client, origin_place_id: str, destination_place_id: str
):
    # Get the driving distance from the origin to the store.
    distance_matrix = gmaps.distance_matrix(
        origins="place_id:" + origin_place_id,
        destinations=["place_id:" + destination_place_id],
        mode="driving",
        units="imperial",
    )

    return Distance(
        origin=origin_place_id,
        destination=destination_place_id,
        distance=distance_matrix["rows"][0]["elements"][0]["distance"],
        duration=distance_matrix["rows"][0]["elements"][0]["distance"],
    )


def find_stores_nearby(
    gmaps: googlemaps.Client,
    latitude: float,
    longitude: float,
    n: int = 3,
    name: str = None,
    keyword: str = None,
):
    assert name or keyword, "Name or keyword must be given"

    # Search for places near the origin.
    stores = gmaps.places_nearby(
        location=(latitude, longitude),
        radius=50000,  # Search within 50 km of the origin.
        name=name,
        keyword=keyword,
    )

    # print(stores)

    # Take the first three open stores
    stores_result = [
        Store(
            name=store["name"],
            rating=store["rating"],
            user_ratings_total=store["user_ratings_total"],
            place_id=store["place_id"],
            # types=store["types"],
        )
        for store in stores["results"]
        if store["business_status"] == "OPERATIONAL"
    ]

    # stores_result = sorted(stores_result, key=lambda x: x['distances']['duration']['value'])

    return stores_result


def find_stores_by_travel_duration(
    gmaps: googlemaps.Client, place: Place, name: str = None, keyword: str = None, n=3
):
    stores = find_stores_nearby(
        gmaps, place.latitude, place.longitude, name=name, keyword=keyword
    )

    for store in stores:
        store.distance = get_driving_distance(gmaps, place.place_id, store.place_id)

    return sorted(stores, key=lambda x: x.distance.duration["value"])[0:n]




def main():
    gmaps = googlemaps.Client(
        key=os.environ["GOOGLE_MAPS_API_KEY"], queries_per_second=50
    )
    address = "3058 OH-3, Loudonville, OH 44842"
    place = place_from_address(gmaps, address)
    walmarts = find_stores_by_travel_duration(gmaps, place, name="walmart supercenter")
    for walmart in walmarts:
        print(walmart)


if __name__ == "__main__":
    main()
