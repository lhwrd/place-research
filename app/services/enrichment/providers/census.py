"""Census population and tract demographics provider."""

import logging
from typing import Any, Dict, Optional

import httpx

from app.core.redaction import redact_secrets
from app.integrations.census_api import CensusAPIClient

from ..base_provider import (
    BaseEnrichmentProvider,
    ProviderCategory,
    ProviderMetadata,
    ProviderResult,
)


class CensusProvider(BaseEnrichmentProvider):
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.api_client = CensusAPIClient()

    @property
    def metadata(self) -> ProviderMetadata:
        return ProviderMetadata(
            name="census_provider",
            category=ProviderCategory.DEMOGRAPHICS,
            enabled=True,
            description=(
                "Provides city and county population, and census tract age, race/ethnicity "
                "and education, from the ACS 5-year estimates."
            ),
            version="1.0.0",
            requires_api_key=True,
            cost_per_call=0.0,
            cache_duration_days=90,  # ACS estimates are released once a year
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
        Enrich property with Census population and demographics.

        Returns:
            ProviderResult with acs_year, state, city, county and tract (see
            CensusAPIClient.get_demographics)
        """
        try:
            data = await self.api_client.get_demographics(latitude, longitude)
        except (httpx.HTTPError, ValueError) as e:
            error = redact_secrets(str(e))
            self.logger.error(
                "Error fetching Census data for %s (%s, %s): %s",
                address,
                latitude,
                longitude,
                error,
            )
            return ProviderResult(
                provider_name=self.metadata.name,
                data={},
                success=False,
                error_message=error,
                api_calls_made=1,
            )

        return ProviderResult(
            provider_name=self.metadata.name,
            data=data,
            success=True,
            # Geocoder, county, tract (2 requests: over 50 variables) and city
            api_calls_made=4 + (1 if data.get("city") else 0),
        )

    async def validate_config(self) -> bool:
        """Validate the Census API key."""
        return await self.api_client.validate_api_key()
