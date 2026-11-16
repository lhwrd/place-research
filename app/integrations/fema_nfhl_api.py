"""FEMA National Flood Hazard Layer (NFHL) client.

Queries FEMA's public ArcGIS service for the flood hazard zone at a point. No API key.
https://hazards.fema.gov/arcgis/rest/services/public/NFHL/MapServer
"""

import logging
from typing import Any, Dict, Optional

from .arcgis_api import ArcGISClient

logger = logging.getLogger(__name__)

FEMA_NFHL = "https://hazards.fema.gov/arcgis/rest/services/public/NFHL/MapServer"
# Layer 28 is "Flood Hazard Zones" (the S_FLD_HAZ_AR polygons)
FLOOD_HAZARD_ZONES_LAYER = "28"
FIELDS = ("FLD_ZONE", "ZONE_SUBTY", "SFHA_TF", "STATIC_BFE")

# FEMA uses -9999 for "no value" in numeric fields
NO_VALUE = -9999

NOT_MAPPED = "Not mapped"


class FemaNfhlAPIClient(ArcGISClient):
    """Flood zone lookups against FEMA's NFHL map service."""

    def __init__(self):
        # The service intermittently resets connections; the ArcGIS client's retries
        # usually succeed
        super().__init__(base_url=FEMA_NFHL, service="FEMA NFHL")

    async def validate_api_key(self) -> bool:
        """No key is needed; check the service answers for a known mapped point."""
        try:
            zone = await self.get_flood_zone(latitude=39.74, longitude=-104.99)
        except Exception:  # pylint: disable=broad-except
            return False
        return zone.get("flood_zone") not in (None, NOT_MAPPED)

    async def get_flood_zone(self, latitude: float, longitude: float) -> Dict[str, Any]:
        """
        Look up the flood hazard zone containing a point.

        Returns:
            {"flood_zone", "flood_risk", "in_sfha", "base_flood_elevation_ft"}. flood_zone is
            "Not mapped" where FEMA has no flood map, and the other fields are then None.

        Raises:
            httpx.HTTPError: If the service can't be reached or returns an HTTP error
            ValueError: If the service returns an ArcGIS error body
        """
        zones = await self.query_near(
            FLOOD_HAZARD_ZONES_LAYER, latitude, longitude, out_fields=FIELDS
        )
        if not zones:
            logger.info("No FEMA flood map at (%.6f, %.6f)", latitude, longitude)
            return {
                "flood_zone": NOT_MAPPED,
                "flood_risk": None,
                "in_sfha": None,
                "base_flood_elevation_ft": None,
            }

        # Overlapping polygons (e.g. along a zone boundary): report the riskiest
        zone = max(zones, key=_risk_rank)
        return {
            "flood_zone": zone.get("FLD_ZONE"),
            "flood_risk": zone.get("ZONE_SUBTY") or None,
            "in_sfha": zone.get("SFHA_TF") == "T",
            "base_flood_elevation_ft": _value(zone.get("STATIC_BFE")),
        }


def _risk_rank(zone: Dict[str, Any]) -> tuple:
    """Higher is riskier: SFHA first, then coastal V zones, then the 0.2% (moderate) X zone."""
    fld_zone = str(zone.get("FLD_ZONE") or "")
    subtype = str(zone.get("ZONE_SUBTY") or "")
    return (zone.get("SFHA_TF") == "T", fld_zone.startswith("V"), "0.2 PCT" in subtype)


def _value(number: Optional[float]) -> Optional[float]:
    return None if number is None or number <= NO_VALUE else number
