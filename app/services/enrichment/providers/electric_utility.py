"""The electric utility serving the property, and what its residential customers pay.

From the electric retail service territories (HIFLD) joined to EIA-861 sales and revenue,
as published in Esri's Living Atlas. The rate is the utility's residential revenue divided
by the kilowatt-hours it sold: an average over all its customers, not a tariff.

Territories overlap, mostly where a municipal utility sits inside an investor-owned
utility's wider area, so every utility at the point is returned, smallest territory first:
that one is the likeliest. The listing or the utility itself has the final word. No key.
"""

import logging
import re
from typing import Any, Dict, List, Optional

import httpx

from app.integrations.arcgis_api import ESRI_POLICY_MAPS, ArcGISClient

from ..base_provider import (
    BaseEnrichmentProvider,
    ProviderCategory,
    ProviderMetadata,
    ProviderResult,
)

TERRITORIES_LAYER = "Electricity_Rates_H3_Res5/FeatureServer/7"
# Newest first; the first year with a residential rate is used
RATE_YEARS = (2025, 2024, 2023)
FIELDS = (
    "NAME",
    "TYPE",
    "Shape__Area",
    *(f"Res_Electricity_Rate_Nom_{year}" for year in RATE_YEARS),
    *(f"Res_Customer_Count_{year}" for year in RATE_YEARS),
)
# Territories drawn far wider than the utility's handful of homes (Reedy Creek's covers
# most of Central Florida for nine residential customers) are left out
MIN_RESIDENTIAL_CUSTOMERS = 1000

TYPES = {
    "MUNICIPAL": "municipal",
    "INVESTOR OWNED": "investor-owned",
    "COOPERATIVE": "cooperative",
}


class ElectricUtilityProvider(BaseEnrichmentProvider):
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.api_client = ArcGISClient(ESRI_POLICY_MAPS, service="Electric service territories")

    @property
    def metadata(self) -> ProviderMetadata:
        return ProviderMetadata(
            name="electric_utility_provider",
            category=ProviderCategory.PROPERTY,
            description="Electric utility at the address and its average residential rate.",
            version="1.0.0",
            requires_api_key=False,
            cache_duration_days=365,
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
            ProviderResult with utilities, likeliest first: name, type (municipal,
            investor-owned, cooperative or None), residential_cents_per_kwh, rate_year and
            residential_customers
        """
        try:
            features = await self.api_client.query_near(
                TERRITORIES_LAYER, latitude, longitude, out_fields=FIELDS
            )
        except (httpx.HTTPError, ValueError) as e:
            self.logger.error("Error fetching electric utility for %s: %s", address, e)
            return ProviderResult(
                provider_name=self.metadata.name,
                data={},
                success=False,
                error_message=str(e),
                api_calls_made=1,
            )
        return ProviderResult(
            provider_name=self.metadata.name,
            data={"utilities": summarize_utilities(features)},
            success=True,
            api_calls_made=1,
        )

    async def validate_config(self) -> bool:
        return True


def summarize_utilities(features: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    utilities = []
    for f in sorted(features, key=lambda f: f.get("Shape__Area") or float("inf")):
        year = next((y for y in RATE_YEARS if f.get(f"Res_Electricity_Rate_Nom_{y}")), None)
        customers = next(
            (f[f"Res_Customer_Count_{y}"] for y in RATE_YEARS if f.get(f"Res_Customer_Count_{y}")),
            None,
        )
        if customers is not None and customers < MIN_RESIDENTIAL_CUSTOMERS:
            continue
        rate = f.get(f"Res_Electricity_Rate_Nom_{year}") if year else None
        utilities.append(
            {
                "name": _name(f.get("NAME")),
                "type": TYPES.get(f.get("TYPE")),
                "residential_cents_per_kwh": round(rate, 1) if rate else None,
                "rate_year": year,
                "residential_customers": int(customers) if customers is not None else None,
            }
        )
    return utilities


def _name(raw: Optional[str]) -> Optional[str]:
    """EIA tags same-named utilities with their state: "CITY OF WINTER PARK - (FL)"."""
    return " ".join(re.sub(r"\s*-\s*\([A-Z]{2}\)\s*$", "", raw or "").split()) or None
