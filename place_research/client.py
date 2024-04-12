""" Module for creating a Google Maps API client instance."""
import os
from googlemaps import Client


def get_client(api_key: str | None = None):
    """Get a Google Maps API client instance."""
    api_key = api_key or os.environ.get("GOOGLE_MAPS_API_KEY")
    assert api_key is not None, "API key must be provided."
    return Client(key=api_key, timeout=10, queries_per_second=5)
