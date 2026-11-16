import math

from shapely.geometry import Point
from shapely.geometry.base import BaseGeometry
from shapely.ops import transform


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate the great circle distance between two points
    on the earth (specified in decimal degrees) in meters.
    """
    # Convert decimal degrees to radians
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])

    # Haversine formula
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    c = 2 * math.asin(math.sqrt(a))

    # Radius of earth in meters
    r = 6371000
    return c * r


def geometry_distance_m(latitude: float, longitude: float, geometry: BaseGeometry) -> float:
    """
    Meters from a point to a shapely geometry in WGS84 (0 if the point is inside it).

    Projects onto a flat plane centred on the point, which is accurate to well under 1%
    within a few kilometers: the distances the providers care about.
    """
    meters_per_deg_lat = 110_950.0
    meters_per_deg_lon = 111_320.0 * math.cos(math.radians(latitude))

    def to_local(x, y, z=None):
        return (x - longitude) * meters_per_deg_lon, (y - latitude) * meters_per_deg_lat

    return float(transform(to_local, geometry).distance(Point(0, 0)))
