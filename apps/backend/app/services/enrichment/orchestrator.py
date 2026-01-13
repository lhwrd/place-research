"""Dynamic enrichment orchestrator using provider registry."""

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import and_
from sqlalchemy.orm import Session

from app.exceptions import EnrichmentRateLimitError, PropertyNotFoundError
from app.models.property import Property
from app.models.property_enrichment import PropertyEnrichment
from app.models.user_preference import UserPreference
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

    CACHE_DURATION_DAYS = 30
    ENRICHMENT_RATE_LIMIT = 10

    def __init__(self, db: Session):
        self.db = db
        self.cache_service = CacheService(db)
        self.provider_registry = registry

    async def enrich_property(
        self,
        property_id: int,
        user_id: int,
        use_cached: bool = True,
        provider_filter: Optional[List[str]] = None,
        category_filter: Optional[List[ProviderCategory]] = None,
    ) -> Dict[str, Any]:
        """
        Enrich a property using all applicable providers.

        Args:
            property_id: ID of the property to enrich
            user_id: ID of the user requesting enrichment
            use_cached:  Whether to use cached data if available
            provider_filter: Optional list of specific provider names to run
            category_filter: Optional list of categories to run

        Returns:
            Dictionary with all enrichment data organized by provider
        """
        logger.info(
            "Starting property enrichment: property_id=%d, user_id=%d, use_cached=%s",
            property_id,
            user_id,
            use_cached,
            extra={
                "property_id": property_id,
                "user_id": user_id,
                "use_cached": use_cached,
                "provider_filter": provider_filter,
                "category_filter": category_filter,
            },
        )

        # Get property
        property_record = await self._get_property(property_id, user_id)

        # Check rate limits
        if not use_cached:
            await self._check_rate_limit(user_id)

        # Get user preferences
        user_preferences = await self._get_user_preferences(user_id)
        user_prefs_dict = self._preferences_to_dict(user_preferences)

        # Get applicable providers
        providers = self._get_applicable_providers(
            provider_filter=provider_filter,
            category_filter=category_filter,
            user_preferences=user_prefs_dict,
        )

        logger.info(
            "Running %d providers for property %d: %s",
            len(providers),
            property_id,
            [p.metadata.name for p in providers],
            extra={
                "property_id": property_id,
                "provider_count": len(providers),
                "providers": [p.metadata.name for p in providers],
            },
        )

        # Execute all providers in parallel
        results = await self._execute_providers(
            providers=providers,
            property_record=property_record,
            user_preferences=user_prefs_dict,
            use_cached=use_cached,
        )

        # Save results to database
        await self._save_enrichment_results(property_id, results)

        # Track API usage
        await self._track_api_usage(user_id, results)

        # Log completion summary
        success_count = sum(1 for r in results if r.success)
        error_count = len(results) - success_count
        logger.info(
            "Property enrichment completed: property_id=%d, %d/%d providers successful",
            property_id,
            success_count,
            len(results),
            extra={
                "property_id": property_id,
                "total_providers": len(results),
                "successful": success_count,
                "failed": error_count,
            },
        )

        # Format response
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
        property_record: Property,
        user_preferences: Dict[str, Any],
        use_cached: bool,
    ) -> List[ProviderResult]:
        """Execute all providers in parallel."""
        property_data = {
            "bedrooms": property_record.bedrooms,
            "bathrooms": property_record.bathrooms,
            "square_feet": property_record.square_feet,
            "year_built": property_record.year_built,
            "property_type": property_record.property_type,
        }

        # Create tasks for each provider
        tasks = []
        for provider in providers:
            task = self._run_provider_with_cache(
                provider=provider,
                latitude=property_record.latitude,
                longitude=property_record.longitude,
                address=property_record.address,
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

    async def _save_enrichment_results(
        self, property_id: int, results: List[ProviderResult]
    ) -> None:
        """Save enrichment results to database."""
        # Get or create enrichment record
        enrichment = (
            self.db.query(PropertyEnrichment)
            .filter(PropertyEnrichment.property_id == property_id)
            .first()
        )

        if not enrichment:
            enrichment = PropertyEnrichment(
                property_id=property_id, enriched_at=datetime.now(timezone.utc)
            )
            self.db.add(enrichment)

        # Organize results by category/type
        for result in results:
            if not result.success:
                continue

            provider_name = result.provider_name
            data = result.data

            # Store in appropriate column based on provider name/category
            # This is where you'd map provider results to database columns
            self._map_result_to_enrichment(enrichment, provider_name, data)

        enrichment.updated_at = datetime.now(timezone.utc)
        enrichment.enriched_at = datetime.now(timezone.utc)

        self.db.commit()

    def _map_result_to_enrichment(
        self, enrichment: PropertyEnrichment, provider_name: str, data: Dict[str, Any]
    ) -> None:
        """Map provider results to enrichment database fields."""
        # This is a flexible mapping system
        # You can use a JSON column for dynamic data or specific columns

        # Get existing dynamic data or initialize
        if not hasattr(enrichment, "dynamic_enrichment_data"):
            # This assumes you add a JSON column called dynamic_enrichment_data
            enrichment.dynamic_enrichment_data = {}

        # Store provider data in dynamic JSON field
        if enrichment.dynamic_enrichment_data is None:
            enrichment.dynamic_enrichment_data = {}

        enrichment.dynamic_enrichment_data[provider_name] = data

        # Also handle known providers with dedicated columns
        if provider_name == "walk_score":
            enrichment.walk_score = data.get("walk_score")
            enrichment.bike_score = data.get("bike_score")
            enrichment.transit_score = data.get("transit_score")
            enrichment.walk_score_description = data.get("description")

        elif provider_name == "nearby_places":
            enrichment.nearby_grocery_stores = data.get("grocery_store", [])
            enrichment.nearby_parks = data.get("park", [])
            enrichment.nearby_restaurants = data.get("restaurant", [])

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

    async def _get_property(self, property_id: int, user_id: int) -> Property:
        """Get property and verify access."""
        property_record = self.db.query(Property).filter(Property.id == property_id).first()

        if not property_record or property_record.user_id != user_id:
            raise PropertyNotFoundError(property_id=property_id)

        return property_record

    async def _check_rate_limit(self, user_id: int) -> None:
        """Check enrichment rate limits."""
        from app.models.api_usage import APIUsage

        one_hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)
        enrichment_count = (
            self.db.query(APIUsage)
            .filter(
                and_(
                    APIUsage.user_id == user_id,
                    APIUsage.service_name == "enrichment",
                    APIUsage.called_at >= one_hour_ago,
                )
            )
            .count()
        )

        if enrichment_count >= self.ENRICHMENT_RATE_LIMIT:
            raise EnrichmentRateLimitError(retry_after=3600)

    async def _get_user_preferences(self, user_id: int) -> Optional[UserPreference]:
        """Get user preferences."""
        return self.db.query(UserPreference).filter(UserPreference.user_id == user_id).first()

    def _preferences_to_dict(self, preferences: Optional[UserPreference]) -> Dict[str, Any]:
        """Convert preferences model to dictionary."""
        if not preferences:
            return {}

        return {
            "user_id": preferences.user_id,
            "min_walk_score": preferences.min_walk_score,
            "min_bike_score": preferences.min_bike_score,
            "max_grocery_distance": preferences.max_grocery_distance,
            "max_park_distance": preferences.max_park_distance,
            "preferred_amenities": preferences.preferred_amenities,
        }

    async def _track_api_usage(self, user_id: int, results: List[ProviderResult]) -> None:
        """Track API usage from all providers."""
        from app.models.api_usage import APIUsage

        for result in results:
            if result.api_calls_made > 0:
                usage = APIUsage(
                    user_id=user_id,
                    service_name=result.provider_name,
                    calls_count=result.api_calls_made,
                    called_at=datetime.now(timezone.utc),
                )
                self.db.add(usage)

        self.db.commit()
