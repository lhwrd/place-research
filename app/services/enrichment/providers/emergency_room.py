"""Drive time to the nearest hospital emergency room (Google Places).

One Text Search for emergency rooms within 25 miles, with opening hours, then one
Distance Matrix call for the closest few by straight line. Freestanding ERs count: in
Florida they are hospital-run, open around the clock, and take ambulances.

Places has no emergency-room type: hospitals, their ER entrances and freestanding ERs
come back as "hospital" or "service", alongside urgent cares, ER parking lots and
physician groups. A result is kept when it is open 24/7 and named like a hospital or an
ER, or, with no hours listed, named like an ER. Urgent care, children's-only ERs and the
like are dropped.
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

QUERY = "emergency room"
RADIUS_MILES = 25
SEARCH_RESULTS = 20  # the API's largest page
MAX_ERS = 3  # drive times looked up, each a billed Distance Matrix element
# One hospital's main building and its ER entrance are one place
SAME_ER_M = 300

METERS_PER_MILE = 1609.344

ER_NAME = re.compile(r"emergenc|\bER\b|\bE\.R\.|trauma", re.IGNORECASE)
HOSPITAL_NAME = re.compile(r"hospital|medical center|\bER\b|emergenc", re.IGNORECASE)
NOT_AN_ER = re.compile(
    r"urgent|parking|garage|physicians|doctors|clinic|veterinar|animal|\bpets?\b|child|"
    r"pediatric|kids|nemours|dental|behavioral|psychiatric|rehab|hospice|surgery center|"
    r"imaging|lab\b|pharmacy",
    re.IGNORECASE,
)
CLOSED = {"CLOSED_PERMANENTLY", "CLOSED_TEMPORARILY"}

logger = logging.getLogger(__name__)


class EmergencyRoomProvider(BaseEnrichmentProvider):
    def __init__(self):
        self.places_api = GooglePlacesAPI()
        self.maps_api = GoogleMapsAPI()

    @property
    def metadata(self) -> ProviderMetadata:
        return ProviderMetadata(
            name="emergency_room_provider",
            category=ProviderCategory.SAFETY,
            description="Drive time to the nearest hospital emergency room.",
            version="1.0.0",
            requires_api_key=True,
            # Text Search Enterprise (for opening hours) plus the drive times
            cost_per_call=0.035 + 0.005 * MAX_ERS,
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
            ProviderResult with ers, shortest drive first (name, address, straight_line_m,
            drive_minutes, drive_miles), and radius_m. ers is empty when there's no ER
            within RADIUS_MILES.
        """
        try:
            found = await self.places_api.text_search(
                lat=latitude,
                lon=longitude,
                text_query=QUERY,
                radius_miles=RADIUS_MILES,
                max_results=SEARCH_RESULTS,
                opening_hours=True,
                merge_departments=False,
                nearest_first=True,
            )
        except Exception as e:  # pylint: disable=broad-except
            logger.error("Error searching emergency rooms for %s: %s", address, e)
            return self._failed(str(e), api_calls=1)

        candidates = emergency_rooms(latitude, longitude, found)
        radius_m = round(RADIUS_MILES * METERS_PER_MILE)
        if not candidates:
            return ProviderResult(
                provider_name=self.metadata.name,
                data={"ers": [], "radius_m": radius_m},
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
            logger.error("Error fetching ER drive times for %s: %s", address, e)
            return self._failed(str(e), api_calls=2)

        for result in results:
            index = result.get("destination_index")
            if result.get("status") != "OK" or index is None or index >= len(candidates):
                continue
            candidates[index]["drive_minutes"] = result.get("duration_minutes")
            candidates[index]["drive_miles"] = result.get("distance_miles")
        ers = sorted(
            (c for c in candidates if c.get("drive_minutes") is not None),
            key=lambda c: c["drive_minutes"],
        )
        if not ers:
            return self._failed("No drive time to any emergency room", api_calls=2)
        return ProviderResult(
            provider_name=self.metadata.name,
            data={"ers": ers, "radius_m": radius_m},
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


def is_emergency_room(place: Dict[str, Any]) -> bool:
    name = place.get("name") or ""
    if not name or NOT_AN_ER.search(name) or place.get("business_status") in CLOSED:
        return False
    open_24 = place.get("open_24_hours")
    if open_24 is None:  # no hours listed
        return bool(ER_NAME.search(name))
    return open_24 and bool(HOSPITAL_NAME.search(name) or ER_NAME.search(name))


def emergency_rooms(
    latitude: float, longitude: float, found: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """The nearest MAX_ERS distinct emergency rooms, by straight line."""
    ers = sorted(
        (
            {
                "name": p["name"],
                "address": p.get("address"),
                "latitude": p["latitude"],
                "longitude": p["longitude"],
                "straight_line_m": round(
                    haversine_distance(latitude, longitude, p["latitude"], p["longitude"])
                ),
            }
            for p in found
            if p.get("latitude") is not None
            and p.get("longitude") is not None
            and is_emergency_room(p)
        ),
        key=lambda er: er["straight_line_m"],
    )
    distinct: List[Dict[str, Any]] = []
    for er in ers:
        if any(
            haversine_distance(er["latitude"], er["longitude"], d["latitude"], d["longitude"])
            < SAME_ER_M
            for d in distinct
        ):
            continue
        distinct.append(er)
        if len(distinct) == MAX_ERS:
            break
    return distinct
