"""Parse Zillow listing URLs and the listing JSON the iOS Shortcut extracts from the page.

The Shortcut sends whatever JSON it pulled out of the listing page: schema.org JSON-LD
blocks, Zillow's embedded property object (from __NEXT_DATA__), or both. Zillow changes
its page structure without notice, so everything here is best-effort and never raises
on unexpected shapes; missing facts are simply None.
"""

import json
import re
from dataclasses import asdict, dataclass
from typing import Any, Dict, Iterator, Optional
from urllib.parse import urlparse

SQFT_PER_ACRE = 43560
ZPID_PATTERN = re.compile(r"(\d+)_zpid")
# /homedetails/111-White-Pl-Port-Orange-FL-32127/46284123_zpid/
SLUG_PATTERN = re.compile(r"/homedetails/([^/]+)/\d+_zpid")
SLUG_STATE_ZIP = re.compile(r"^(.*)-([A-Z]{2})-(\d{5})$")
# Guards against json.loads on huge non-JSON strings while walking the payload
MAX_EMBEDDED_JSON_CHARS = 5_000_000


@dataclass
class ListingFacts:
    """Facts about a listing; any of them may be missing."""

    street: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip_code: Optional[str] = None
    price: Optional[int] = None
    beds: Optional[float] = None
    baths: Optional[float] = None
    sqft: Optional[int] = None
    lot_acres: Optional[float] = None
    year_built: Optional[int] = None
    property_type: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None

    @property
    def full_address(self) -> Optional[str]:
        """Single-line address, e.g. '111 White Pl, Port Orange, FL 32127'."""
        if not self.street:
            return None
        state_zip = " ".join(p for p in (self.state, self.zip_code) if p)
        return ", ".join(p for p in (self.street, self.city, state_zip) if p)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def parse_zpid(url: str) -> Optional[str]:
    """Extract the Zillow property id from a listing URL."""
    match = ZPID_PATTERN.search(url or "")
    return match.group(1) if match else None


def address_from_url(url: str) -> Optional[str]:
    """Best-effort address from the URL slug, used when the listing JSON has none."""
    match = SLUG_PATTERN.search(urlparse(url or "").path)
    if not match:
        return None
    slug = match.group(1)
    parts = SLUG_STATE_ZIP.match(slug)
    if parts:
        street_city, state, zip_code = parts.groups()
        return f"{street_city.replace('-', ' ')}, {state} {zip_code}"
    return slug.replace("-", " ")


def parse_listing_json(raw: Any) -> ListingFacts:
    """
    Extract listing facts from the Shortcut's JSON payload.

    Args:
        raw: A JSON string, or already-decoded JSON (dict or list)

    Returns:
        ListingFacts, preferring Zillow's property object over JSON-LD where both exist
    """
    data = _decode(raw)
    if data is None:
        return ListingFacts()

    facts = ListingFacts()
    zillow = _find_zillow_property(data)
    if zillow:
        _apply_zillow_property(facts, zillow)
    for node in _walk(data):
        if "@type" in node:
            _apply_json_ld(facts, node)
    return facts


def _decode(raw: Any) -> Any:
    if isinstance(raw, (dict, list)):
        return raw
    if not isinstance(raw, str) or not raw.strip():
        return None
    try:
        return json.loads(raw)
    except ValueError:
        return None


def _walk(node: Any) -> Iterator[Dict[str, Any]]:
    """Yield every dict in a JSON tree, descending into JSON-encoded strings too."""
    if isinstance(node, dict):
        yield node
        for value in node.values():
            yield from _walk(value)
    elif isinstance(node, list):
        for item in node:
            yield from _walk(item)
    elif (
        isinstance(node, str)
        and node[:1] in "{["
        and len(node) < MAX_EMBEDDED_JSON_CHARS
        and "zpid" in node
    ):
        # Zillow nests its property cache as a JSON string inside __NEXT_DATA__
        decoded = _decode(node)
        if decoded is not None:
            yield from _walk(decoded)


def _find_zillow_property(data: Any) -> Optional[Dict[str, Any]]:
    for node in _walk(data):
        if "zpid" in node and any(k in node for k in ("price", "bedrooms", "livingArea")):
            return node
    return None


def _apply_zillow_property(facts: ListingFacts, prop: Dict[str, Any]) -> None:
    address = prop.get("address") if isinstance(prop.get("address"), dict) else {}
    facts.street = facts.street or address.get("streetAddress")
    facts.city = facts.city or address.get("city")
    facts.state = facts.state or address.get("state")
    facts.zip_code = facts.zip_code or address.get("zipcode")
    facts.price = facts.price or _to_int(prop.get("price"))
    facts.beds = facts.beds or _to_float(prop.get("bedrooms"))
    facts.baths = facts.baths or _to_float(prop.get("bathrooms"))
    facts.sqft = facts.sqft or _to_int(prop.get("livingArea"))
    facts.lot_acres = facts.lot_acres or _zillow_lot_acres(prop)
    facts.year_built = facts.year_built or _to_int(prop.get("yearBuilt"))
    facts.property_type = facts.property_type or _humanize(prop.get("homeType"))
    facts.latitude = facts.latitude or _to_float(prop.get("latitude"))
    facts.longitude = facts.longitude or _to_float(prop.get("longitude"))


def _zillow_lot_acres(prop: Dict[str, Any]) -> Optional[float]:
    value = _to_float(prop.get("lotAreaValue"))
    units = str(prop.get("lotAreaUnits") or "").lower()
    if value is not None and units:
        return round(value, 2) if "acre" in units else round(value / SQFT_PER_ACRE, 2)
    lot_sqft = _to_float(prop.get("lotSize"))
    return round(lot_sqft / SQFT_PER_ACRE, 2) if lot_sqft else None


def _apply_json_ld(facts: ListingFacts, node: Dict[str, Any]) -> None:
    address = node.get("address")
    if isinstance(address, dict):
        facts.street = facts.street or address.get("streetAddress")
        facts.city = facts.city or address.get("addressLocality")
        facts.state = facts.state or address.get("addressRegion")
        facts.zip_code = facts.zip_code or address.get("postalCode")

    floor_size = node.get("floorSize")
    if isinstance(floor_size, dict):
        facts.sqft = facts.sqft or _to_int(floor_size.get("value"))

    facts.beds = facts.beds or _to_float(node.get("numberOfBedrooms") or node.get("numberOfRooms"))
    facts.baths = facts.baths or _to_float(node.get("numberOfBathroomsTotal"))
    facts.year_built = facts.year_built or _to_int(node.get("yearBuilt"))

    offers = node.get("offers")
    if isinstance(offers, dict):
        facts.price = facts.price or _to_int(offers.get("price"))

    geo = node.get("geo")
    if isinstance(geo, dict):
        facts.latitude = facts.latitude or _to_float(geo.get("latitude"))
        facts.longitude = facts.longitude or _to_float(geo.get("longitude"))


def _to_float(value: Any) -> Optional[float]:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    match = re.search(r"-?\d[\d,]*\.?\d*", str(value))
    return float(match.group(0).replace(",", "")) if match else None


def _to_int(value: Any) -> Optional[int]:
    number = _to_float(value)
    return int(round(number)) if number is not None else None


def _humanize(value: Any) -> Optional[str]:
    """SINGLE_FAMILY -> Single family."""
    if not value:
        return None
    return str(value).replace("_", " ").capitalize()
