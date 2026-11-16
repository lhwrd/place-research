"""Lakes and streams near the property that FDEP lists as impaired.

Florida's Impaired Waters Rule assessment flags waterbodies that fail water quality
standards: in Central Florida mostly nutrients (algae blooms), bacteria (swimming
advisories) and mercury (fish consumption). Areas are FDEP waterbody IDs (WBIDs), which
cover a water body and the land draining into it. Florida only; no key.
"""

import logging
from collections import OrderedDict
from typing import Any, Dict, List, Optional

import httpx

from app.integrations.arcgis_api import FDEP_OPEN_DATA, ArcGISClient

from ..base_provider import (
    BaseEnrichmentProvider,
    ProviderCategory,
    ProviderMetadata,
    ProviderResult,
)

IMPAIRED_WATERS_LAYER = "OpenData/IMPAIRED_WATERS/MapServer/14"
SEARCH_RADIUS_M = 800  # about half a mile

FIELDS = ("WATERBODY_NAME", "WATERBODY_TYPE", "PARAMETER_IWR", "ASSESSMENT_STATUS")


class ImpairedWatersProvider(BaseEnrichmentProvider):
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.api_client = ArcGISClient(FDEP_OPEN_DATA, service="FDEP impaired waters")

    @property
    def metadata(self) -> ProviderMetadata:
        return ProviderMetadata(
            name="impaired_waters_provider",
            category=ProviderCategory.ENVIRONMENTAL,
            description="FDEP-listed impaired lakes and streams within half a mile.",
            version="1.0.0",
            requires_api_key=False,
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
            ProviderResult with impaired_waters: [{name, type, parameters}]
        """
        try:
            features = await self.api_client.query_near(
                IMPAIRED_WATERS_LAYER, latitude, longitude, SEARCH_RADIUS_M, FIELDS
            )
        except (httpx.HTTPError, ValueError) as e:
            self.logger.error("Error fetching impaired waters for %s: %s", address, e)
            return ProviderResult(
                provider_name=self.metadata.name,
                data={},
                success=False,
                error_message=str(e),
                api_calls_made=1,
            )

        return ProviderResult(
            provider_name=self.metadata.name,
            data={"impaired_waters": group_by_waterbody(features)},
            success=True,
            api_calls_made=1,
        )

    async def validate_config(self) -> bool:
        return True


def group_by_waterbody(features: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """One entry per waterbody with its impairments, e.g. Lake Eola: nutrients."""
    waters: "OrderedDict[str, Dict[str, Any]]" = OrderedDict()
    for f in features:
        if (f.get("ASSESSMENT_STATUS") or "").lower() != "impaired":
            continue
        name = (f.get("WATERBODY_NAME") or "Unnamed").title()
        water = waters.setdefault(
            name, {"name": name, "type": (f.get("WATERBODY_TYPE") or "").title(), "parameters": []}
        )
        parameter = f.get("PARAMETER_IWR")
        if parameter and parameter not in water["parameters"]:
            water["parameters"].append(parameter)
    return list(waters.values())
