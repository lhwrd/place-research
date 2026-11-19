"""Dynamic enrichment orchestrator using provider registry."""

import asyncio
import hashlib
import json
import logging
from typing import Any, Dict, Iterable, List, Optional

from app.services.cache_service import CacheService
from app.services.enrichment.base_provider import ProviderCategory, ProviderResult
from app.services.enrichment.provider_registry import registry

logger = logging.getLogger(__name__)

# After the deadline, how much longer providers still running get before they're given up on
LATE_LIMIT_SECONDS = 90.0


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
        deadline_seconds: Optional[float] = None,
        late_limit_seconds: float = LATE_LIMIT_SECONDS,
    ) -> Dict[str, Any]:
        """
        Enrich a location using all applicable providers.

        With a deadline, returns once it passes with the providers that finished by then.
        The rest keep running: response["late"] is then a task that resolves to a response
        of the same shape for them, once they finish or late_limit_seconds more have passed
        (the stragglers are then cancelled and reported as failed). The caller must await
        it. Without a deadline, "late" is None and every provider is in the response.

        Args:
            latitude: Property latitude
            longitude: Property longitude
            address: Property address
            property_data: Optional listing facts (bedrooms, square_feet, ...)
            user_preferences: Provider inputs (amenities, preferred places, custom locations)
            use_cached: Whether to use cached provider results if available
            provider_filter: Optional list of specific provider names to run
            category_filter: Optional list of categories to run
            deadline_seconds: How long to wait before returning (None: until all finish)
            late_limit_seconds: After the deadline, how long the rest still get

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

        tasks = self._start_providers(
            providers=providers,
            latitude=latitude,
            longitude=longitude,
            address=address,
            property_data=property_data or {},
            user_preferences=user_preferences,
            use_cached=use_cached,
        )
        done, pending = await _wait(tasks, deadline_seconds)
        results = _collect(tasks, done)
        _log_completed(results)

        response = self._format_response(results)
        response["late"] = None
        response["metadata"]["pending_providers"] = sorted(tasks[t] for t in pending)
        if pending:
            logger.info(
                "Deadline of %.0fs passed; still waiting on %s",
                deadline_seconds,
                response["metadata"]["pending_providers"],
                extra={"pending_providers": response["metadata"]["pending_providers"]},
            )
            late = {t: tasks[t] for t in pending}
            response["late"] = asyncio.create_task(self._finish_late(late, late_limit_seconds))
        return response

    async def _finish_late(
        self, tasks: Dict[asyncio.Task, str], limit_seconds: float
    ) -> Dict[str, Any]:
        """Wait for providers still running after the deadline; give up after limit_seconds."""
        done, pending = await _wait(tasks, limit_seconds)
        for task in pending:
            task.cancel()
        await asyncio.gather(*pending, return_exceptions=True)

        results = _collect(tasks, done)
        for task in pending:
            logger.warning(
                "Provider %s gave up: still running %.0fs after the deadline",
                tasks[task],
                limit_seconds,
                extra={"provider": tasks[task]},
            )
            results.append(
                ProviderResult(
                    provider_name=tasks[task],
                    data={},
                    success=False,
                    error_message=f"Gave up after {limit_seconds:.0f}s more than the deadline",
                )
            )
        _log_completed(results)
        response = self._format_response(results)
        response["late"] = None
        response["metadata"]["pending_providers"] = []
        return response

    def provider_info(
        self, user_preferences: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Dict[str, Any]]:
        """
        What a caller needs to decide whether a provider's stored result is still good.

        Returns:
            Provider name -> {"max_age_days", "inputs"} for every provider that would run.
            inputs is a fingerprint of the settings the result depends on (None if it
            depends only on the location).
        """
        info = {}
        for provider in self._get_applicable_providers(user_preferences=user_preferences):
            inputs = provider.inputs(user_preferences)
            info[provider.metadata.name] = {
                "max_age_days": provider.metadata.cache_duration_days,
                "inputs": None if inputs is None else _fingerprint(inputs),
            }
        return info

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

    async def _execute_providers(self, **kwargs) -> List[ProviderResult]:
        """Execute all providers in parallel and wait for every one."""
        tasks = self._start_providers(**kwargs)
        done, _ = await _wait(tasks, None)
        return _collect(tasks, done)

    def _start_providers(
        self,
        providers: List,
        latitude: float,
        longitude: float,
        address: str,
        property_data: Dict[str, Any],
        user_preferences: Dict[str, Any],
        use_cached: bool,
    ) -> Dict[asyncio.Task, str]:
        """Start every provider running. Returns task -> provider name, in provider order."""
        return {
            asyncio.ensure_future(
                self._run_provider_with_cache(
                    provider=provider,
                    latitude=latitude,
                    longitude=longitude,
                    address=address,
                    property_data=property_data,
                    user_preferences=user_preferences,
                    use_cached=use_cached,
                )
            ): provider.metadata.name
            for provider in providers
        }

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


async def _wait(tasks: Iterable[asyncio.Task], timeout: Optional[float]) -> tuple:
    """asyncio.wait, which refuses an empty set. Returns (done, pending)."""
    tasks = set(tasks)
    if not tasks:
        return set(), set()
    return await asyncio.wait(tasks, timeout=timeout)


def _collect(tasks: Dict[asyncio.Task, str], done: set) -> List[ProviderResult]:
    """Results of the finished tasks, in provider order. Exceptions are logged and dropped."""
    results = []
    for task, provider_name in tasks.items():
        if task not in done:
            continue
        error = task.exception()
        if error is not None:
            logger.error(
                "Provider %s failed: %s",
                provider_name,
                str(error),
                extra={
                    "provider": provider_name,
                    "error": str(error),
                    "error_type": type(error).__name__,
                },
                exc_info=error,
            )
        elif isinstance(task.result(), ProviderResult):
            results.append(task.result())
    return results


def _log_completed(results: List[ProviderResult]) -> None:
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


def _fingerprint(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()[:16]
