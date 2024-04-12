""" Functions to search for places nearby a given address. """

import pandas as pd
from googlemaps import Client
from place_research.routes import get_distances_from_origin
from place_research.utils import meters_to_miles


def calculate_distance_score(distance):
    """Calculate a score based on the distance to a place."""
    if distance <= 1:
        return 5
    if distance <= 5:
        return 4
    if distance <= 10:
        return 3
    if distance <= 20:
        return 2
    return 1


def calculate_composite_score(df: pd.DataFrame):
    """Calculate a composite score based on the distance and rating of a place."""
    return round(df.groupby("search_term")["distance_score"].max().mean(), 2)


def place_results_to_dataframe(
    gmaps: Client, subject_address: str, places_nearby: list[dict]
) -> pd.DataFrame:
    """Convert a list of places to a pandas DataFrame."""
    # Get the addresses of the places
    points = [x["address"] for x in places_nearby]

    # Get the distances from the subject address to the places in chunks of 10
    chunk_size = 10
    distances = []

    for i in range(0, len(points), chunk_size):
        chunk = points[i : i + chunk_size]
        distances.extend(get_distances_from_origin(gmaps, subject_address, chunk))

    # Add the distances to the places
    for place, distance in zip(places_nearby, distances):
        place["distance"] = meters_to_miles(distance["distance"])
        place["duration"] = int(round(distance["duration"] / 60, 0))

    # Convert the list of places to a DataFrame
    df = pd.DataFrame(places_nearby)

    return df


def get_nearest_places(input_df: pd.DataFrame):
    """Get the nearest places for each search term."""
    df = input_df.copy()

    # Get rows where the distance score is the max for the search term
    df = (
        df.loc[
            df.groupby("search_term")["distance_score"].idxmax(),
            ["search_term", "name", "distance", "duration", "distance_score"],
        ]
        .reset_index(drop=True)
        .set_index("search_term")
    )

    return df


def make_nearest_places_pretty(styler):
    """Apply styling to the nearest places DataFrame."""
    styler.background_gradient(cmap="RdYlGn", subset=["distance_score"], vmin=1, vmax=5)
    return styler
