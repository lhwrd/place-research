""" Module for finding points along a route and getting distances
from an origin to a list of points. """

from googlemaps import Client
from flask import current_app as app

def find_points_along_route(
    gmaps: Client, start_address: str, end_address: str, stops: int
):
    """Given a number of stops, find equidistant points along a route between two addresses.

    Args:
        start_address (str): Start address for the route
        end_address (str): End address for the route
        stops (int): Number of stops to find along the route
    """
    route = gmaps.directions(start_address, end_address)  # type: ignore
    steps = route[0]["legs"][0]["steps"]
    total_distance = route[0]["legs"][0]["distance"]["value"]
    interval_distance = round(total_distance / (stops + 1), 0)

    stop_locations = []
    distance_covered = 0

    for step in steps:
        step_distance = step["distance"]["value"]
        while distance_covered + step_distance >= interval_distance:
            fraction = (interval_distance - distance_covered) / step_distance
            lat = step["start_location"]["lat"] + fraction * (
                step["end_location"]["lat"] - step["start_location"]["lat"]
            )
            lng = step["start_location"]["lng"] + fraction * (
                step["end_location"]["lng"] - step["start_location"]["lng"]
            )
            stop_locations.append((lat, lng))
            step_distance -= interval_distance - distance_covered
            distance_covered = 0
        distance_covered += step_distance

    return stop_locations


def get_distances_from_origin(
    gmaps: Client, origin: str | tuple[float, float], points: list
):
    """Get distances from an origin to a list of points"""
    distances = gmaps.distance_matrix(origin, points, mode="driving")  # type: ignore

    result = []

    for i, point in enumerate(points):
        result.append(
            {
                "location": distances["destination_addresses"][i],
                "point": point,
                "distance": distances["rows"][0]["elements"][i]["distance"]["value"],
                "duration": distances["rows"][0]["elements"][i]["duration"]["value"],
            }
        )

    return result


def chunked_distance_matrix(
    gmaps: Client, origin: str | tuple[float, float], points: list[str]
):
    """Get the distance matrix from the subject address to a list of points."""
    chunk_size = 10
    distances = []

    for i in range(0, len(points), chunk_size):
        chunk = points[i : i + chunk_size]
        distances.extend(get_distances_from_origin(gmaps, origin, chunk))

    app.logger.debug("Distances: %s", distances)

    return distances
