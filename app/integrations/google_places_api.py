"""Google Maps API integration."""

import logging
from typing import Any, Dict, List, Optional

from app.core.config import settings
from app.exceptions import GoogleMapsAPIError
from app.integrations.base_client import BaseAPIClient, retry_on_failure

logger = logging.getLogger(__name__)


class GooglePlacesAPI(BaseAPIClient):
    """
    Google Maps Places API client.

    Provides access to:
    - Places API endpoints for nearby search and place details.
    """

    # API endpoints
    NEARBY_SEARCH_ENDPOINT = "places:searchNearby"
    TEXT_SEARCH_ENDPOINT = "places:searchText"
    DETAILS_ENDPOINT = "places/"

    FIELDS = [
        "id",
        "displayName",
        "formattedAddress",
        "location",
        "primaryTypeDisplayName",
    ]

    def __init__(self):
        """Initialize Google Maps API client."""
        super().__init__(
            base_url="https://places.googleapis.com/v1",
            api_key=settings.google_maps_api_key,
            timeout=30.0,
            rate_limit_per_second=50,  # Google's default is higher, but be conservative
        )

    def _get_service_name(self) -> str:
        """Return service name."""
        return "google_places"

    def _get_auth_headers(self) -> Dict[str, str]:
        """Google Maps uses query param for auth, not headers."""
        return (
            {
                "X-Goog-Api-Key": self.api_key,
            }
            if self.api_key
            else {}
        )

    async def validate_api_key(self) -> bool:
        """Validate API key by making a simple geocoding request."""
        try:
            logger.info("Validating Google Places API key")
            result = await self.place_details(place_id="ChIJN1t_tDeuEmsRUsoyG83frY4")
            is_valid = result is not None
            logger.info(
                "Google Places API key validation: %s",
                "success" if is_valid else "failed",
            )
            return is_valid
        except GoogleMapsAPIError as e:
            logger.warning("Google Places API key validation failed: %s", str(e))
            return False

    @retry_on_failure(max_retries=3, backoff_factor=1.0)
    async def nearby_search(
        self,
        lat: float,
        lon: float,
        place_types: List[str],
        radius_miles: float = 5.0,
        max_results: int = 3,
    ) -> List[Dict[str, Any]]:
        """
        Search for nearby places of a specific type.

        Args:
            lat: Center point latitude
            lon: Center point longitude
            place_type: Type of place to search for
            radius_miles: Search radius in miles
            keyword: Optional keyword filter
            max_results: Maximum number of results to return

        Returns:
            List of nearby places with details

        Example return:
            [
                {
                    "name": "Walmart Supercenter",
                    "place_id": "ChIJN1t_tDeuEmsRUsoyG83frY4",
                    "latitude": 34.052235,
                    "longitude": -118.243683,
                    "address": "123 Main St, Los Angeles, CA 90012",
                    "type": "Grocery Store",
                },
                ...
            ]
        """
        # Convert miles to meters for API
        radius_meters = int(radius_miles * 1609.34)

        logger.info(
            "Google Places nearby search: types=%s, radius=%.1f miles (%d meters), max_results=%d",
            place_types,
            radius_miles,
            radius_meters,
            max_results,
            extra={
                "latitude": lat,
                "longitude": lon,
                "place_types": place_types,
                "radius_miles": radius_miles,
                "radius_meters": radius_meters,
                "max_results": max_results,
            },
        )

        data = {
            "includedTypes": place_types,
            "maxResultCount": max_results,
            "locationRestriction": {
                "circle": {
                    "center": {"latitude": lat, "longitude": lon},
                    "radius": radius_meters,
                }
            },
        }
        headers = {
            "X-Goog-FieldMask": ",".join(["places." + field for field in self.FIELDS]),
        }

        try:
            response_data = await self._make_request(
                "POST", self.NEARBY_SEARCH_ENDPOINT, json_data=data, headers=headers
            )
            results = response_data.get("places", [])

            logger.info(
                "Google Places nearby search returned %d results for types %s",
                len(results),
                place_types,
                extra={"result_count": len(results), "place_types": place_types},
            )
            logger.debug("Nearby search response data: %s", response_data)

            if not results:
                return []

            # Parse and enrich results
            parsed_results = []
            for place in results:
                parsed_place = self._parse_place_result(place)
                parsed_results.append(parsed_place)

            return parsed_results

        except Exception as e:
            logger.error(
                "Nearby search error for types %s at (%.6f, %.6f): %s",
                place_types,
                lat,
                lon,
                str(e),
                extra={
                    "place_types": place_types,
                    "latitude": lat,
                    "longitude": lon,
                    "error": str(e),
                },
                exc_info=True,
            )
            raise

    @retry_on_failure(max_retries=3, backoff_factor=1.0)
    async def text_search(
        self,
        lat: float,
        lon: float,
        text_query: str,
        radius_miles: float = 5.0,
        max_results: int = 3,
    ) -> List[Dict[str, Any]]:
        """
        Search for nearby places of a specific type.

        Args:
            lat: Center point latitude
            lon: Center point longitude
            text_query: Text query to search for
            radius_miles: Search radius in miles
            keyword: Optional keyword filter
            max_results: Maximum number of results to return

        Returns:
            List of nearby places with details

        Example return:
            [
                {
                    "name": "Walmart Supercenter",
                    "place_id": "ChIJN1t_tDeuEmsRUsoyG83frY4",
                    "latitude": 34.052235,
                    "longitude": -118.243683,
                    "address": "123 Main St, Los Angeles, CA 90012",
                    "type": "Grocery Store",
                },
                ...
            ]
        """
        # Convert miles to meters for API
        radius_meters = int(radius_miles * 1609.34)

        logger.info(
            "Google Places text search: query='%s', radius=%.1f miles, max_results=%d",
            text_query,
            radius_miles,
            max_results,
            extra={
                "text_query": text_query,
                "latitude": lat,
                "longitude": lon,
                "radius_miles": radius_miles,
                "max_results": max_results,
            },
        )

        data = {
            "textQuery": text_query,
            "maxResultCount": max_results,
            "locationRestriction": {
                "circle": {
                    "center": {"latitude": lat, "longitude": lon},
                    "radius": radius_meters,
                }
            },
        }
        headers = {
            "X-Goog-FieldMask": ",".join(["places." + field for field in self.FIELDS]),
        }

        try:
            response_data = await self._make_request(
                "POST", self.TEXT_SEARCH_ENDPOINT, json_data=data, headers=headers
            )

            results = response_data.get("places", [])

            logger.info(
                "Google Places text search returned %d results for query '%s'",
                len(results),
                text_query,
                extra={"result_count": len(results), "text_query": text_query},
            )

            if not results:
                return []

            # Parse and enrich results
            parsed_results = []
            for place in results:
                parsed_place = self._parse_place_result(place)
                parsed_results.append(parsed_place)

            return parsed_results

        except Exception as e:
            logger.error(
                "Text search error for query '%s' at (%.6f, %.6f): %s",
                text_query,
                lat,
                lon,
                str(e),
                extra={
                    "text_query": text_query,
                    "latitude": lat,
                    "longitude": lon,
                    "error": str(e),
                },
                exc_info=True,
            )
            raise

    @retry_on_failure(max_retries=3, backoff_factor=1.0)
    async def place_details(
        self, place_id: str, fields: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Get detailed information about a place.

        Args:
            place_id: Google Place ID
            fields: Optional list of fields to retrieve

        Returns:
            Detailed place information
        """
        fields = fields or self.FIELDS

        logger.info(
            "Google Places fetching details for place_id: %s",
            place_id,
            extra={"place_id": place_id, "fields": fields},
        )

        headers = {
            "X-Goog-FieldMask": ",".join(fields),
        }

        try:
            response_data = await self._make_request(
                "GET", self.DETAILS_ENDPOINT + place_id, headers=headers
            )

            if not response_data:
                error_msg = response_data.get("error_message", response_data.get("status"))
                logger.error(
                    "Place details failed for place_id %s: %s",
                    place_id,
                    error_msg,
                    extra={"place_id": place_id, "error_message": error_msg},
                )
                raise GoogleMapsAPIError(
                    message=f"Place details failed: {error_msg}", api_status_code=200
                )

            logger.info(
                "Successfully retrieved place details for place_id: %s",
                place_id,
                extra={"place_id": place_id},
            )
            return self._parse_place_result(response_data)

        except Exception as e:
            logger.error(
                "Place details error for place_id '%s': %s",
                place_id,
                str(e),
                extra={"place_id": place_id, "error": str(e)},
                exc_info=True,
            )
            raise

    def _parse_place_result(self, place: Dict[str, Any]) -> Dict[str, Any]:
        """Parse place result and calculate distance."""
        return {
            "name": place.get("displayName", {}).get("text"),
            "place_id": place.get("id"),
            "latitude": place.get("location", {}).get("latitude"),
            "longitude": place.get("location", {}).get("longitude"),
            "address": place.get("formattedAddress"),
            "type": place.get("primaryTypeDisplayName", {}).get("text"),
        }
