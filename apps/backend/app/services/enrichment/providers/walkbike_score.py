"""Walk Score enrichment provider."""

import logging
from typing import Any, Dict, Optional

from app.integrations.walk_score_api import WalkScoreAPI
from app.services.enrichment.base_provider import (
    BaseEnrichmentProvider,
    ProviderCategory,
    ProviderMetadata,
    ProviderResult,
)

logger = logging.getLogger(__name__)


class WalkScoreProvider(BaseEnrichmentProvider):
    """Provider for walk, bike, and transit scores."""

    def __init__(self):
        self.api_client = WalkScoreAPI()

    @property
    def metadata(self) -> ProviderMetadata:
        return ProviderMetadata(
            name="walk_score",
            category=ProviderCategory.WALKABILITY,
            description="Provides walk, bike, and transit scores",
            version="1.0.0",
            enabled=True,
            requires_api_key=True,
            cost_per_call=0.01,
            cache_duration_days=90,  # Walk scores don't change often
            rate_limit_per_hour=100,
        )

    async def enrich(
        self,
        latitude: float,
        longitude: float,
        address: str,
        property_data: Optional[Dict[str, Any]] = None,
        user_preferences: Optional[Dict[str, Any]] = None,
    ) -> ProviderResult:
        """Get walk, bike, and transit scores."""
        try:
            result = await self.api_client.get_score(lat=latitude, lon=longitude, address=address)

            data = {
                "walk_score": result.get("walkscore"),
                "bike_score": result.get("bike", {}).get("score"),
                "transit_score": result.get("transit", {}).get("score"),
                "description": result.get("description"),
            }

            return ProviderResult(
                provider_name=self.metadata.name,
                data=data,
                success=True,
                api_calls_made=1,
            )

        except Exception as e:
            logger.error("Walk Score API error: %s", str(e))
            return ProviderResult(
                provider_name=self.metadata.name,
                data={},
                success=False,
                error_message=str(e),
                api_calls_made=0,
            )

    async def validate_config(self) -> bool:
        """Validate API key is configured."""
        return await self.api_client.validate_api_key()

    def should_run(self, user_preferences: Optional[Dict[str, Any]] = None) -> bool:
        """Run if user cares about walkability."""
        if not super().should_run(user_preferences):
            return False

        # Run if user has walkability preferences set
        if user_preferences:
            return any(
                [
                    user_preferences.get("min_walk_score"),
                    user_preferences.get("min_bike_score"),
                    user_preferences.get("min_transit_score"),
                ]
            )

        # Default to running
        return True
