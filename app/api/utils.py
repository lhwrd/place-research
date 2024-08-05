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


def seconds_to_human_readable(seconds: int):
    """Convert seconds to a human-readable format"""
    hours = seconds_to_hours(seconds)
    minutes = int((seconds % 3600) / 60)
    if hours == 0:
        return f"{minutes} minutes"

    return f"{hours} hours, {minutes} minutes"
