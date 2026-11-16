"""The county property appraiser's record for the parcel, from Florida's statewide parcels.

Every year each of Florida's 67 county property appraisers submits its tax roll (the NAL
file) to the Department of Revenue, which joins it to the parcel polygons; Florida GIO
publishes the result as one public, keyless ArcGIS layer. It gives year built, living
area, lot size, use, quality, just and taxable value, homestead status and recent sales.
It has no bedroom or bathroom counts: those stay with each county's own system.

Field meanings follow the Department's NAL/SDF/NAP Users Guide. The layer was exported
from a shapefile, so names are cut to 10 characters (TOT_LVG_AREA is TOT_LVG_AR), and
fields the guide says are left blank come back as 0.

Florida only; elsewhere no parcel is found.
"""

import logging
import re
from typing import Any, Dict, List, Optional, Tuple

import httpx

from app.integrations.arcgis_api import FL_GIO, ArcGISClient
from app.utils.distance_calculator import geometry_distance_m

from ..base_provider import (
    BaseEnrichmentProvider,
    ProviderCategory,
    ProviderMetadata,
    ProviderResult,
)

PARCELS_LAYER = "Florida_Statewide_Cadastral/FeatureServer/0"

# A geocoded point can land on the street or the neighbor's lot; look this far around it.
# The layer can't answer distance queries (see ArcGISClient.query_box), so it's a square.
SEARCH_HALF_SIZE_M = 40

SQFT_PER_ACRE = 43560

FIELDS = (
    "CO_NO", "PARCEL_ID", "ASMNT_YR", "DOR_UC", "PHY_ADDR1", "PHY_CITY", "PHY_ZIPCD",
    "ACT_YR_BLT", "EFF_YR_BLT", "TOT_LVG_AR", "LND_SQFOOT", "NO_BULDNG", "NO_RES_UNT",
    "IMP_QUAL", "JV", "LND_VAL", "TV_SD", "TV_NSD", "JV_HMSTD",
    "SALE_PRC1", "SALE_YR1", "SALE_MO1", "QUAL_CD1", "VI_CD1",
    "SALE_PRC2", "SALE_YR2", "SALE_MO2", "QUAL_CD2", "VI_CD2",
)  # fmt: skip

# The Department's county numbers: alphabetical from 11, with Miami-Dade still filed
# under its pre-1997 name, Dade
COUNTIES = {
    number: name.replace("_", " ")
    for number, name in enumerate(
        """Alachua Baker Bay Bradford Brevard Broward Calhoun Charlotte Citrus Clay Collier
        Columbia Miami-Dade DeSoto Dixie Duval Escambia Flagler Franklin Gadsden Gilchrist
        Glades Gulf Hamilton Hardee Hendry Hernando Highlands Hillsborough Holmes
        Indian_River Jackson Jefferson Lafayette Lake Lee Leon Levy Liberty Madison Manatee
        Marion Martin Monroe Nassau Okaloosa Okeechobee Orange Osceola Palm_Beach Pasco
        Pinellas Polk Putnam St._Johns St._Lucie Santa_Rosa Sarasota Seminole Sumter
        Suwannee Taylor Union Volusia Wakulla Walton Washington""".split(),
        start=11,
    )
}

# DOR land use codes: the residential ones by name, the rest by group
RESIDENTIAL_USES = {
    "000": "Vacant residential",
    "001": "Single family",
    "002": "Mobile home",
    "003": "Multi-family, 10+ units",
    "004": "Condominium",
    "005": "Cooperative",
    "006": "Retirement home",
    "007": "Miscellaneous residential",
    "008": "Multi-family, under 10 units",
    "009": "Residential common area",
}
USE_GROUPS = [
    (39, "Commercial"),
    (49, "Industrial"),
    (69, "Agricultural"),
    (79, "Institutional"),
    (89, "Government"),
    (97, "Miscellaneous"),
    (98, "Centrally assessed"),
    (99, "Non-agricultural acreage"),
]

QUALITY = {
    "1": "Minimum",
    "2": "Below average",
    "3": "Average",
    "4": "Above average",
    "5": "Excellent",
    "6": "Superior",
}

# Sale qualification codes 01-06 are arm's-length sales (01-02 are the ones the Department
# uses for its sales ratio studies; 03-06 are arm's length but the property or parcels
# changed). 11-43 are disqualified: family transfers, foreclosures, quit claims, ...
ARMS_LENGTH_CODES = {"01", "02", "03", "04", "05", "06"}

DIRECTIONS = {"N", "S", "E", "W", "NE", "NW", "SE", "SW"}
UNIT_LABELS = {"UNIT", "APT", "STE", "SUITE"}


class ParcelProvider(BaseEnrichmentProvider):
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.api_client = ArcGISClient(FL_GIO, service="Florida parcels")

    @property
    def metadata(self) -> ProviderMetadata:
        return ProviderMetadata(
            name="parcel_provider",
            category=ProviderCategory.PROPERTY,
            description=(
                "The county property appraiser's record for the parcel (Florida): year "
                "built, living area, lot, use, value, homestead and recent sales."
            ),
            version="1.0.0",
            requires_api_key=False,
            # The roll is republished every August
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
            ProviderResult with found (False outside Florida or with no parcel nearby),
            match ("address", "location" or "nearest"), and the parcel's details (see
            parcel_details)
        """
        try:
            parcels = await self.api_client.query_box(
                PARCELS_LAYER, latitude, longitude, SEARCH_HALF_SIZE_M, FIELDS
            )
        except (httpx.HTTPError, ValueError) as e:
            self.logger.error("Error fetching parcel for %s: %s", address, e)
            return ProviderResult(
                provider_name=self.metadata.name,
                data={},
                success=False,
                error_message=str(e),
                api_calls_made=1,
            )

        chosen = choose_parcel(latitude, longitude, address, parcels)
        if chosen is None:
            data: Dict[str, Any] = {"found": False}
        else:
            parcel, match = chosen
            data = {"found": True, "match": match, **parcel_details(parcel)}
        return ProviderResult(
            provider_name=self.metadata.name, data=data, success=True, api_calls_made=1
        )

    async def validate_config(self) -> bool:
        return True


def choose_parcel(
    latitude: float, longitude: float, address: str, parcels: List[Dict[str, Any]]
) -> Optional[Tuple[Dict[str, Any], str]]:
    """
    The parcel the property is on, and how it was picked.

    In order: one whose situs address matches the property's ("address"); the one the
    point falls in ("location"); the nearest ("nearest"). Ties go to the nearest parcel,
    then to a residential one over a condo's common area.
    """
    if not parcels:
        return None

    def rank(parcel: Dict[str, Any]) -> Tuple[float, bool]:
        geometry = parcel.get("geometry")
        distance = geometry_distance_m(latitude, longitude, geometry) if geometry else float("inf")
        return distance, parcel.get("DOR_UC") == "009"

    ranked = sorted(parcels, key=rank)
    wanted = street_line(address)

    exact = [p for p in ranked if normalize(p.get("PHY_ADDR1")) == wanted]
    if exact:
        return exact[0], "address"
    same_street = [p for p in ranked if same_house(normalize(p.get("PHY_ADDR1")), wanted)]
    if same_street:
        return same_street[0], "address"

    nearest = ranked[0]
    return nearest, "location" if rank(nearest)[0] == 0 else "nearest"


def parcel_details(p: Dict[str, Any]) -> Dict[str, Any]:
    """The parcel's attributes, renamed, with the NAL's blank-as-zero turned into None."""
    use_code = (p.get("DOR_UC") or "").strip() or None
    lot_sqft = _positive(p.get("LND_SQFOOT"))
    just_value = _positive(p.get("JV"))
    land_value = _positive(p.get("LND_VAL"))
    return {
        "county": COUNTIES.get(_int(p.get("CO_NO"))),
        "parcel_id": (p.get("PARCEL_ID") or "").strip() or None,
        "assessment_year": _positive(p.get("ASMNT_YR")),
        "situs_address": _situs(p),
        "use_code": use_code,
        "use": use_description(use_code),
        "year_built": _positive(p.get("ACT_YR_BLT")),
        "effective_year_built": _positive(p.get("EFF_YR_BLT")),
        "living_area_sqft": _positive(p.get("TOT_LVG_AR")),
        "lot_sqft": lot_sqft,
        "lot_acres": round(lot_sqft / SQFT_PER_ACRE, 2) if lot_sqft else None,
        "buildings": _positive(p.get("NO_BULDNG")),
        "residential_units": _positive(p.get("NO_RES_UNT")),
        "quality": QUALITY.get((p.get("IMP_QUAL") or "").strip()),
        "just_value": just_value,
        "land_value": land_value,
        "taxable_value": _positive(p.get("TV_NSD")),
        "school_taxable_value": _positive(p.get("TV_SD")),
        "homestead": bool(_positive(p.get("JV_HMSTD"))),
        "recent_sales": recent_sales(p),
    }


def use_description(code: Optional[str]) -> Optional[str]:
    if not code:
        return None
    if code in RESIDENTIAL_USES:
        return RESIDENTIAL_USES[code]
    number = _int(code)
    if number is None:
        return None
    for upper, group in USE_GROUPS:
        if number <= upper:
            return group
    return None


def recent_sales(p: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Up to two sales from the previous or current calendar year, newest first.

    The NAL carries only these; a parcel with none simply hasn't sold lately.
    """
    sales = []
    for n in (1, 2):
        year = _positive(p.get(f"SALE_YR{n}"))
        if not year:
            continue
        code = (p.get(f"QUAL_CD{n}") or "").strip() or None
        sales.append(
            {
                "year": year,
                "month": _int(p.get(f"SALE_MO{n}")),
                "price": _positive(p.get(f"SALE_PRC{n}")),
                "qualification_code": code,
                "arms_length": code in ARMS_LENGTH_CODES,
                "vacant_land": (p.get(f"VI_CD{n}") or "").strip() == "V",
            }
        )
    return sorted(sales, key=lambda s: (s["year"], s["month"] or 0), reverse=True)


def street_line(address: str) -> str:
    """The normalized street part of a one-line address: "111 White Pl, Port ..." -> "111 WHITE PL"."""
    return normalize((address or "").split(",")[0])


def normalize(street: Optional[str]) -> str:
    """Upper case, no punctuation or unit labels: "304 S MacDill Ave, #3" -> "304 S MACDILL AVE 3"."""
    text = re.sub(r"[^A-Z0-9 ]", " ", (street or "").upper())
    return " ".join(w for w in text.split() if w not in UNIT_LABELS)


def same_house(situs: str, wanted: str) -> bool:
    """
    Same house number and street name, ignoring suffix and unit spellings.

    "1216 VIRGINIA DR" matches "1216 Virginia Drive"; "304 S MACDILL AVE UNIT 3" matches
    "304 S MacDill Ave #3" (and the other units: the nearest one wins).
    """
    a, b = _number_and_name(situs), _number_and_name(wanted)
    return a is not None and a == b


def _number_and_name(street: str) -> Optional[Tuple[str, str]]:
    words = street.split()
    if len(words) < 2 or not words[0].isdigit():
        return None
    rest = [w for w in words[1:] if w not in DIRECTIONS] or words[1:]
    return words[0], rest[0]


def _situs(p: Dict[str, Any]) -> Optional[str]:
    street = (p.get("PHY_ADDR1") or "").strip()
    city = (p.get("PHY_CITY") or "").strip()
    return ", ".join(part for part in (street, city.title()) if part) or None


def _int(value: Any) -> Optional[int]:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _positive(value: Any) -> Optional[int]:
    """The NAL leaves not-applicable fields blank; this layer serves those as 0."""
    number = _int(value)
    return number if number and number > 0 else None
