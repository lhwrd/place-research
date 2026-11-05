"""Baserow-driven property ingest and enrichment.

Baserow is the source of truth for properties. The iOS Shortcut creates rows through the
listings endpoints, and a Baserow webhook (plus a periodic sweep) asks this service to
enrich any row whose Status is New, Re-enrich or empty. Enrichment writes its results back
to the row and moves Status to Enriched or Error, which the webhook handler then ignores,
so the service's own updates never trigger another run.
"""

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import lru_cache
from typing import Any, Dict, List, Optional, Set, Tuple

from app.core.config import settings
from app.exceptions import ExternalAPIError
from app.integrations.baserow_api import BaserowAPI
from app.integrations.baserow_schema import LocationFields, PropertyFields, SettingsFields, Status
from app.services import baserow_mapper
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

# Baserow long-text cells get slow to load past this; the raw JSON is only kept for re-parsing
MAX_LISTING_JSON_CHARS = 500_000
MAX_ERROR_CHARS = 2_000


@dataclass
class ImageUpload:
    content: bytes
    filename: str
    content_type: str


class RowNotFoundError(Exception):
    """Raised when a Properties row does not exist."""


class BaserowEnrichmentService:
    """Creates listing rows, attaches photos, and enriches rows in Baserow."""

    def __init__(
        self,
        client: Optional[BaserowAPI] = None,
        geocoder: Optional[GeocodingService] = None,
        orchestrator: Optional[EnrichmentOrchestrator] = None,
    ):
        self.client = client or BaserowAPI()
        self.geocoder = geocoder or GeocodingService()
        self.orchestrator = orchestrator or EnrichmentOrchestrator()
        self.table_id = settings.baserow_properties_table_id
        self._in_progress: Set[int] = set()

    # Ingest

    async def create_listing(self, url: str, listing_json: Any = None) -> Tuple[int, bool]:
        """
        Create a Properties row for a Zillow listing, or return the existing one.

        Returns:
            (row_id, created)
        """
        zpid = parse_zpid(url)
        if zpid:
            existing = await self.client.list_rows(
                self.table_id, equals={PropertyFields.ZILLOW_ID: zpid}, include=["id"]
            )
            if existing:
                logger.info("Listing already in Baserow: zpid=%s row=%s", zpid, existing[0]["id"])
                return existing[0]["id"], False

        facts = parse_listing_json(listing_json)
        values: Dict[str, Any] = {
            PropertyFields.ADDRESS: facts.full_address or address_from_url(url) or url,
            PropertyFields.ZILLOW_URL: url,
            PropertyFields.STATUS: await self._status_option(Status.NEW),
            **baserow_mapper.listing_fields(facts),
        }
        if zpid:
            values[PropertyFields.ZILLOW_ID] = zpid
        raw = _listing_json_text(listing_json)
        if raw:
            values[PropertyFields.LISTING_JSON] = raw

        row = await self.client.create_row(self.table_id, values)
        logger.info("Created Baserow listing row %s for %s", row["id"], url)
        return row["id"], True

    async def add_images(self, row_id: int, images: List[ImageUpload]) -> int:
        """Upload images and append them to the row's Photos. Returns the new photo count."""
        row = await self._get_row(row_id)
        photos = [{"name": p["name"]} for p in row.get(PropertyFields.PHOTOS) or []]
        for image in images:
            uploaded = await self.client.upload_file(
                image.content, image.filename, image.content_type
            )
            photos.append({"name": uploaded["name"]})

        await self.client.update_row(self.table_id, row_id, {PropertyFields.PHOTOS: photos})
        return len(photos)

    # Enrichment

    async def enrich_row(self, row_id: int) -> bool:
        """
        Enrich a row if its Status asks for it.

        Returns:
            True if enrichment ran, False if the row was skipped
        """
        if row_id in self._in_progress:
            logger.info("Row %s is already being enriched; skipping", row_id)
            return False
        self._in_progress.add(row_id)
        try:
            row = await self._get_row(row_id)
            status = row_status(row)
            if not needs_enrichment(status):
                return False

            await self.client.update_row(
                self.table_id,
                row_id,
                {PropertyFields.STATUS: await self._status_option(Status.ENRICHING)},
            )
            try:
                fields = await self._enrich(row, use_cached=status != Status.RE_ENRICH)
            except Exception as e:  # pylint: disable=broad-except
                logger.error("Enrichment failed for row %s: %s", row_id, e, exc_info=True)
                await self.client.update_row(
                    self.table_id,
                    row_id,
                    {
                        PropertyFields.STATUS: await self._status_option(Status.ERROR),
                        PropertyFields.ERROR: str(e)[:MAX_ERROR_CHARS],
                    },
                )
                return True

            fields[PropertyFields.STATUS] = await self._status_option(Status.ENRICHED)
            fields[PropertyFields.ERROR] = ""
            await self.client.update_row(self.table_id, row_id, fields)
            logger.info("Enriched Baserow row %s", row_id)
            return True
        finally:
            self._in_progress.discard(row_id)

    async def sweep(self) -> int:
        """Enrich every row that needs it (catches missed webhooks). Returns rows enriched."""
        rows = await self.client.list_rows(self.table_id, include=[PropertyFields.STATUS])
        enriched = 0
        for row in rows:
            if needs_enrichment(row_status(row)) and await self.enrich_row(row["id"]):
                enriched += 1
        if enriched:
            logger.info("Baserow sweep enriched %d rows", enriched)
        return enriched

    async def _enrich(self, row: Dict[str, Any], use_cached: bool) -> Dict[str, Any]:
        facts = parse_listing_json(row.get(PropertyFields.LISTING_JSON))
        address = row.get(PropertyFields.ADDRESS) or facts.full_address
        if not address:
            raise ValueError("Row has no address")

        latitude, longitude = facts.latitude, facts.longitude
        if latitude is None or longitude is None:
            geocoded = await self.geocoder.geocode_address(address)
            latitude, longitude = geocoded["latitude"], geocoded["longitude"]

        preferences = await self.load_preferences()
        result = await self.orchestrator.enrich(
            latitude=latitude,
            longitude=longitude,
            address=address,
            property_data=_property_data(facts),
            user_preferences=preferences,
            use_cached=use_cached,
        )

        return {
            **baserow_mapper.listing_fields(facts),
            **baserow_mapper.enrichment_fields(
                result.get("enrichment_data", {}),
                latitude=latitude,
                longitude=longitude,
                enriched_at=datetime.now(timezone.utc),
            ),
        }

    # Preferences

    async def load_preferences(self) -> Dict[str, Any]:
        """Build provider preferences from the Baserow Settings and Locations tables."""
        preferences: Dict[str, Any] = {
            "preferred_amenities": [],
            "preferred_places": [],
            "custom_locations": [],
        }

        if settings.baserow_settings_table_id:
            rows = await self.client.list_rows(settings.baserow_settings_table_id)
            if rows:
                preferences["preferred_amenities"] = _lines(
                    rows[0].get(SettingsFields.AMENITY_TYPES)
                )
                preferences["preferred_places"] = _lines(
                    rows[0].get(SettingsFields.PREFERRED_PLACES)
                )

        if settings.baserow_locations_table_id:
            rows = await self.client.list_rows(settings.baserow_locations_table_id)
            for row in rows:
                location = await self._location_from_row(row)
                if location:
                    preferences["custom_locations"].append(location)
            preferences["custom_locations"].sort(key=lambda loc: (-loc.priority, loc.name))

        return preferences

    async def _location_from_row(self, row: Dict[str, Any]) -> Optional[CustomLocation]:
        name = row.get(LocationFields.NAME)
        address = row.get(LocationFields.ADDRESS)
        if not row.get(LocationFields.ACTIVE) or not name or not address:
            return None
        try:
            geocoded = await self.geocoder.geocode_address(address)
        except Exception as e:  # pylint: disable=broad-except
            logger.warning("Skipping location %r: could not geocode %r: %s", name, address, e)
            return None

        location_type = row.get(LocationFields.TYPE)
        return CustomLocation(
            id=row["id"],
            name=name,
            location_type=location_type.get("value") if isinstance(location_type, dict) else None,
            address=address,
            latitude=geocoded["latitude"],
            longitude=geocoded["longitude"],
            priority=int(row.get(LocationFields.PRIORITY) or 0),
            city=geocoded.get("city"),
            state=geocoded.get("state"),
        )

    # Helpers

    async def _get_row(self, row_id: int) -> Dict[str, Any]:
        try:
            return await self.client.get_row(self.table_id, row_id)
        except ExternalAPIError as e:
            if e.details.get("api_status_code") == 404:
                raise RowNotFoundError(row_id) from e
            raise

    async def _status_option(self, value: str) -> int:
        return await self.client.select_option_id(self.table_id, PropertyFields.STATUS, value)


def row_status(row: Dict[str, Any]) -> Optional[str]:
    """The row's Status label (single selects come back as {"id", "value", "color"})."""
    status = row.get(PropertyFields.STATUS)
    return status.get("value") if isinstance(status, dict) else status


def needs_enrichment(status: Optional[str]) -> bool:
    """Rows added by hand in Baserow have no Status yet; treat them as New."""
    return status is None or status in Status.ACTIONABLE


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
        logger.warning("Listing JSON is %d chars; not storing it in Baserow", len(text))
        return None
    return text


def _lines(value: Optional[str]) -> List[str]:
    return [line.strip() for line in (value or "").splitlines() if line.strip()]


@lru_cache(maxsize=1)
def get_baserow_service() -> BaserowEnrichmentService:
    """Process-wide service, so the in-progress guard and field cache are shared."""
    return BaserowEnrichmentService()
