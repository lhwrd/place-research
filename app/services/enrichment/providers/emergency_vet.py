"""Drive time to the nearest 24-hour emergency vet (Google Places).

For a sick pet at night, the regular vet is closed and what matters is the nearest animal
hospital that's open around the clock. One Text Search for emergency vets within 30 miles,
with opening hours, then one Distance Matrix call for the closest few by straight line.

Places count as 24-hour when Google's hours say so, or, where a place has no hours
listed, when its name does ("24 Hour", "24/7"). An emergency or urgent-care vet with set
hours is kept too, since one that closes at 10 p.m. may still be the quicker drive in the
evening. General practice vets the search also returns are dropped.
"""

import logging
import re
from typing import Any, Dict, List, Optional

from app.integrations.google_maps_api import GoogleMapsAPI
from app.integrations.google_places_api import GooglePlacesAPI
from app.utils.distance_calculator import haversine_distance

from ..base_provider import (
    BaseEnrichmentProvider,
    ProviderCategory,
    ProviderMetadata,
    ProviderResult,
)

QUERY = "24 hour emergency veterinary hospital"
PLACE_TYPE = "veterinary_care"
RADIUS_MILES = 30
SEARCH_RESULTS = 20  # the API's largest page

# Drive times looked up (each a billed Distance Matrix element)
MAX_24_HOUR = 3
MAX_LIMITED_HOURS = 2

METERS_PER_MILE = 1609.344

TWENTY_FOUR_HOUR_NAME = re.compile(r"\b24\s*(?:/\s*7|-?\s*h(?:ou)?rs?)\b", re.IGNORECASE)
EMERGENCY_NAME = re.compile(r"emergenc|urgent|critical care", re.IGNORECASE)
ER_NAME = re.compile(r"\bER\b")  # "Pet ER", but not "Ber" or "er"
CLOSED = {"CLOSED_PERMANENTLY", "CLOSED_TEMPORARILY"}

logger = logging.getLogger(__name__)


class EmergencyVetProvider(BaseEnrichmentProvider):
    def __init__(self):
        self.places_api = GooglePlacesAPI()
        self.maps_api = GoogleMapsAPI()

    @property
    def metadata(self) -> ProviderMetadata:
        return ProviderMetadata(
            name="emergency_vet_provider",
            category=ProviderCategory.NEARBY_PLACES,
            description="Drive time to the nearest 24-hour emergency vet.",
            version="1.0.0",
            requires_api_key=True,
            # Text Search Enterprise (for opening hours) plus the drive times
            cost_per_call=0.035 + 0.005 * (MAX_24_HOUR + MAX_LIMITED_HOURS),
            cache_duration_days=180,
        )

    async def enrich(
        self,
        latitude: float,
        longitude: float,
        address: str,
        property_data: Optional[Dict[str, Any]] = None,
        user_preferences: Optional[Dict[str, Any]] = None,
    ) -> ProviderResult:
        """
        Returns:
            ProviderResult with vets, shortest drive first (name, address, open_24_hours,
            straight_line_m, drive_minutes, drive_miles), and radius_m. vets is empty
            when there's no emergency vet within RADIUS_MILES.
        """
        try:
            found = await self.places_api.text_search(
                lat=latitude,
                lon=longitude,
                text_query=QUERY,
                radius_miles=RADIUS_MILES,
                max_results=SEARCH_RESULTS,
                included_type=PLACE_TYPE,
                opening_hours=True,
                # An ER often shares a plaza with a general practice
                merge_departments=False,
                nearest_first=True,
            )
        except Exception as e:  # pylint: disable=broad-except
            logger.error("Error searching emergency vets for %s: %s", address, e)
            return self._failed(str(e), api_calls=1)

        candidates = emergency_vets(latitude, longitude, found)
        radius_m = round(RADIUS_MILES * METERS_PER_MILE)
        if not candidates:
            return ProviderResult(
                provider_name=self.metadata.name,
                data={"vets": [], "radius_m": radius_m},
                success=True,
                api_calls_made=1,
            )

        try:
            results = await self.maps_api.distance_matrix(
                origin=(latitude, longitude),
                destinations=[(c.pop("latitude"), c.pop("longitude")) for c in candidates],
                mode="driving",
            )
        except Exception as e:  # pylint: disable=broad-except
            logger.error("Error fetching emergency vet drive times for %s: %s", address, e)
            return self._failed(str(e), api_calls=2)

        for result in results:
            index = result.get("destination_index")
            if result.get("status") != "OK" or index is None or index >= len(candidates):
                continue
            candidates[index]["drive_minutes"] = result.get("duration_minutes")
            candidates[index]["drive_miles"] = result.get("distance_miles")
        vets = sorted(
            (c for c in candidates if c.get("drive_minutes") is not None),
            key=lambda c: c["drive_minutes"],
        )
        if not vets:
            return self._failed("No drive time to any emergency vet", api_calls=2)
        return ProviderResult(
            provider_name=self.metadata.name,
            data={"vets": vets, "radius_m": radius_m},
            success=True,
            api_calls_made=2,
        )

    def _failed(self, message: str, api_calls: int) -> ProviderResult:
        return ProviderResult(
            provider_name=self.metadata.name,
            data={},
            success=False,
            error_message=message,
            api_calls_made=api_calls,
        )

    async def validate_config(self) -> bool:
        return await self.places_api.validate_api_key()


def emergency_vets(
    latitude: float, longitude: float, found: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """The nearest few 24-hour vets and limited-hours ERs, by straight line."""
    open_all_night: List[Dict[str, Any]] = []
    limited: List[Dict[str, Any]] = []
    for place in found:
        name = place.get("name") or ""
        if place.get("latitude") is None or place.get("longitude") is None:
            continue
        if place.get("business_status") in CLOSED:
            continue
        hours_say = place.get("open_24_hours")
        open_24 = hours_say if hours_say is not None else bool(TWENTY_FOUR_HOUR_NAME.search(name))
        if not open_24 and not (EMERGENCY_NAME.search(name) or ER_NAME.search(name)):
            continue  # a general practice
        vet = {
            "name": name or None,
            "address": place.get("address"),
            "open_24_hours": open_24,
            "latitude": place["latitude"],
            "longitude": place["longitude"],
            "straight_line_m": round(
                haversine_distance(latitude, longitude, place["latitude"], place["longitude"])
            ),
        }
        (open_all_night if open_24 else limited).append(vet)

    def nearest(vets: List[Dict[str, Any]], n: int) -> List[Dict[str, Any]]:
        return sorted(vets, key=lambda v: v["straight_line_m"])[:n]

    return nearest(open_all_night, MAX_24_HOUR) + nearest(limited, MAX_LIMITED_HOURS)
