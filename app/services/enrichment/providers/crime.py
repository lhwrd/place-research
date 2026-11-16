"""Crime rates from the FBI for the police agency covering the property.

Inside an incorporated city with its own police department that's the city PD; otherwise
the county sheriff. Rates are for the whole agency (a sheriff's covers all of the
unincorporated county), so they say how a jurisdiction compares, not how a street does.

Florida agencies report to the FBI through NIBRS from 2025, and some (Orlando PD among
them) haven't reported at all yet; months an agency didn't report come back as zero, so
only months with offenses count, and an agency with none is flagged as not reporting.
"""

import asyncio
import logging
import re
from datetime import date
from typing import Any, Dict, List, Optional

import httpx

from app.core.redaction import redact_secrets
from app.integrations.census_api import CensusAPIClient
from app.integrations.fbi_cde_api import PROPERTY, VIOLENT, FbiCdeAPIClient

from ..base_provider import (
    BaseEnrichmentProvider,
    ProviderCategory,
    ProviderMetadata,
    ProviderResult,
)

# Ask for this many months back; the CDE lags a few months behind
LOOKBACK_MONTHS = 18
WINDOW_MONTHS = 12


class CrimeProvider(BaseEnrichmentProvider):
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.api_client = FbiCdeAPIClient()
        self.census_client = CensusAPIClient()

    @property
    def metadata(self) -> ProviderMetadata:
        return ProviderMetadata(
            name="crime_provider",
            category=ProviderCategory.SAFETY,
            description=(
                "Violent and property crime per 100k for the covering police agency "
                "(FBI Crime Data Explorer), against the state rate."
            ),
            version="1.0.0",
            requires_api_key=True,
            cache_duration_days=30,
        )

    def should_run(self, user_preferences: Optional[Dict[str, Any]] = None) -> bool:
        return bool(self.api_client.api_key) and super().should_run(user_preferences)

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
            ProviderResult with agency, ori, jurisdiction ("city" or "county"), reporting,
            and, when reporting: period_start, period_end, months, violent_per_100k,
            property_per_100k, state_violent_per_100k, state_property_per_100k, population
        """
        calls = 0
        try:
            geo = await self.census_client.get_geographies(latitude, longitude)
            calls += 1
            state = geo["state"].get("STUSAB")
            agencies = await self.api_client.get_agencies(state)
            calls += 1
            agency = choose_agency(agencies, geo["county"].get("BASENAME"), geo.get("place"))
            if agency is None:
                raise ValueError(f"No police agency found for {geo['county'].get('NAME')}")

            start, end = month_window(date.today())
            violent, prop = await asyncio.gather(
                self.api_client.get_monthly_offenses(agency["ori"], VIOLENT, start, end),
                self.api_client.get_monthly_offenses(agency["ori"], PROPERTY, start, end),
            )
            calls += 2
        except (httpx.HTTPError, ValueError, KeyError) as e:
            error = redact_secrets(str(e))
            self.logger.error("Error fetching crime data for %s: %s", address, error)
            return ProviderResult(
                provider_name=self.metadata.name,
                data={},
                success=False,
                error_message=error,
                api_calls_made=calls,
            )

        data = {
            "agency": agency["agency_name"],
            "ori": agency["ori"],
            "jurisdiction": "city" if agency.get("agency_type_name") == "City" else "county",
            **summarize(agency["agency_name"], geo["state"].get("NAME"), violent, prop),
        }
        return ProviderResult(
            provider_name=self.metadata.name, data=data, success=True, api_calls_made=calls
        )

    async def validate_config(self) -> bool:
        return await self.api_client.validate_api_key()


def _normalize(name: Optional[str]) -> str:
    """'St. Johns' and 'ST JOHNS' both -> 'st johns'."""
    return re.sub(r"[^a-z ]", "", (name or "").lower()).strip()


def choose_agency(
    agencies: List[Dict[str, Any]], county: Optional[str], place: Optional[Dict[str, Any]]
) -> Optional[Dict[str, Any]]:
    """The city's police department if the point is in a city that has one, else the sheriff."""
    county_key = _normalize(county)
    in_county = [
        a
        for a in agencies
        if county_key in {_normalize(c) for c in (a.get("counties") or "").split(",")}
    ]

    if place and place.get("type") == "incorporated":
        city = _normalize(place.get("BASENAME"))
        for agency in in_county:
            name = _normalize(agency.get("agency_name"))
            if agency.get("agency_type_name") == "City" and name.startswith(f"{city} police"):
                return agency

    for agency in in_county:
        if agency.get("agency_type_name") == "County" and "sheriff" in _normalize(
            agency.get("agency_name")
        ):
            return agency
    return None


def month_window(today: date) -> tuple:
    """("MM-YYYY", "MM-YYYY") from LOOKBACK_MONTHS ago through this month."""
    index = today.year * 12 + today.month - 1 - LOOKBACK_MONTHS
    return f"{index % 12 + 1:02d}-{index // 12}", f"{today.month:02d}-{today.year}"


def _month_key(month: str) -> tuple:
    mm, yyyy = month.split("-")
    return int(yyyy), int(mm)


def summarize(
    agency_name: str,
    state_name: Optional[str],
    violent: Dict[str, Any],
    prop: Dict[str, Any],
) -> Dict[str, Any]:
    """Annualized rates over the latest (up to) 12 months the agency reported."""

    def series(body: Dict[str, Any], kind: str, name: Optional[str]) -> Dict[str, float]:
        return ((body.get("offenses") or {}).get(kind) or {}).get(f"{name} Offenses") or {}

    v_count, p_count = series(violent, "actuals", agency_name), series(prop, "actuals", agency_name)
    reported = sorted(
        (
            m
            for m in set(v_count) | set(p_count)
            if (v_count.get(m) or 0) + (p_count.get(m) or 0) > 0
        ),
        key=_month_key,
    )[-WINDOW_MONTHS:]
    if not reported:
        return {"reporting": False}

    def annual_rate(body: Dict[str, Any], name: Optional[str]) -> Optional[float]:
        rates = series(body, "rates", name)
        values = [rates[m] for m in reported if rates.get(m) is not None]
        return round(sum(values) * 12 / len(values), 1) if values else None

    population = (
        ((violent.get("populations") or {}).get("population") or {})
        .get(agency_name, {})
        .get(reported[-1])
    )
    return {
        "reporting": True,
        "period_start": reported[0],
        "period_end": reported[-1],
        "months": len(reported),
        "violent_per_100k": annual_rate(violent, agency_name),
        "property_per_100k": annual_rate(prop, agency_name),
        "state_violent_per_100k": annual_rate(violent, state_name),
        "state_property_per_100k": annual_rate(prop, state_name),
        "population": population,
    }
