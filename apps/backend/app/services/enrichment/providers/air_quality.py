from app.integrations.air_quality_api import AirQualityAPIClient

from ..base_provider import (
    BaseEnrichmentProvider,
    ProviderCategory,
    ProviderMetadata,
    ProviderResult,
)


class AirQualityProvider(BaseEnrichmentProvider):
    def __init__(self):
        self.api_client = AirQualityAPIClient()

    @property
    def metadata(self) -> ProviderMetadata:
        return ProviderMetadata(
            name="AirQualityProvider",
            category=ProviderCategory.ENVIRONMENTAL,
            enabled=True,
            description="Provides air quality data using the AirNow API.",
            version="1.0.0",
            requires_api_key=True,
            cost_per_call=0.0,
        )

    async def enrich(
        self,
        latitude: float,
        longitude: float,
        address: str,
        property_data=None,
        user_preferences=None,
    ) -> ProviderResult:
        """Fetch air quality data for a specific place."""
        api_response = await self.api_client.get_air_quality(latitude=latitude, longitude=longitude)
        success = bool(api_response)
        error_message = None if success else "Failed to fetch air quality data"
        return ProviderResult(
            provider_name=self.metadata.name,
            data=api_response,
            success=success,
            error_message=error_message,
            api_calls_made=1,
            cached=False,
        )

    async def validate_config(self) -> bool:
        """Validate that the API key is set and valid."""
        is_valid = await self.api_client.validate_api_key()
        return is_valid
