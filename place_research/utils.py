""" Utility functions for the place_research app"""


def miles_to_meters(miles: int) -> int:
    """Convert miles to meters"""
    return int(round(miles * 1609.34, 0))


def meters_to_miles(meters: int):
    """Convert meters to miles"""
    return int(round(meters / 1609.34, 0))


def seconds_to_hours(seconds: int):
    """Convert seconds to hours"""
    return int(round(seconds / 3600, 0))
