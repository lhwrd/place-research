"""FBI Crime Data Explorer (CDE) API: agency list and monthly offense counts.

Served through api.data.gov, which needs a free key (CRIME_DATA_API_KEY):
https://api.data.gov/signup/
"""

import logging
from typing import Any, Dict, List, Optional

from app.core.config import settings

from .base_client import BaseAPIClient, send_with_retry

logger = logging.getLogger(__name__)

# Offense groups the summarized endpoint accepts
VIOLENT = "violent-crime"
PROPERTY = "property-crime"


class FbiCdeAPIClient(BaseAPIClient):
    # State postal code -> agencies; the list changes rarely, so it's kept per process
    _agencies: Dict[str, List[Dict[str, Any]]] = {}

    def __init__(self, api_key: Optional[str] = None):
        super().__init__(
            base_url="https://api.usa.gov/crime/fbi/cde",
            api_key=api_key or settings.crime_data_api_key,
            timeout=45.0,
            rate_limit_per_second=5.0,
        )

    def _get_service_name(self) -> str:
        return "fbi_cde"

    async def validate_api_key(self) -> bool:
        return bool(self.api_key)

    async def get_agencies(self, state: str) -> List[Dict[str, Any]]:
        """
        Every reporting agency in a state: ori, agency_name, agency_type_name ("City",
        "County", ...), counties (e.g. "FLAGLER, VOLUSIA"), latitude, longitude.
        """
        state = state.upper()
        cache = self.__class__._agencies
        if state not in cache:
            by_county = await self._get(f"agency/byStateAbbr/{state}", {})
            agencies: Dict[str, Dict[str, Any]] = {}
            for county_agencies in by_county.values():
                for agency in county_agencies:
                    agencies[agency["ori"]] = agency
            cache[state] = list(agencies.values())
        return cache[state]

    async def get_monthly_offenses(
        self, ori: str, offense: str, start: str, end: str
    ) -> Dict[str, Any]:
        """
        Monthly offenses for one agency, with the state's rate for comparison.

        Args:
            offense: VIOLENT or PROPERTY
            start, end: "MM-YYYY"

        Returns:
            The CDE response: offenses.actuals/rates keyed "<name> Offenses", each
            {"MM-YYYY": value}; populations.population keyed by name. Months the agency
            didn't report come back as 0.
        """
        return await self._get(f"summarized/agency/{ori}/{offense}", {"from": start, "to": end})

    async def _get(self, path: str, params: Dict[str, Any]) -> Dict[str, Any]:
        if not self.api_key:
            raise ValueError("CRIME_DATA_API_KEY not configured")
        await self._rate_limit()
        url = f"{self.base_url}/{path}"
        response = await send_with_retry(
            lambda: self.client.get(url, params={**params, "API_KEY": self.api_key}),
            service="FBI Crime Data Explorer",
        )
        response.raise_for_status()
        return response.json()
