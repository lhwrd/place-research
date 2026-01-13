"""Geocoding service for converting addresses to coordinates and vice versa."""

import logging
from typing import Any, Dict, List, Optional

from app.db.database import SessionLocal
from app.exceptions import GeocodingFailedError, InvalidAddressError
from app.integrations.google_maps_api import GoogleMapsAPI
from app.services.cache_service import CacheService

logger = logging.getLogger(__name__)


class GeocodingService:
    """
    Service for geocoding addresses and reverse geocoding coordinates.

    Features:
    - Address to coordinates (geocoding)
    - Coordinates to address (reverse geocoding)
    - Address validation and normalization
    - Automatic caching to reduce API calls
    - Component-based geocoding (city, state, zip)
    - Batch geocoding support
    """

    # Cache duration for geocoding results (90 days - addresses don't change)
    GEOCODING_CACHE_TTL_DAYS = 90

    def __init__(self):
        """Initialize geocoding service."""
        self.maps_api = GoogleMapsAPI()
        self._cache_service: Optional[CacheService] = None

    @property
    def cache_service(self) -> CacheService:
        """Get or create cache service instance."""
        if self._cache_service is None:
            db = SessionLocal()
            self._cache_service = CacheService(db)
        return self._cache_service

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

    async def reverse_geocode(
        self, latitude: float, longitude: float, use_cache: bool = True
    ) -> Optional[Dict[str, Any]]:
        """
        Reverse geocode coordinates to get address.

        Args:
            latitude: Latitude
            longitude: Longitude
            use_cache: Whether to use cached results

        Returns:
            Dictionary with address information or None if not found

        Example:
            result = await geocoding_service.reverse_geocode(37.4224764, -122.0842499)
            # Returns same structure as geocode_address
        """
        # Validate coordinates
        if not self._validate_coordinates(latitude, longitude):
            logger.error(f"Invalid coordinates: ({latitude}, {longitude})")
            return None

        # Round coordinates for cache consistency
        lat_rounded = round(latitude, 6)
        lon_rounded = round(longitude, 6)

        # Check cache
        if use_cache:
            cache_key = self._generate_reverse_geocode_cache_key(lat_rounded, lon_rounded)
            cached_result = await self.cache_service.get(cache_key)

            if cached_result:
                logger.debug(f"Reverse geocoding cache hit for: ({lat_rounded}, {lon_rounded})")
                return cached_result

        # Call Google Maps API
        try:
            result = await self.maps_api.reverse_geocode(
                latitude=lat_rounded, longitude=lon_rounded
            )

            if result and use_cache:
                # Cache result
                cache_key = self._generate_reverse_geocode_cache_key(lat_rounded, lon_rounded)
                await self.cache_service.set(
                    key=cache_key, value=result, ttl_days=self.GEOCODING_CACHE_TTL_DAYS
                )

            logger.info(f"Reverse geocoded coordinates: ({latitude}, {longitude})")

            return result

        except Exception as e:
            logger.error(f"Reverse geocoding failed for ({latitude}, {longitude}): {str(e)}")
            return None

    async def geocode_batch(
        self, addresses: List[str], components: Optional[Dict[str, str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Geocode multiple addresses in batch.

        Args:
            addresses: List of addresses to geocode
            components:  Optional component filters applied to all addresses

        Returns:
            List of geocoding results (same order as input)

        Note:
            Failed geocoding attempts will return None in the results list.
        """
        results = []

        for address in addresses:
            try:
                result = await self.geocode_address(address=address, components=components)
                results.append(result)
            except Exception as e:
                logger.warning(f"Batch geocoding failed for '{address}': {str(e)}")
                results.append(None)

        logger.info(
            f"Batch geocoded {len(addresses)} addresses ({sum(1 for r in results if r)} successful)"
        )

        return results

    async def validate_address(self, address: str, strict: bool = False) -> Dict[str, Any]:
        """
        Validate an address and return detailed validation results.

        Args:
            address: Address to validate
            strict: If True, only accept addresses with exact street numbers

        Returns:
            Dictionary with validation results:
            {
                "valid": bool,
                "formatted_address": str,
                "confidence": str,  # "rooftop", "range_interpolated", "geometric_center", "approximate"
                "partial_match": bool,
                "components_complete": bool
            }
        """
        try:
            result = await self.geocode_address(address)

            # Determine confidence level based on location type
            # Note: Google Maps API doesn't always return location_type in our current implementation
            # You may need to enhance the GoogleMapsAPI to include this
            confidence = "rooftop"  # Default assumption

            # Check if it's a partial match (address components might be missing)
            partial_match = False
            if result.get("formatted_address"):
                # Simple heuristic: if formatted address is very different from input, it's partial
                input_parts = set(address.lower().split())
                formatted_parts = set(result["formatted_address"].lower().split())
                common_parts = input_parts.intersection(formatted_parts)
                partial_match = len(common_parts) < len(input_parts) * 0.5

            # Check component completeness
            required_components = ["city", "state", "zip_code"]
            components_complete = all(result.get(comp) for comp in required_components)

            valid = True

            # Strict validation
            if strict:
                # In strict mode, require full address with street number
                if partial_match or not components_complete:
                    valid = False

                # Check for street number in formatted address
                import re

                if not re.match(r"^\d+\s", result.get("formatted_address", "")):
                    valid = False

            return {
                "valid": valid,
                "formatted_address": result.get("formatted_address"),
                "latitude": result.get("latitude"),
                "longitude": result.get("longitude"),
                "confidence": confidence,
                "partial_match": partial_match,
                "components_complete": components_complete,
                "components": {
                    "city": result.get("city"),
                    "state": result.get("state"),
                    "zip_code": result.get("zip_code"),
                    "county": result.get("county"),
                    "country": result.get("country"),
                },
            }

        except Exception as e:
            logger.error(f"Address validation failed for '{address}': {str(e)}")
            return {"valid": False, "error": str(e)}

    async def geocode_components(
        self,
        street: Optional[str] = None,
        city: Optional[str] = None,
        state: Optional[str] = None,
        zip_code: Optional[str] = None,
        country: str = "US",
    ) -> Optional[Dict[str, Any]]:
        """
        Geocode using address components instead of full address string.

        Args:
            street: Street address
            city: City name
            state: State code or name
            zip_code: ZIP/postal code
            country: Country code (default: US)

        Returns:
            Geocoding result or None if failed

        Example:
            result = await geocoding_service. geocode_components(
                street="1600 Amphitheatre Parkway",
                city="Mountain View",
                state="CA",
                zip_code="94043"
            )
        """
        # Build address from components
        address_parts = []
        if street:
            address_parts.append(street)
        if city:
            address_parts.append(city)
        if state:
            address_parts.append(state)
        if zip_code:
            address_parts.append(zip_code)

        if not address_parts:
            logger.error("No address components provided")
            return None

        address = ", ".join(address_parts)

        # Build component filters
        components = {}
        if country:
            components["country"] = country
        if zip_code:
            components["postal_code"] = zip_code

        try:
            return await self.geocode_address(
                address=address, components=components if components else None
            )
        except Exception as e:
            logger.error(f"Component geocoding failed:  {str(e)}")
            return None

    async def get_distance_between_addresses(
        self, address1: str, address2: str
    ) -> Optional[Dict[str, Any]]:
        """
        Calculate straight-line distance between two addresses.

        Args:
            address1: First address
            address2: Second address

        Returns:
            Dictionary with distance information or None if failed
            {
                "distance_miles": float,
                "from_address": str,
                "to_address": str,
                "from_coords": {"lat": float, "lon": float},
                "to_coords":  {"lat": float, "lon":  float}
            }
        """
        try:
            # Geocode both addresses
            result1 = await self.geocode_address(address1)
            result2 = await self.geocode_address(address2)

            # Calculate distance
            distance_miles = self.maps_api._calculate_distance(
                result1["latitude"],
                result1["longitude"],
                result2["latitude"],
                result2["longitude"],
            )

            return {
                "distance_miles": round(distance_miles, 2),
                "from_address": result1["formatted_address"],
                "to_address": result2["formatted_address"],
                "from_coords": {
                    "lat": result1["latitude"],
                    "lon": result1["longitude"],
                },
                "to_coords": {"lat": result2["latitude"], "lon": result2["longitude"]},
            }

        except Exception as e:
            logger.error(f"Distance calculation failed: {str(e)}")
            return None

    def normalize_address_string(self, address: str) -> str:
        """
        Normalize an address string for consistent comparison.

        This is useful for detecting duplicate addresses or comparing user input.

        Args:
            address: Address to normalize

        Returns:
            Normalized address string
        """
        return self._normalize_address(address)

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

    def _validate_coordinates(self, latitude: float, longitude: float) -> bool:
        """Validate that coordinates are within valid ranges."""
        return -90 <= latitude <= 90 and -180 <= longitude <= 180

    def _generate_geocode_cache_key(
        self, address: str, components: Optional[Dict[str, str]] = None
    ) -> str:
        """Generate cache key for geocoding request."""
        key = f"geocode:{address}"

        if components:
            comp_str = ": ".join(f"{k}={v}" for k, v in sorted(components.items()))
            key += f":{comp_str}"

        return key

    def _generate_reverse_geocode_cache_key(self, latitude: float, longitude: float) -> str:
        """Generate cache key for reverse geocoding request."""
        return f"reverse_geocode:{latitude}:{longitude}"

    async def clear_geocoding_cache(self) -> int:
        """
        Clear all geocoding cache entries.

        Returns:
            Number of cache entries cleared
        """
        # This would require additional cache service methods
        # For now, just log
        logger.info("Geocoding cache clear requested")
        return 0
