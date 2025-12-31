"""Input validation utilities for place-research.

This module provides validation functions for common inputs like coordinates,
geolocation strings, and API parameters.
"""

import re
from typing import Optional, Tuple

from .exceptions import (
    InvalidCoordinatesError,
    InvalidGeolocationError,
    ValidationError,
)


def validate_geolocation(geolocation: str) -> Tuple[float, float]:
    """Validate and parse geolocation string.

    Args:
        geolocation: String in format "lat;lng" (e.g., "40.7128;-74.0060")

    Returns:
        Tuple of (latitude, longitude)

    Raises:
        InvalidGeolocationError: If format is invalid
        InvalidCoordinatesError: If coordinates are out of range
    """
    if not geolocation:
        raise ValidationError("Geolocation is required")

    # Check format
    if ";" not in geolocation:
        raise InvalidGeolocationError(geolocation)

    parts = geolocation.split(";")
    if len(parts) != 2:
        raise InvalidGeolocationError(geolocation)

    # Parse coordinates
    try:
        lat = float(parts[0].strip())
        lng = float(parts[1].strip())
    except (ValueError, AttributeError) as e:
        raise InvalidGeolocationError(geolocation) from e

    # Validate ranges
    return validate_coordinates(lat, lng)


def validate_coordinates(lat: float, lng: float) -> Tuple[float, float]:
    """Validate latitude and longitude are within valid ranges.

    Args:
        lat: Latitude (-90 to 90)
        lng: Longitude (-180 to 180)

    Returns:
        Tuple of (latitude, longitude)

    Raises:
        InvalidCoordinatesError: If coordinates are out of range
    """
    if not -90 <= lat <= 90:
        raise InvalidCoordinatesError(lat, lng)

    if not -180 <= lng <= 180:
        raise InvalidCoordinatesError(lat, lng)

    return lat, lng


def validate_address(address: Optional[str]) -> Optional[str]:
    """Validate and normalize address string.

    Args:
        address: Address string to validate

    Returns:
        Normalized address or None

    Raises:
        ValidationError: If address is invalid
    """
    if not address:
        return None

    # Remove excessive whitespace
    normalized = " ".join(address.split())

    # Check minimum length
    if len(normalized) < 3:
        raise ValidationError(
            "Address too short (minimum 3 characters)", field="address", value=address
        )

    # Check maximum length
    if len(normalized) > 500:
        raise ValidationError(
            "Address too long (maximum 500 characters)",
            field="address",
            value=f"{address[:50]}...",
        )

    return normalized


def validate_place_id(place_id: Optional[str]) -> Optional[str]:
    """Validate place ID format.

    Args:
        place_id: Place ID to validate

    Returns:
        Validated place ID or None

    Raises:
        ValidationError: If place ID format is invalid
    """
    if not place_id:
        return None

    # Remove whitespace
    place_id = place_id.strip()

    # Check format (alphanumeric, hyphens, underscores)
    if not re.match(r"^[a-zA-Z0-9_-]+$", place_id):
        raise ValidationError(
            "Invalid place ID format. Must be alphanumeric with hyphens/underscores only",
            field="place_id",
            value=place_id,
        )

    return place_id


def validate_provider_name(provider_name: str) -> str:
    """Validate provider name.

    Args:
        provider_name: Provider name to validate

    Returns:
        Validated provider name

    Raises:
        ValidationError: If provider name is invalid
    """
    if not provider_name:
        raise ValidationError("Provider name is required", field="provider_name")

    # Normalize to lowercase
    normalized = provider_name.lower().strip()

    # Check format
    if not re.match(r"^[a-z0-9_]+$", normalized):
        raise ValidationError(
            "Invalid provider name format. Must be lowercase alphanumeric with underscores",
            field="provider_name",
            value=provider_name,
        )

    return normalized


def sanitize_error_message(message: str, max_length: int = 500) -> str:
    """Sanitize error message for safe display.

    Removes sensitive information and truncates long messages.

    Args:
        message: Error message to sanitize
        max_length: Maximum length of sanitized message

    Returns:
        Sanitized error message
    """
    if not message:
        return "Unknown error"

    # Remove potential sensitive patterns
    patterns = [
        (r'api[_-]?key["\']?\s*[:=]\s*["\']?[\w-]+', "api_key=***"),
        (r'token["\']?\s*[:=]\s*["\']?[\w-]+', "token=***"),
        (r'password["\']?\s*[:=]\s*["\']?[\w-]+', "password=***"),
        (r'secret["\']?\s*[:=]\s*["\']?[\w-]+', "secret=***"),
    ]

    sanitized = message
    for pattern, replacement in patterns:
        sanitized = re.sub(pattern, replacement, sanitized, flags=re.IGNORECASE)

    # Truncate if too long
    if len(sanitized) > max_length:
        sanitized = sanitized[: max_length - 3] + "..."

    return sanitized
