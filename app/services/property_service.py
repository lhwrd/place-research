"""Property ingest and enrichment.

Properties come from the iOS Shortcut (a Zillow URL plus scraped listing JSON) or from the
web UI (a Zillow URL or a plain address). Each new property is enriched in the background:
fetch the Zillow listing page (price, description, first photo), geocode, run every provider,
and store each provider's data on the row. A provider that fails keeps its previous data,
so a flaky API never blanks a property; so does a Zillow page that can't be fetched.

The stored results are the cache. Enriching again only calls the providers whose result
is missing, failed last time, is older than the provider's cache_duration_days, or was
computed from settings that have since changed; several providers are billed per call.
"""

import asyncio
import json
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from pathlib import PurePosixPath
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple
from urllib.parse import urlparse

import httpx

from app.core.config import settings
from app.db import Database, PropertyStatus, get_database
from app.db.database import LOCATION_GEOCODE_COLUMNS
from app.integrations.zillow_page import (
    ZillowFetchError,
    ZillowPageClient,
    is_zillow_listing_url,
)
from app.services.enrichment.orchestrator import EnrichmentOrchestrator
from app.services.enrichment.providers.driving_distance import CustomLocation
from app.services.geocoding_service import GeocodingService
from app.services.zillow_listing import (
    ListingFacts,
    address_from_url,
    parse_listing_json,
    parse_zpid,
    photo_urls,
)

logger = logging.getLogger(__name__)

# The raw JSON is only kept for re-parsing; don't let one huge paste bloat the database
MAX_LISTING_JSON_CHARS = 2_000_000
MAX_ERROR_CHARS = 2_000

# The listing's first photo is copied; its filename starts with this
ZILLOW_PHOTO_PREFIX = "zillow-"
# Photos tried, in order, until one is usable
MAX_PHOTO_TRIES = 3
LISTING_PHOTO_TYPES = frozenset({"image/jpeg", "image/png", "image/webp"})
MAX_LISTING_PHOTO_BYTES = 25 * 1024 * 1024
# What filling_in() calls the listing photo still downloading
PHOTOS = "listing_photo"

# How long enrichment waits for providers before storing what it has. Slower ones (public
# map servers have bad days) fill in when they finish.
PROVIDER_DEADLINE_SECONDS = 12.0

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
        listing_client: Optional[ZillowPageClient] = None,
    ):
        self.db = db or get_database()
        self.geocoder = geocoder or GeocodingService()
        self.orchestrator = orchestrator or EnrichmentOrchestrator()
        self.listing_client = listing_client or ZillowPageClient()
        self._in_progress: Set[int] = set()
        # Properties stored at the deadline with results still to come -> what's pending
        self._filling: Dict[int, List[str]] = {}
        self._background: Set[asyncio.Task] = set()

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

        Stores what has arrived once PROVIDER_DEADLINE_SECONDS pass, so the property can be
        looked at; providers still running then (and the listing photo, if still downloading) fill
        in afterward, in the background. Until they do, the property is busy (is_busy) and
        another enrichment of it is skipped.

        Args:
            use_cached: Keep stored provider results that are still good and only run the
                rest. False runs every provider.

        Returns:
            True if enrichment ran, False if the property is missing or already running
        """
        if property_id in self._in_progress:
            logger.info("Property %s is already being enriched; skipping", property_id)
            return False
        self._in_progress.add(property_id)
        finishing_later = False
        try:
            prop = self.db.get_property(property_id)
            if prop is None:
                return False

            self.db.update_property(property_id, {"status": PropertyStatus.ENRICHING})
            photos: Optional[asyncio.Task] = None
            try:
                listing_error, photo_list = await self._refresh_listing(prop)
                if photo_list:
                    # Downloads while the providers run
                    photos = asyncio.create_task(
                        self._import_listing_photos(property_id, photo_list)
                    )
                prop = self.db.get_property(property_id) or prop
                values, late = await self._enrich(prop, use_cached=use_cached)
                values["error"] = _join_errors([listing_error, values.get("error")])
            except Exception as e:  # pylint: disable=broad-except
                logger.error("Enrichment failed for property %s: %s", property_id, e, exc_info=True)
                self.db.update_property(
                    property_id,
                    {"status": PropertyStatus.ERROR, "error": str(e)[:MAX_ERROR_CHARS]},
                )
                if photos is not None:
                    await photos
                return True

            self.db.update_property(property_id, values)
            waiting = list((late or {}).get("names") or [])
            if photos is not None and not photos.done():
                waiting.append(PHOTOS)
            if waiting:
                logger.info("Enriched property %s; still waiting on %s", property_id, waiting)
                self._filling[property_id] = waiting
                task = asyncio.create_task(self._finish_later(property_id, late, photos))
                self._background.add(task)
                task.add_done_callback(self._background.discard)
                finishing_later = True
            else:
                if photos is not None:
                    await photos  # done: just collects it
                logger.info("Enriched property %s", property_id)
            return True
        finally:
            if not finishing_later:
                self._in_progress.discard(property_id)

    def is_busy(self, property_id: int) -> bool:
        """Whether the property is being enriched, including late results still filling in."""
        return property_id in self._in_progress

    def filling_in(self, property_id: int) -> List[str]:
        """What the property's enrichment is still waiting on after storing the rest."""
        return list(self._filling.get(property_id) or [])

    async def wait_for_background(self) -> None:
        """Wait for late results still filling in (for tests and shutdown)."""
        while self._background:
            await asyncio.gather(*self._background, return_exceptions=True)

    async def _finish_later(
        self,
        property_id: int,
        late: Optional[Dict[str, Any]],
        photos: Optional[asyncio.Task],
    ) -> None:
        """Store providers that missed the deadline, once they finish."""
        try:
            if photos is not None:
                await photos
            if late is not None:
                response = await late["task"]
                self._store_late_results(property_id, late, response.get("enrichment_data") or {})
            logger.info("Property %s: late results stored", property_id)
        except Exception as e:  # pylint: disable=broad-except
            logger.error(
                "Storing late results failed for property %s: %s", property_id, e, exc_info=True
            )
        finally:
            self._filling.pop(property_id, None)
            self._in_progress.discard(property_id)

    def _store_late_results(
        self, property_id: int, late: Dict[str, Any], results: Dict[str, Any]
    ) -> None:
        prop = self.db.get_property(property_id)
        if prop is None:
            return
        if (prop.get("latitude"), prop.get("longitude")) != late["location"]:
            # The address was edited meanwhile: these are for the old location
            logger.info("Property %s moved; dropping late results", property_id)
            return
        enrichment, runs, failed = _apply_results(prop, results, late["providers"])
        # Earlier lines for these providers are replaced; the rest (including the listing's)
        # stay
        kept = [
            line
            for line in (prop.get("error") or "").splitlines()
            if line.split(":", 1)[0] not in results
        ]
        self.db.update_property(
            property_id,
            {
                **_parcel_columns(enrichment.get("parcel_provider"), prop),
                "enrichment": enrichment,
                "enrichment_meta": runs,
                "error": _join_errors(kept + failed),
            },
        )

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

    async def _refresh_listing(self, prop: Dict[str, Any]) -> Tuple[Optional[str], List[str]]:
        """
        Fetch the property's Zillow page and store its listing data.

        Runs on every enrichment, so the price and availability stay current. A page that
        can't be fetched (Zillow's bot check, a removed listing) keeps the stored data.

        Returns:
            (a line for the property's failures or None, the listing's photo URLs to copy)
        """
        url = prop.get("zillow_url")
        if not settings.zillow_fetch_enabled or not url or not is_zillow_listing_url(url):
            return None, []
        try:
            listing = await self.listing_client.fetch_property(url)
        except ZillowFetchError as e:
            logger.warning("Property %s: could not fetch Zillow listing: %s", prop["id"], e)
            return f"zillow_listing: {e}", []

        facts = parse_listing_json(listing)
        values: Dict[str, Any] = {
            "listing_json": _listing_json_text(listing),
            **_listing_columns(facts),
        }
        # Replace the address guessed from the URL, but never one typed in
        if facts.full_address and prop.get("address") in (address_from_url(url), url):
            values["address"] = facts.full_address
        self.db.update_property(prop["id"], values)
        return None, photo_urls(listing)

    async def _import_listing_photos(self, property_id: int, urls: List[str]) -> int:
        """
        Copy the listing's first photo into the property's photos. Returns how many were
        added (0 or 1).

        Only once (listing_photo_copied), so a photo you deleted doesn't come back on the
        next enrichment; properties from before that flag count as copied if they have any
        Zillow photo. A photo that can't be used is skipped for the next one, up to
        MAX_PHOTO_TRIES. Never raises.
        """
        try:
            prop = self.db.get_property(property_id) or {}
            if prop.get("listing_photo_copied") or any(
                f.startswith(ZILLOW_PHOTO_PREFIX) for f in self.db.photo_filenames(property_id)
            ):
                return 0
            for url in urls[:MAX_PHOTO_TRIES]:
                try:
                    response = await self.listing_client.fetch_photo(url)
                except (ZillowFetchError, httpx.HTTPError) as e:
                    logger.warning("Property %s: skipping listing photo: %s", property_id, e)
                    continue
                content_type = (
                    response.headers.get("content-type", "").split(";")[0].strip().lower()
                )
                content = response.content
                if (
                    response.status_code != 200
                    or content_type not in LISTING_PHOTO_TYPES
                    or not content
                    or len(content) > MAX_LISTING_PHOTO_BYTES
                ):
                    logger.warning(
                        "Property %s: skipping listing photo (HTTP %s, %s, %d bytes)",
                        property_id,
                        response.status_code,
                        content_type or "no type",
                        len(content),
                    )
                    continue
                name = PurePosixPath(urlparse(url).path).name or "1.jpg"
                self.db.add_photo(property_id, ZILLOW_PHOTO_PREFIX + name, content_type, content)
                self.db.update_property(property_id, {"listing_photo_copied": 1})
                logger.info("Property %s: copied the listing photo", property_id)
                return 1
            return 0
        except Exception as e:  # pylint: disable=broad-except
            logger.error("Property %s: copying the listing photo failed: %s", property_id, e)
            return 0

    async def _enrich(
        self, prop: Dict[str, Any], use_cached: bool
    ) -> Tuple[Dict[str, Any], Optional[Dict[str, Any]]]:
        """
        Run the providers that are due, until the deadline.

        Returns:
            (the property's new values, None or what _finish_later needs for the providers
            still running: {"task", "names", "providers", "location"})
        """
        facts = parse_listing_json(prop.get("listing_json"))
        address = prop.get("address") or facts.full_address
        if not address:
            raise ValueError("Property has no address")

        latitude, longitude = facts.latitude, facts.longitude
        if latitude is None or longitude is None:
            # Geocoded on an earlier run (editing the address clears these)
            latitude, longitude = prop.get("latitude"), prop.get("longitude")
        if latitude is None or longitude is None:
            geocoded = await self.geocoder.geocode_address(address)
            latitude, longitude = geocoded["latitude"], geocoded["longitude"]
        latitude, longitude = round(latitude, 6), round(longitude, 6)
        moved = (latitude, longitude) != (prop.get("latitude"), prop.get("longitude"))

        preferences = await self.load_preferences()
        providers = self.orchestrator.provider_info(preferences)
        now = datetime.now(timezone.utc)
        runs = _previous_runs(prop)
        to_run = [
            name
            for name, info in providers.items()
            if not use_cached or moved or not _is_fresh(runs.get(name), info, now)
        ]
        logger.info(
            "Property %s: running %d of %d providers", prop["id"], len(to_run), len(providers)
        )

        results: Dict[str, Any] = {}
        late = None
        if to_run:
            result = await self.orchestrator.enrich(
                latitude=latitude,
                longitude=longitude,
                address=address,
                property_data=_property_data(facts),
                user_preferences=preferences,
                # What to reuse was decided above; the orchestrator's own cache doesn't
                # know about settings changes
                use_cached=False,
                provider_filter=to_run,
                deadline_seconds=PROVIDER_DEADLINE_SECONDS,
            )
            results = result.get("enrichment_data") or {}
            if result.get("late") is not None:
                late = {
                    "task": result["late"],
                    "names": (result.get("metadata") or {}).get("pending_providers") or [],
                    "providers": providers,
                    "location": (latitude, longitude),
                }

        enrichment, runs, failed = _apply_results(prop, results, providers, runs)
        listing = _listing_columns(facts)
        return {
            **_parcel_columns(enrichment.get("parcel_provider"), {**prop, **listing}),
            **listing,
            "latitude": latitude,
            "longitude": longitude,
            "enrichment": enrichment,
            "enrichment_meta": runs,
            "enriched_at": now.isoformat(timespec="seconds"),
            "status": PropertyStatus.ENRICHED,
            # Partial failures are worth seeing, but don't make the property an Error
            "error": _join_errors(failed),
        }, late

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
        geocoded = row
        if row.get("latitude") is None or row.get("longitude") is None:
            # First use of this address: geocode it once and keep the answer on the row
            try:
                found = await self.geocoder.geocode_address(row["address"])
            except Exception as e:  # pylint: disable=broad-except
                logger.warning(
                    "Skipping location %r: could not geocode %r: %s",
                    row["name"],
                    row["address"],
                    e,
                )
                return None
            geocoded = {column: found.get(column) for column in LOCATION_GEOCODE_COLUMNS}
            self.db.update_location(row["id"], geocoded)
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


def _previous_runs(prop: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """
    Provider name -> {"at", "ok", "inputs"} for each provider's latest run.

    Properties enriched before runs were recorded only have the property's enriched_at and
    its list of failures, so every stored result gets that time and unknown inputs (which
    reruns the providers that depend on settings, once).
    """
    recorded = prop.get("enrichment_meta")
    if recorded:
        return dict(recorded)
    failed = {line.split(":", 1)[0] for line in (prop.get("error") or "").splitlines()}
    return {
        name: {"at": prop.get("enriched_at"), "ok": name not in failed, "inputs": None}
        for name in prop.get("enrichment") or {}
    }


def _apply_results(
    prop: Dict[str, Any],
    results: Dict[str, Any],
    providers: Dict[str, Dict[str, Any]],
    runs: Optional[Dict[str, Dict[str, Any]]] = None,
) -> Tuple[Dict[str, Any], Dict[str, Dict[str, Any]], List[str]]:
    """
    Merge provider results into the property's stored ones. A provider keeps its previous
    data unless it succeeded this time.

    Returns:
        (enrichment, enrichment_meta, a "name: error" line per provider that failed)
    """
    enrichment = dict(prop.get("enrichment") or {})
    runs = dict(runs if runs is not None else _previous_runs(prop))
    failed = []
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    for name, provider_result in results.items():
        succeeded = bool(provider_result.get("success"))
        if succeeded and provider_result.get("data"):
            enrichment[name] = provider_result["data"]
        elif not succeeded:
            failed.append(f"{name}: {provider_result.get('error') or 'failed'}")
        runs[name] = {
            "at": timestamp,
            "ok": succeeded,
            "inputs": (providers.get(name) or {}).get("inputs"),
        }
    return enrichment, runs, failed


def _join_errors(lines: Sequence[Optional[str]]) -> Optional[str]:
    return "\n".join(line for line in lines if line)[:MAX_ERROR_CHARS] or None


def _is_fresh(run: Optional[Dict[str, Any]], info: Dict[str, Any], now: datetime) -> bool:
    """Whether a provider's stored result can stand in for calling it again."""
    if not run or not run.get("ok") or run.get("inputs") != info.get("inputs"):
        return False
    try:
        ran_at = datetime.fromisoformat(run["at"])
    except (KeyError, TypeError, ValueError):
        return False
    if ran_at.tzinfo is None:
        ran_at = ran_at.replace(tzinfo=timezone.utc)
    return now - ran_at < timedelta(days=info.get("max_age_days") or 0)


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


def _parcel_columns(parcel: Optional[Dict[str, Any]], current: Dict[str, Any]) -> Dict[str, Any]:
    """
    Listing facts the property appraiser's record can supply, for the ones still blank.

    The listing and hand edits win: this only fills gaps (e.g. a property added by
    address). The statewide roll has living area, year built and lot, but no bedroom,
    bathroom or garage counts. Nothing is taken from a parcel picked only because it was
    nearest, which may be the neighbor's, or from a multi-unit parcel, whose living area
    is the whole building's.
    """
    if not parcel or not parcel.get("found") or parcel.get("match") == "nearest":
        return {}
    if (parcel.get("residential_units") or 0) > 1:
        return {}
    values = {
        "sqft": parcel.get("living_area_sqft"),
        "year_built": parcel.get("year_built"),
        "lot_acres": parcel.get("lot_acres"),
    }
    return {k: v for k, v in values.items() if v is not None and current.get(k) is None}


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
