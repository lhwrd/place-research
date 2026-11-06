"""Geocoding service for converting addresses to coordinates and vice versa."""

import logging
from typing import Any, Dict, Optional

from app.exceptions import GeocodingFailedError, InvalidAddressError
from app.integrations.google_maps_api import GoogleMapsAPI
from app.services.cache_service import CacheService

logger = logging.getLogger(__name__)


class GeocodingService:
    """
    Service for geocoding addresses and reverse geocoding coordinates.

    Features:
    - Address to coordinates (geocoding)
    - Address normalization
    - Automatic caching to reduce API calls
    """

    # Cache duration for geocoding results (90 days - addresses don't change)
    GEOCODING_CACHE_TTL_DAYS = 90

    def __init__(self):
        """Initialize geocoding service."""
        self.maps_api = GoogleMapsAPI()
        self.cache_service = CacheService()

    async def geocode_address(
        self,
        address: str,
        components: Optional[Dict[str, str]] = None,
        use_cache: bool = True,
    ) -> Dict[str, Any]:
        """
        Geocode an address to get coordinates and formatted address.

        Args:
            address: Address to geocode
            components: Optional component filters (e.g., {"country": "US"})
            use_cache: Whether to use cached results

        Returns:
            Dictionary with geocoding results

        Raises:
            InvalidAddressError: If address format is invalid
            GeocodingFailedError: If geocoding fails

        Example:
            result = await geocoding_service.geocode_address("1600 Amphitheatre Parkway, Mountain View, CA")
            # Returns:
            # {
            #     "formatted_address": "1600 Amphitheatre Pkwy, Mountain View, CA 94043, USA",
            #     "latitude": 37.4224764,
            #     "longitude":  -122.0842499,
            #     "place_id": "ChIJ2eUgeAK6j4ARbn5u_wAGqWA",
            #     "city":  "Mountain View",
            #     "state": "CA",
            #     "zip_code": "94043",
            #     "county": "Santa Clara County",
            #     "country": "United States"
            # }
        """
        # Validate address
        if not address or len(address.strip()) < 5:
            raise InvalidAddressError(address=address, reason="Address is too short")

        # Normalize address for cache key
        normalized_address = self._normalize_address(address)

        # Check cache
        if use_cache:
            cache_key = self._generate_geocode_cache_key(normalized_address, components)
            cached_result = await self.cache_service.get(cache_key)

            if cached_result:
                logger.debug(f"Geocoding cache hit for:  {normalized_address}")
                return cached_result

        # Call Google Maps API
        try:
            result = await self.maps_api.geocode(address=normalized_address, components=components)

            if not result:
                raise GeocodingFailedError(address=address)

            # Cache result
            if use_cache:
                cache_key = self._generate_geocode_cache_key(normalized_address, components)
                await self.cache_service.set(
                    key=cache_key, value=result, ttl_days=self.GEOCODING_CACHE_TTL_DAYS
                )

            logger.info(f"Geocoded address: {address}")

            return result

        except Exception as e:
            logger.error(f"Geocoding failed for '{address}': {str(e)}")
            raise GeocodingFailedError(address=address)

    # Private helper methods

    def _normalize_address(self, address: str) -> str:
        """
        Normalize address for consistent caching and comparison.

        - Convert to lowercase
        - Remove extra whitespace
        - Standardize common abbreviations
        """
        import re

        # Convert to lowercase
        normalized = address.lower().strip()

        # Remove extra whitespace
        normalized = re.sub(r"\s+", " ", normalized)

        # Standardize common abbreviations
        abbreviations = {
            "street": "st",
            "avenue": "ave",
            "road": "rd",
            "drive": "dr",
            "lane": "ln",
            "court": "ct",
            "circle": "cir",
            "boulevard": "blvd",
            "parkway": "pkwy",
            "north": "n",
            "south": "s",
            "east": "e",
            "west": "w",
            "apartment": "apt",
            "suite": "ste",
        }

        for full, abbr in abbreviations.items():
            # Replace whole words only
            normalized = re.sub(r"\b" + full + r"\b", abbr, normalized)

        return normalized

    def _generate_geocode_cache_key(
        self, address: str, components: Optional[Dict[str, str]] = None
    ) -> str:
        """Generate cache key for geocoding request."""
        key = f"geocode:{address}"

        if components:
            comp_str = ": ".join(f"{k}={v}" for k, v in sorted(components.items()))
            key += f":{comp_str}"

        return key
