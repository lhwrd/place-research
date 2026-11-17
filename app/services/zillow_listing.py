"""Parse Zillow listing URLs and the listing JSON the iOS Shortcut extracts from the page.

The Shortcut sends whatever JSON it pulled out of the listing page: schema.org JSON-LD
blocks, Zillow's embedded property object (from __NEXT_DATA__), or both. Zillow changes
its page structure without notice, so everything here is best-effort and never raises
on unexpected shapes; missing facts are simply None.
"""

import json
import re
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, Iterator, List, Optional, Tuple
from urllib.parse import urlparse

SQFT_PER_ACRE = 43560
ZPID_PATTERN = re.compile(r"(\d+)_zpid")
# /homedetails/111-White-Pl-Port-Orange-FL-32127/46284123_zpid/
SLUG_PATTERN = re.compile(r"/homedetails/([^/]+)/\d+_zpid")
SLUG_STATE_ZIP = re.compile(r"^(.*)-([A-Z]{2})-(\d{5})$")
# What Zillow's rental form leaves in the brokerage field when the landlord skips it
PLACEHOLDER_NAMES = frozenset({"enter a company name"})
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
    garage_spaces: Optional[int] = None  # 0 means the listing says there's no garage
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


@dataclass
class ListingDetails:
    """What the listing says beyond the facts kept in columns: for the detail page."""

    status: Optional[str] = None  # "For rent", "Off market", ...
    description: Optional[str] = None
    # Zillow's summary of the listing: ("Pets", "Cats, Small Dogs"), ("Laundry", "In Unit")
    at_a_glance: List[Tuple[str, str]] = field(default_factory=list)
    highlights: List[str] = field(default_factory=list)  # short phrases Zillow pulls out
    fees: List[Tuple[str, str]] = field(default_factory=list)  # ("Deposit", "$2,050")
    lease_term: Optional[str] = None
    appliances: List[str] = field(default_factory=list)
    flooring: List[str] = field(default_factory=list)
    days_on_zillow: Optional[int] = None
    rent_zestimate: Optional[int] = None
    zestimate: Optional[int] = None
    listed_by: Optional[str] = None  # "Jane Doe · Acme Realty"
    contact_phone: Optional[str] = None
    photo_urls: List[str] = field(default_factory=list)

    def __bool__(self) -> bool:
        return any(asdict(self).values())


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
    zillow = find_zillow_property(data)
    if zillow:
        _apply_zillow_property(facts, zillow)
    for node in _walk(data):
        if "@type" in node:
            _apply_json_ld(facts, node)
    return facts


def parse_listing_details(raw: Any) -> ListingDetails:
    """Description, rental terms, photos etc. from Zillow's property object, if present."""
    data = _decode(raw)
    prop = find_zillow_property(data) if data is not None else None
    if not prop:
        return ListingDetails()

    reso = _dict(prop.get("resoFacts"))
    attribution = _dict(prop.get("attributionInfo"))
    contact = _dict(prop.get("postingContact"))
    description = prop.get("description")
    return ListingDetails(
        status=_humanize(prop.get("homeStatus")),
        description=description.strip() if isinstance(description, str) else None,
        at_a_glance=[
            (str(f["factLabel"]), str(f["factValue"]))
            for f in _dicts(reso.get("atAGlanceFacts"))
            if f.get("factLabel") and f.get("factValue") not in (None, "")
        ],
        highlights=_highlights(prop.get("homeInsights")),
        fees=[
            (str(f["type"]), str(f["fee"]))
            for f in _dicts(reso.get("feesAndDues"))
            if f.get("type") and f.get("fee")
        ],
        lease_term=_text(reso.get("leaseTerm")),
        appliances=_strings(reso.get("appliances")),
        flooring=_strings(reso.get("flooring")),
        days_on_zillow=_to_int(prop.get("daysOnZillow")),
        rent_zestimate=_to_int(prop.get("rentZestimate")),
        zestimate=_to_int(prop.get("zestimate")),
        listed_by=" · ".join(
            dict.fromkeys(
                n
                for n in (
                    _text(contact.get("name") or attribution.get("agentName")),
                    _text(prop.get("brokerageName") or attribution.get("brokerName")),
                )
                if n and n.lower() not in PLACEHOLDER_NAMES
            )
        )
        or None,
        contact_phone=_text(attribution.get("agentPhoneNumber")),
        photo_urls=photo_urls(prop),
    )


def photo_urls(prop: Dict[str, Any]) -> List[str]:
    """The widest JPEG of each listing photo, in listing order."""
    urls = []
    for photo in _dicts(prop.get("originalPhotos") or prop.get("responsivePhotos")):
        sources = [s for s in _dicts(_dict(photo.get("mixedSources")).get("jpeg")) if s.get("url")]
        if sources:
            best = max(sources, key=lambda s: _to_int(s.get("width")) or 0)
            urls.append(str(best["url"]))
        elif isinstance(photo.get("url"), str):
            urls.append(photo["url"])
    return list(dict.fromkeys(urls))


def _highlights(insights: Any) -> List[str]:
    """The phrases from Zillow's first insights model (the others repeat them)."""
    for group in _dicts(insights):
        for insight in _dicts(group.get("insights")):
            phrases = _strings(insight.get("phrases"))
            if phrases:
                return phrases
    return []


def _dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _dicts(value: Any) -> List[Dict[str, Any]]:
    return [v for v in value if isinstance(v, dict)] if isinstance(value, list) else []


def _strings(value: Any) -> List[str]:
    if not isinstance(value, list):
        return []
    return [str(v).strip() for v in value if isinstance(v, (str, int, float)) and str(v).strip()]


def _text(value: Any) -> Optional[str]:
    return str(value).strip() or None if isinstance(value, (str, int, float)) else None


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


def find_zillow_property(data: Any, zpid: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    Zillow's property object in a JSON tree.

    Args:
        zpid: The listing's id, when known. Nearby and similar homes have zpids and prices
            too, so with it the listing's own object wins over the first one found.
    """
    first = None
    for node in _walk(data):
        if "zpid" in node and any(k in node for k in ("price", "bedrooms", "livingArea")):
            if zpid is None or str(node["zpid"]) == str(zpid):
                return node
            first = first or node
    return first


def _apply_zillow_property(facts: ListingFacts, prop: Dict[str, Any]) -> None:
    address = prop.get("address") if isinstance(prop.get("address"), dict) else {}
    facts.street = facts.street or address.get("streetAddress")
    facts.city = facts.city or address.get("city")
    facts.state = facts.state or address.get("state")
    facts.zip_code = facts.zip_code or address.get("zipcode")
    facts.price = facts.price or _to_int(prop.get("price"))
    facts.beds = facts.beds or _to_float(prop.get("bedrooms"))
    facts.baths = facts.baths or _zillow_baths(prop)
    facts.sqft = facts.sqft or _to_int(prop.get("livingArea"))
    facts.lot_acres = facts.lot_acres or _zillow_lot_acres(prop)
    facts.year_built = facts.year_built or _to_int(prop.get("yearBuilt"))
    facts.property_type = facts.property_type or _humanize(prop.get("homeType"))
    if facts.garage_spaces is None:
        facts.garage_spaces = _zillow_garage_spaces(prop)
    facts.latitude = facts.latitude or _to_float(prop.get("latitude"))
    facts.longitude = facts.longitude or _to_float(prop.get("longitude"))


def _zillow_baths(prop: Dict[str, Any]) -> Optional[float]:
    """Half baths count as half; Zillow's "bathrooms" counts 2 full + 1 half as 3."""
    reso = prop.get("resoFacts") if isinstance(prop.get("resoFacts"), dict) else {}
    full, half = _to_float(reso.get("bathroomsFull")), _to_float(reso.get("bathroomsHalf"))
    if full is not None and half:
        return full + half / 2
    return _to_float(prop.get("bathrooms"))


def _zillow_garage_spaces(prop: Dict[str, Any]) -> Optional[int]:
    """Garage spaces from Zillow's RESO facts; 0 if it says there's no garage."""
    reso = prop.get("resoFacts") if isinstance(prop.get("resoFacts"), dict) else {}
    spaces = _to_int(reso.get("garageParkingCapacity", prop.get("garageParkingCapacity")))
    if spaces is not None:
        return spaces
    if reso.get("hasGarage") is False:
        return 0
    return None


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
