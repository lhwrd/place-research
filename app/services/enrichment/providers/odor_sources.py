"""Facilities near the property that are known for their smell (FDEP permit records).

Three FDEP layers, filtered to the kinds of facility people complain about:

- Wastewater facilities: sewage treatment plants, biosolids and septage sites, and
  permitted animal feeding operations (dairies, egg farms).
- Solid waste facilities: landfills, transfer stations, composting, waste-to-energy.
- Air permits: pulp and paper mills, asphalt plants, phosphate fertilizer plants, sugar
  mills, citrus processors, rendering plants and petroleum terminals.

How far a smell carries depends on the kind of facility, so each kind has its own range: a
kraft paper mill is smelled ten miles downwind, a trailer park's package plant only next
door. A facility counts only within its kind's range. Wind direction isn't considered.
Florida only; no key.
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional

import httpx

from app.integrations.arcgis_api import FDEP_OPEN_DATA, ArcGISClient
from app.utils.distance_calculator import haversine_distance

from ..base_provider import (
    BaseEnrichmentProvider,
    ProviderCategory,
    ProviderMetadata,
    ProviderResult,
)

METERS_PER_MILE = 1609.344
MAX_SOURCES = 10

# kind: (label, miles within which it is worth a mention). Ordered strongest first: a
# facility permitted as several kinds is reported as the first of them.
KINDS = {
    "paper_mill": ("pulp and paper mill", 10),
    "landfill": ("landfill", 3),
    "rendering_plant": ("rendering plant", 3),
    "fertilizer_plant": ("phosphate fertilizer plant", 3),
    "sugar_mill": ("sugar mill", 3),
    "animal_feeding": ("animal feeding operation", 3),
    "biosolids": ("biosolids / septage site", 1.5),
    "wastewater_plant": ("wastewater treatment plant", 1),
    "waste_to_energy": ("waste-to-energy plant", 1),
    "composting": ("composting / organics facility", 1),
    "debris_landfill": ("construction debris landfill", 1),
    "asphalt_plant": ("asphalt plant", 1),
    "citrus_plant": ("citrus processing plant", 1),
    "transfer_station": ("waste transfer station", 0.5),
    "petroleum_terminal": ("petroleum terminal", 0.5),
    "small_wastewater_plant": ("small wastewater plant", 0.25),
}

WASTEWATER_LAYER = "OpenData/WAFR/MapServer/3"
WASTEWATER_FIELDS = (
    "FACILITY_ID",
    "FACILITY_NAME",
    "FACILITY_TYPE",
    "DESIGN_CAPACITY",
    "PERMITTED_CAPACITY",
)
WASTEWATER_TYPES = {
    "RES": "biosolids",  # residuals / septage management
    "RAF": "biosolids",  # residuals application (land spreading)
    "CFO": "animal_feeding",
    "AFO": "animal_feeding",
}
# Domestic wastewater plants below this (million gallons a day) are package plants serving
# one trailer park, campground or school
SMALL_PLANT_MGD = 0.1

SOLID_WASTE_LAYER = "OpenData/DWM_WASTE_ICR_BACKG/MapServer/1"
SOLID_WASTE_FIELDS = ("FACILITY_ID", "FACILITY_NAME", "CLASS")
SOLID_WASTE_CLASSES = {
    "CLASS I LANDFILL": "landfill",  # household garbage
    "CLASS II LANDFILL": "landfill",
    "CLASS III LANDFILL": "debris_landfill",  # yard trash, construction debris, furniture
    "CONSTRUCTION/DEMOLITION DEBRIS DISPOSAL": "debris_landfill",
    "SLUDGE MANAGEMENT SITE": "biosolids",
    "WASTE TO ENERGY FACILITY": "waste_to_energy",
    "SOLID WASTE COMBUSTOR": "waste_to_energy",
    "COMPOSTING FACILITY": "composting",
    "SOURCE-SEPARATED ORGANICS PROC. FAC. (SOPF)": "composting",
    "TRANSFER STATION": "transfer_station",
}
# The layer also lists closed, proposed and merely pre-authorized (disaster debris) sites
SOLID_WASTE_OPERATING = (
    "Active",
    "Authorized To Operate",
    "Licensed",
    "Registered",
    "Under Solid Waste Permit",
)

AIR_LAYER = "OpenData/ARMS/MapServer/0"
AIR_FIELDS = ("AIRS_ID", "NAME", "SIC", "FACILITY_TYPE")
AIR_TYPES = {
    "PULP & PAPER PLANT": "paper_mill",
    "PHOSPHATE FERTILIZER PLANT": "fertilizer_plant",
    "SUGAR PROCESSING PLANT": "sugar_mill",
    "ASPHALT PLANT": "asphalt_plant",
    "CITRUS PROCESSING PLANT": "citrus_plant",
    "PETROLEUM STORAGE/TRANSFER": "petroleum_terminal",
}
# "Pulp & paper plant" includes box and bag plants, which don't smell; these SIC codes are
# the pulp, paper and paperboard mills
MILL_SICS = ("2611", "2621", "2631")
RENDERING_SIC = "2077"  # animal and marine fats and oils


def _in(values) -> str:
    return "(" + ", ".join(f"'{v}'" for v in values) + ")"


WASTEWATER_WHERE = f"FACILITY_STATUS = 'A' AND FACILITY_TYPE IN {_in(['DW', *WASTEWATER_TYPES])}"
SOLID_WASTE_WHERE = (
    f"CLASS_STATUS IN {_in(SOLID_WASTE_OPERATING)} AND CLASS IN {_in(SOLID_WASTE_CLASSES)}"
)
AIR_WHERE = f"STATUS = 'ACTIVE' AND (FACILITY_TYPE IN {_in(AIR_TYPES)} OR SIC = '{RENDERING_SIC}')"


def _range_m(*kinds: str) -> float:
    return max(KINDS[k][1] for k in kinds) * METERS_PER_MILE


WASTEWATER_RADIUS_M = _range_m("wastewater_plant", *WASTEWATER_TYPES.values())
SOLID_WASTE_RADIUS_M = _range_m(*SOLID_WASTE_CLASSES.values())
AIR_RADIUS_M = _range_m("rendering_plant", *AIR_TYPES.values())


class OdorSourcesProvider(BaseEnrichmentProvider):
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.api_client = ArcGISClient(FDEP_OPEN_DATA, service="FDEP odor sources")

    @property
    def metadata(self) -> ProviderMetadata:
        return ProviderMetadata(
            name="odor_sources_provider",
            category=ProviderCategory.ENVIRONMENTAL,
            description="Nearby facilities known for odor: sewage plants, landfills, mills.",
            version="1.0.0",
            requires_api_key=False,
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
            ProviderResult with source_count and sources (at most 10, the one deepest
            inside its kind's range first: name, kind, type, distance_m, range_m)
        """
        queries = (
            (WASTEWATER_LAYER, WASTEWATER_RADIUS_M, WASTEWATER_FIELDS, WASTEWATER_WHERE),
            (SOLID_WASTE_LAYER, SOLID_WASTE_RADIUS_M, SOLID_WASTE_FIELDS, SOLID_WASTE_WHERE),
            (AIR_LAYER, AIR_RADIUS_M, AIR_FIELDS, AIR_WHERE),
        )
        try:
            wastewater, solid_waste, air = await asyncio.gather(
                *(
                    self.api_client.query_near(
                        layer, latitude, longitude, radius, fields, geometry=True, where=where
                    )
                    for layer, radius, fields, where in queries
                )
            )
        except (httpx.HTTPError, ValueError) as e:
            self.logger.error("Error fetching odor sources for %s: %s", address, e)
            return ProviderResult(
                provider_name=self.metadata.name,
                data={},
                success=False,
                error_message=str(e),
                api_calls_made=len(queries),
            )

        candidates = [
            *_candidates(wastewater, "FACILITY_ID", "FACILITY_NAME", wastewater_kind),
            *_candidates(
                solid_waste,
                "FACILITY_ID",
                "FACILITY_NAME",
                lambda f: SOLID_WASTE_CLASSES.get(f.get("CLASS")),
            ),
            *_candidates(air, "AIRS_ID", "NAME", air_kind),
        ]
        return ProviderResult(
            provider_name=self.metadata.name,
            data=summarize_sources(latitude, longitude, candidates),
            success=True,
            api_calls_made=len(queries),
        )

    async def validate_config(self) -> bool:
        return True


def wastewater_kind(feature: Dict[str, Any]) -> Optional[str]:
    facility_type = feature.get("FACILITY_TYPE")
    if facility_type != "DW":
        return WASTEWATER_TYPES.get(facility_type)
    capacity = max(feature.get("DESIGN_CAPACITY") or 0, feature.get("PERMITTED_CAPACITY") or 0)
    return "wastewater_plant" if capacity >= SMALL_PLANT_MGD else "small_wastewater_plant"


def air_kind(feature: Dict[str, Any]) -> Optional[str]:
    if feature.get("SIC") == RENDERING_SIC:
        return "rendering_plant"
    kind = AIR_TYPES.get(feature.get("FACILITY_TYPE"))
    if kind == "paper_mill" and feature.get("SIC") not in MILL_SICS:
        return None
    return kind


def _candidates(features, id_field: str, name_field: str, kind_of) -> List[tuple]:
    return [
        (f.get(id_field) or f.get(name_field), f.get(name_field), kind_of(f), f.get("geometry"))
        for f in features
    ]


def summarize_sources(latitude: float, longitude: float, candidates: List[tuple]) -> Dict[str, Any]:
    """
    Args:
        candidates: (facility id, name, kind or None, point geometry or None) per feature
    """
    order = list(KINDS)
    # One entry per facility: the solid waste layer has a row per activity at a site
    by_facility: Dict[Any, Dict[str, Any]] = {}
    for facility_id, name, kind, point in candidates:
        if kind is None or point is None:
            continue
        label, range_mi = KINDS[kind]
        distance_m = haversine_distance(latitude, longitude, point.y, point.x)
        if distance_m > range_mi * METERS_PER_MILE:
            continue
        current = by_facility.get(facility_id)
        if current is None or order.index(kind) < order.index(current["kind"]):
            by_facility[facility_id] = {
                "name": " ".join((name or "").split()) or None,
                "kind": kind,
                "type": label,
                "distance_m": round(distance_m),
                "range_m": round(range_mi * METERS_PER_MILE),
            }

    sources = sorted(by_facility.values(), key=lambda s: s["distance_m"] / s["range_m"])
    return {"source_count": len(sources), "sources": sources[:MAX_SOURCES]}
