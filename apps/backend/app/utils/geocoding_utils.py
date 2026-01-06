"""Geocoding utility functions."""

import math
from typing import Tuple


def calculate_bounding_box(
    latitude: float, longitude: float, radius_miles: float
) -> Tuple[float, float, float, float]:
    """
    Calculate bounding box coordinates for a radius around a point.

    Useful for database queries to find nearby properties.

    Args:
        latitude: Center point latitude
        longitude: Center point longitude
        radius_miles: Radius in miles

    Returns:
        Tuple of (min_lat, max_lat, min_lon, max_lon)
    """
    # Earth's radius in miles
    earth_radius = 3959.0

    # Angular distance in radians
    angular_distance = radius_miles / earth_radius

    # Convert to radians
    lat_rad = math.radians(latitude)

    # Calculate bounding box
    min_lat = latitude - math.degrees(angular_distance)
    max_lat = latitude + math.degrees(angular_distance)

    # Longitude calculation depends on latitude
    delta_lon = math.degrees(angular_distance / math.cos(lat_rad))
    min_lon = longitude - delta_lon
    max_lon = longitude + delta_lon

    return (min_lat, max_lat, min_lon, max_lon)


def is_point_in_radius(
    center_lat: float,
    center_lon: float,
    point_lat: float,
    point_lon: float,
    radius_miles: float,
) -> bool:
    """
    Check if a point is within a radius of a center point.

    Args:
        center_lat: Center latitude
        center_lon: Center longitude
        point_lat: Point latitude
        point_lon: Point longitude
        radius_miles:  Radius in miles

    Returns:
        True if point is within radius
    """
    # Calculate distance using Haversine
    distance = haversine_distance(center_lat, center_lon, point_lat, point_lon)
    return distance <= radius_miles


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate distance between two points using Haversine formula.

    Args:
        lat1: First point latitude
        lon1: First point longitude
        lat2: Second point latitude
        lon2: Second point longitude

    Returns:
        Distance in miles
    """
    # Earth's radius in miles
    earth_radius = 3959.0

    # Convert to radians
    lat1_rad = math.radians(lat1)
    lon1_rad = math.radians(lon1)
    lat2_rad = math.radians(lat2)
    lon2_rad = math.radians(lon2)

    # Haversine formula
    dlat = lat2_rad - lat1_rad
    dlon = lon2_rad - lon1_rad

    a = math.sin(dlat / 2) ** 2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2) ** 2
    c = 2 * math.asin(math.sqrt(a))

    distance = earth_radius * c
    return distance


def format_coordinates(latitude: float, longitude: float, precision: int = 6) -> str:
    """
    Format coordinates as a string.

    Args:
        latitude: Latitude
        longitude: Longitude
        precision:  Decimal places

    Returns:
        Formatted string like "37.422476, -122.084250"
    """
    return f"{latitude:.{precision}f}, {longitude:.{precision}f}"


def parse_coordinates(coords_string: str) -> Tuple[float, float]:
    """
    Parse a coordinate string into latitude and longitude.

    Args:
        coords_string: String like "37.422476, -122.084250" or "37.422476,-122.084250"

    Returns:
        Tuple of (latitude, longitude)

    Raises:
        ValueError: If string cannot be parsed
    """
    try:
        parts = coords_string.replace(" ", "").split(",")
        if len(parts) != 2:
            raise ValueError("Coordinate string must have exactly 2 values")

        latitude = float(parts[0])
        longitude = float(parts[1])

        if not (-90 <= latitude <= 90):
            raise ValueError("Latitude must be between -90 and 90")
        if not (-180 <= longitude <= 180):
            raise ValueError("Longitude must be between -180 and 180")

        return (latitude, longitude)

    except (ValueError, IndexError) as e:
        raise ValueError(f"Invalid coordinate string: {coords_string}") from e
