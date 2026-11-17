"""Fetch a Zillow listing page and pull out the property object Zillow embeds in it.

There's no Zillow API for this. The listing page is server-rendered with a __NEXT_DATA__
script holding the same property object the app uses: price, facts, description, photos.
Zillow's bot protection (PerimeterX) serves a captcha instead of the page to clients that
don't look like a browser, and may do so to us at any time, so fetching is best-effort:
callers keep whatever listing data they already have when it fails.
"""

import json
import logging
import re
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import httpx

from app.integrations.usage import usage_hooks
from app.services.zillow_listing import find_zillow_property, parse_zpid

logger = logging.getLogger(__name__)

SERVICE_NAME = "zillow"
ALLOWED_HOSTS = ("www.zillow.com", "zillow.com")
PHOTO_HOST = "photos.zillowstatic.com"

# A browser's headers; Zillow serves its captcha to anything announcing itself as a script
BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}
NEXT_DATA = re.compile(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.S)

# The property object is ~150 KB, mostly nearby homes, ads and five sizes of every photo.
# These are the keys worth keeping.
KEPT_KEYS = frozenset(
    {
        "zpid",
        "address",
        "streetAddress",
        "city",
        "state",
        "zipcode",
        "latitude",
        "longitude",
        "price",
        "baseRent",
        "currency",
        "homeStatus",
        "homeType",
        "bedrooms",
        "bathrooms",
        "livingArea",
        "lotAreaValue",
        "lotAreaUnits",
        "lotSize",
        "yearBuilt",
        "description",
        "resoFacts",
        "homeInsights",
        "daysOnZillow",
        "timeOnZillow",
        "rentZestimate",
        "zestimate",
        "priceHistory",
        "attributionInfo",
        "postingContact",
        "brokerageName",
        "specialOffers",
        "virtualTourUrl",
        "photoCount",
        "originalPhotos",
        "responsivePhotos",
    }
)
# Widest photo to keep a link to; Zillow's next size up is the multi-MB original
MAX_PHOTO_WIDTH = 1536
TIMEOUT_SECONDS = 20.0


class ZillowFetchError(Exception):
    """The listing page couldn't be fetched or had no property data."""


def is_zillow_listing_url(url: str) -> bool:
    parsed = urlparse(url or "")
    return parsed.scheme in ("http", "https") and (parsed.hostname or "").lower() in ALLOWED_HOSTS


def is_zillow_photo_url(url: str) -> bool:
    parsed = urlparse(url or "")
    return parsed.scheme == "https" and (parsed.hostname or "").lower() == PHOTO_HOST


class ZillowPageClient:
    """Fetches listing pages and Zillow-hosted photos."""

    def __init__(self, client: Optional[httpx.AsyncClient] = None):
        self._client = client

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=TIMEOUT_SECONDS,
                follow_redirects=True,
                headers=BROWSER_HEADERS,
                event_hooks=usage_hooks(lambda: SERVICE_NAME),
            )
        return self._client

    async def fetch_property(self, url: str) -> Dict[str, Any]:
        """
        The listing's property object, trimmed to KEPT_KEYS.

        Raises:
            ZillowFetchError: Not a Zillow URL, blocked, or no property data on the page
        """
        if not is_zillow_listing_url(url):
            raise ZillowFetchError(f"Not a Zillow listing URL: {url}")
        try:
            response = await self.client.get(url)
        except httpx.HTTPError as e:
            raise ZillowFetchError(f"Request failed: {type(e).__name__}") from e
        # Redirects must stay on Zillow (e.g. a removed listing redirecting elsewhere)
        if not is_zillow_listing_url(str(response.url)):
            raise ZillowFetchError(f"Redirected off Zillow to {response.url.host}")
        if "px-captcha" in response.text:
            raise ZillowFetchError("Blocked by Zillow's bot check (captcha)")
        if response.status_code != 200:
            raise ZillowFetchError(f"HTTP {response.status_code}")

        prop = property_from_html(response.text, zpid=parse_zpid(url))
        if prop is None:
            raise ZillowFetchError("No property data on the page")
        logger.info("Fetched Zillow listing zpid=%s", prop.get("zpid"))
        return prop

    async def fetch_photo(self, url: str) -> httpx.Response:
        """Download a photo; only Zillow's photo host is allowed."""
        if not is_zillow_photo_url(url):
            raise ZillowFetchError(f"Not a Zillow photo URL: {url}")
        return await self.client.get(url)

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()


def property_from_html(html: str, zpid: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """The trimmed property object from a listing page's __NEXT_DATA__, or None."""
    match = NEXT_DATA.search(html or "")
    if not match:
        return None
    try:
        data = json.loads(match.group(1))
    except ValueError:
        return None
    prop = find_zillow_property(data, zpid)
    return trim_property(prop) if prop else None


def trim_property(prop: Dict[str, Any]) -> Dict[str, Any]:
    """Keep KEPT_KEYS, and one size of each photo."""
    trimmed = {k: v for k, v in prop.items() if k in KEPT_KEYS}
    photos = prop.get("originalPhotos") or prop.get("responsivePhotos")
    trimmed.pop("responsivePhotos", None)
    if isinstance(photos, list):
        trimmed["originalPhotos"] = _trim_photos(photos)
    reso = trimmed.get("resoFacts")
    if isinstance(reso, dict):
        # Mostly nulls, empty lists and False
        trimmed["resoFacts"] = {k: v for k, v in reso.items() if v not in (None, "", [], {})}
    return trimmed


def _trim_photos(photos: List[Any]) -> List[Dict[str, Any]]:
    trimmed = []
    for photo in photos:
        if not isinstance(photo, dict):
            continue
        sources = (photo.get("mixedSources") or {}).get("jpeg") or []
        fitting = [
            s
            for s in sources
            if isinstance(s, dict) and s.get("url") and (s.get("width") or 0) <= MAX_PHOTO_WIDTH
        ]
        if not fitting:
            continue
        best = max(fitting, key=lambda s: s.get("width") or 0)
        trimmed.append(
            {
                "caption": photo.get("caption") or "",
                "mixedSources": {"jpeg": [{"url": best["url"], "width": best.get("width")}]},
            }
        )
    return trimmed
