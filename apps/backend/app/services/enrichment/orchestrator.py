"""Dynamic enrichment orchestrator using provider registry."""

import asyncio
import logging
from typing import Any, Dict, List, Optional

from app.services.cache_service import CacheService
from app.services.enrichment.base_provider import ProviderCategory, ProviderResult
from app.services.enrichment.provider_registry import registry

logger = logging.getLogger(__name__)


class EnrichmentOrchestrator:
    """
    Dynamic orchestrator that automatically uses all registered providers.

    No code changes needed when adding new providers - just drop them in
    the providers directory and they'll be automatically discovered and used.
    """

    def __init__(self):
        self.cache_service = CacheService()
        self.provider_registry = registry

    async def enrich(
        self,
        latitude: float,
        longitude: float,
        address: str,
        property_data: Optional[Dict[str, Any]] = None,
        user_preferences: Optional[Dict[str, Any]] = None,
        use_cached: bool = True,
        provider_filter: Optional[List[str]] = None,
        category_filter: Optional[List[ProviderCategory]] = None,
    ) -> Dict[str, Any]:
        """
        Enrich a location using all applicable providers.

        Args:
            latitude: Property latitude
            longitude: Property longitude
            address: Property address
            property_data: Optional listing facts (bedrooms, square_feet, ...)
            user_preferences: Provider inputs (amenities, preferred places, custom locations)
            use_cached: Whether to use cached provider results if available
            provider_filter: Optional list of specific provider names to run
            category_filter: Optional list of categories to run

        Returns:
            Dictionary with all enrichment data organized by provider
        """
        user_preferences = user_preferences or {}
        providers = self._get_applicable_providers(
            provider_filter=provider_filter,
            category_filter=category_filter,
            user_preferences=user_preferences,
        )

        logger.info(
            "Running %d providers for (%.6f, %.6f): %s",
            len(providers),
            latitude,
            longitude,
            [p.metadata.name for p in providers],
            extra={
                "latitude": latitude,
                "longitude": longitude,
                "provider_count": len(providers),
                "providers": [p.metadata.name for p in providers],
            },
        )

        results = await self._execute_providers(
            providers=providers,
            latitude=latitude,
            longitude=longitude,
            address=address,
            property_data=property_data or {},
            user_preferences=user_preferences,
            use_cached=use_cached,
        )

        success_count = sum(1 for r in results if r.success)
        logger.info(
            "Enrichment completed: %d/%d providers successful",
            success_count,
            len(results),
            extra={
                "total_providers": len(results),
                "successful": success_count,
                "failed": len(results) - success_count,
            },
        )

        return self._format_response(results)

    def _get_applicable_providers(
        self,
        provider_filter: Optional[List[str]] = None,
        category_filter: Optional[List[ProviderCategory]] = None,
        user_preferences: Optional[Dict[str, Any]] = None,
    ) -> List:
        """Get list of providers to run based on filters and preferences."""
        # Start with all enabled providers
        providers = self.provider_registry.get_enabled_providers()

        # Filter by provider names if specified
        if provider_filter:
            providers = [p for p in providers if p.metadata.name in provider_filter]

        # Filter by categories if specified
        if category_filter:
            providers = [p for p in providers if p.metadata.category in category_filter]

        # Filter based on user preferences and provider logic
        providers = [p for p in providers if p.should_run(user_preferences=user_preferences)]

        return providers

    async def _execute_providers(
        self,
        providers: List,
        latitude: float,
        longitude: float,
        address: str,
        property_data: Dict[str, Any],
        user_preferences: Dict[str, Any],
        use_cached: bool,
    ) -> List[ProviderResult]:
        """Execute all providers in parallel."""
        # Create tasks for each provider
        tasks = []
        for provider in providers:
            task = self._run_provider_with_cache(
                provider=provider,
                latitude=latitude,
                longitude=longitude,
                address=address,
                property_data=property_data,
                user_preferences=user_preferences,
                use_cached=use_cached,
            )
            tasks.append(task)

        # Execute all tasks in parallel
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Filter out exceptions and log them
        valid_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                provider_name = providers[i].metadata.name
                logger.error(
                    "Provider %s failed: %s",
                    provider_name,
                    str(result),
                    extra={
                        "provider": provider_name,
                        "error": str(result),
                        "error_type": type(result).__name__,
                    },
                    exc_info=result,
                )
            elif isinstance(result, ProviderResult):
                valid_results.append(result)

        return valid_results

    async def _run_provider_with_cache(
        self,
        provider,
        latitude: float,
        longitude: float,
        address: str,
        property_data: Dict[str, Any],
        user_preferences: Dict[str, Any],
        use_cached: bool,
    ) -> ProviderResult:
        """Run a provider with caching support."""
        # Check cache if enabled
        if use_cached:
            cache_key = provider.get_cache_key(latitude=latitude, longitude=longitude)
            cached_result = await self.cache_service.get(cache_key)

            if cached_result:
                logger.info(
                    "Cache hit for provider %s at (%.6f, %.6f)",
                    provider.metadata.name,
                    latitude,
                    longitude,
                    extra={
                        "provider": provider.metadata.name,
                        "cached": True,
                        "latitude": latitude,
                        "longitude": longitude,
                    },
                )
                return ProviderResult(
                    provider_name=provider.metadata.name,
                    data=cached_result,
                    success=True,
                    cached=True,
                    api_calls_made=0,
                )

        # Run provider
        try:
            logger.info(
                "Executing provider %s for (%.6f, %.6f)",
                provider.metadata.name,
                latitude,
                longitude,
                extra={
                    "provider": provider.metadata.name,
                    "latitude": latitude,
                    "longitude": longitude,
                },
            )

            result = await provider.enrich(
                latitude=latitude,
                longitude=longitude,
                address=address,
                property_data=property_data,
                user_preferences=user_preferences,
            )

            # Log provider result
            logger.info(
                "Provider %s completed: success=%s, api_calls=%d",
                provider.metadata.name,
                result.success,
                result.api_calls_made,
                extra={
                    "provider": provider.metadata.name,
                    "success": result.success,
                    "api_calls": result.api_calls_made,
                    "has_data": bool(result.data),
                },
            )

            # Cache the result
            if result.success and result.data:
                cache_key = provider.get_cache_key(latitude=latitude, longitude=longitude)
                await self.cache_service.set(
                    key=cache_key,
                    value=result.data,
                    ttl_days=provider.metadata.cache_duration_days,
                )
                logger.debug(
                    "Cached result for provider %s (TTL: %d days)",
                    provider.metadata.name,
                    provider.metadata.cache_duration_days,
                    extra={
                        "provider": provider.metadata.name,
                        "ttl_days": provider.metadata.cache_duration_days,
                    },
                )

            return result

        except Exception as e:
            logger.error(
                "Provider %s execution failed: %s",
                provider.metadata.name,
                str(e),
                extra={"provider": provider.metadata.name, "error": str(e)},
                exc_info=True,
            )
            # Return error result instead of raising
            return ProviderResult(
                provider_name=provider.metadata.name,
                data={},
                success=False,
                cached=False,
                api_calls_made=0,
                error_message=str(e),
            )

    def _format_response(self, results: List[ProviderResult]) -> Dict[str, Any]:
        """Format provider results into a structured response."""
        response = {
            "success": True,
            "enrichment_data": {},
            "metadata": {
                "total_providers": len(results),
                "successful_providers": sum(1 for r in results if r.success),
                "failed_providers": sum(1 for r in results if not r.success),
                "total_api_calls": sum(r.api_calls_made for r in results),
                "cached_providers": sum(1 for r in results if r.cached),
            },
        }

        # Organize by provider
        for result in results:
            response["enrichment_data"][result.provider_name] = {
                "data": result.data,
                "success": result.success,
                "cached": result.cached,
                "error": result.error_message,
                "enriched_at": (result.enriched_at.isoformat() if result.enriched_at else None),
            }

        return response
