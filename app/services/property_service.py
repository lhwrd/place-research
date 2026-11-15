"""Property ingest and enrichment.

Properties come from the iOS Shortcut (a Zillow URL plus scraped listing JSON) or from the
web UI (a Zillow URL or a plain address). Each new property is enriched in the background:
geocode, run every provider, and store each provider's data on the row. A provider that
fails keeps its previous data, so a flaky API never blanks a property.
"""

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import lru_cache
from typing import Any, Dict, List, Optional, Set, Tuple

from app.db import Database, PropertyStatus, get_database
from app.services.enrichment.orchestrator import EnrichmentOrchestrator
from app.services.enrichment.providers.driving_distance import CustomLocation
from app.services.geocoding_service import GeocodingService
from app.services.zillow_listing import (
    ListingFacts,
    address_from_url,
    parse_listing_json,
    parse_zpid,
)

logger = logging.getLogger(__name__)

# The raw JSON is only kept for re-parsing; don't let one huge paste bloat the database
MAX_LISTING_JSON_CHARS = 2_000_000
MAX_ERROR_CHARS = 2_000

# Settings keys
AMENITY_TYPES = "amenity_types"
PREFERRED_PLACES = "preferred_places"


@dataclass
class ImageUpload:
    content: bytes
    filename: str
    content_type: str


class PropertyNotFoundError(Exception):
    """Raised when a property does not exist."""


class PropertyService:
    """Creates properties, attaches photos, and enriches properties."""

    def __init__(
        self,
        db: Optional[Database] = None,
        geocoder: Optional[GeocodingService] = None,
        orchestrator: Optional[EnrichmentOrchestrator] = None,
    ):
        self.db = db or get_database()
        self.geocoder = geocoder or GeocodingService()
        self.orchestrator = orchestrator or EnrichmentOrchestrator()
        self._in_progress: Set[int] = set()

    # Ingest

    def create_listing(self, url: str, listing_json: Any = None) -> Tuple[int, bool]:
        """
        Add a Zillow listing, or return the existing property for the same zpid.

        Returns:
            (property_id, created)
        """
        zpid = parse_zpid(url)
        if zpid:
            existing = self.db.find_property(zillow_id=zpid)
            if existing:
                logger.info("Listing already saved: zpid=%s property=%s", zpid, existing)
                return existing, False

        facts = parse_listing_json(listing_json)
        values: Dict[str, Any] = {
            "address": facts.full_address or address_from_url(url) or url,
            "zillow_url": url,
            "zillow_id": zpid,
            "listing_json": _listing_json_text(listing_json),
            **_listing_columns(facts),
        }
        property_id = self.db.create_property(values)
        logger.info("Created property %s for %s", property_id, url)
        return property_id, True

    def create_from_input(self, text: str) -> Tuple[int, bool]:
        """Add a property from the web form: a Zillow URL or a street address."""
        text = text.strip()
        if text.lower().startswith(("http://", "https://")):
            return self.create_listing(text)

        existing = self.db.find_property(address=text)
        if existing:
            return existing, False
        property_id = self.db.create_property({"address": text})
        logger.info("Created property %s for address %r", property_id, text)
        return property_id, True

    def add_images(self, property_id: int, images: List[ImageUpload]) -> int:
        """Store images on a property. Returns the property's new photo count."""
        if self.db.get_property(property_id) is None:
            raise PropertyNotFoundError(property_id)
        for image in images:
            self.db.add_photo(property_id, image.filename, image.content_type, image.content)
        return len(self.db.photo_ids(property_id))

    # Enrichment

    async def enrich(self, property_id: int, use_cached: bool = True) -> bool:
        """
        Enrich a property and store the results.

        Returns:
            True if enrichment ran, False if the property is missing or already running
        """
        if property_id in self._in_progress:
            logger.info("Property %s is already being enriched; skipping", property_id)
            return False
        self._in_progress.add(property_id)
        try:
            prop = self.db.get_property(property_id)
            if prop is None:
                return False

            self.db.update_property(property_id, {"status": PropertyStatus.ENRICHING})
            try:
                values = await self._enrich(prop, use_cached=use_cached)
            except Exception as e:  # pylint: disable=broad-except
                logger.error("Enrichment failed for property %s: %s", property_id, e, exc_info=True)
                self.db.update_property(
                    property_id,
                    {"status": PropertyStatus.ERROR, "error": str(e)[:MAX_ERROR_CHARS]},
                )
                return True

            self.db.update_property(property_id, values)
            logger.info("Enriched property %s", property_id)
            return True
        finally:
            self._in_progress.discard(property_id)

    async def enrich_safely(self, property_id: int, use_cached: bool = True) -> None:
        """For background tasks, whose errors would otherwise only surface as a traceback."""
        try:
            await self.enrich(property_id, use_cached=use_cached)
        except Exception as e:  # pylint: disable=broad-except
            logger.error("Background enrichment failed for %s: %s", property_id, e, exc_info=True)

    async def enrich_pending(self) -> int:
        """Enrich properties left New or Enriching (e.g. by a restart). Returns the count."""
        enriched = 0
        for property_id in self.db.property_ids_with_status(*PropertyStatus.PENDING):
            if await self.enrich(property_id):
                enriched += 1
        if enriched:
            logger.info("Enriched %d pending properties", enriched)
        return enriched

    async def _enrich(self, prop: Dict[str, Any], use_cached: bool) -> Dict[str, Any]:
        facts = parse_listing_json(prop.get("listing_json"))
        address = prop.get("address") or facts.full_address
        if not address:
            raise ValueError("Property has no address")

        latitude, longitude = facts.latitude, facts.longitude
        if latitude is None or longitude is None:
            geocoded = await self.geocoder.geocode_address(address)
            latitude, longitude = geocoded["latitude"], geocoded["longitude"]

        result = await self.orchestrator.enrich(
            latitude=latitude,
            longitude=longitude,
            address=address,
            property_data=_property_data(facts),
            user_preferences=await self.load_preferences(),
            use_cached=use_cached,
        )

        # Keep each provider's previous data unless it succeeded this time
        enrichment = dict(prop.get("enrichment") or {})
        failed = []
        for name, provider_result in (result.get("enrichment_data") or {}).items():
            if provider_result.get("success") and provider_result.get("data"):
                enrichment[name] = provider_result["data"]
            elif not provider_result.get("success"):
                failed.append(f"{name}: {provider_result.get('error') or 'failed'}")

        return {
            **_listing_columns(facts),
            "latitude": round(latitude, 6),
            "longitude": round(longitude, 6),
            "enrichment": enrichment,
            "enriched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "status": PropertyStatus.ENRICHED,
            # Partial failures are worth seeing, but don't make the property an Error
            "error": "\n".join(failed)[:MAX_ERROR_CHARS] or None,
        }

    # Preferences

    async def load_preferences(self) -> Dict[str, Any]:
        """Provider inputs from the Settings and Locations pages."""
        locations = []
        for row in self.db.list_locations(active_only=True):
            location = await self._custom_location(row)
            if location:
                locations.append(location)
        locations.sort(key=lambda loc: (-loc.priority, loc.name))

        return {
            "preferred_amenities": _lines(self.db.get_setting(AMENITY_TYPES)),
            "preferred_places": _lines(self.db.get_setting(PREFERRED_PLACES)),
            "custom_locations": locations,
        }

    async def _custom_location(self, row: Dict[str, Any]) -> Optional[CustomLocation]:
        try:
            geocoded = await self.geocoder.geocode_address(row["address"])
        except Exception as e:  # pylint: disable=broad-except
            logger.warning(
                "Skipping location %r: could not geocode %r: %s", row["name"], row["address"], e
            )
            return None
        return CustomLocation(
            id=row["id"],
            name=row["name"],
            location_type=row.get("type"),
            address=row["address"],
            latitude=geocoded["latitude"],
            longitude=geocoded["longitude"],
            priority=int(row.get("priority") or 0),
            city=geocoded.get("city"),
            state=geocoded.get("state"),
        )


def _listing_columns(facts: ListingFacts) -> Dict[str, Any]:
    """Listing facts that were found (missing ones don't overwrite stored values)."""
    values = {
        "price": facts.price,
        "beds": facts.beds,
        "baths": facts.baths,
        "sqft": facts.sqft,
        "lot_acres": facts.lot_acres,
        "year_built": facts.year_built,
        "property_type": facts.property_type,
        "garage_spaces": facts.garage_spaces,
    }
    return {k: v for k, v in values.items() if v is not None}


def _property_data(facts: ListingFacts) -> Dict[str, Any]:
    return {
        "bedrooms": facts.beds,
        "bathrooms": facts.baths,
        "square_feet": facts.sqft,
        "year_built": facts.year_built,
        "property_type": facts.property_type,
    }


def _listing_json_text(listing_json: Any) -> Optional[str]:
    if listing_json is None or listing_json == "":
        return None
    text = listing_json if isinstance(listing_json, str) else json.dumps(listing_json)
    if len(text) > MAX_LISTING_JSON_CHARS:
        logger.warning("Listing JSON is %d chars; not storing it", len(text))
        return None
    return text


def _lines(value: Optional[str]) -> List[str]:
    return [line.strip() for line in (value or "").splitlines() if line.strip()]


@lru_cache(maxsize=1)
def get_property_service() -> PropertyService:
    """Process-wide service, so the in-progress guard is shared."""
    return PropertyService()
