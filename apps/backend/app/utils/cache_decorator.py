"""Cache decorator for easy function result caching."""

import hashlib
import logging
from functools import wraps
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


def cached(
    ttl_seconds: Optional[int] = None,
    ttl_days: Optional[int] = None,
    key_prefix: str = "",
    cache_service: Optional[Any] = None,
):
    """
    Decorator to cache function results.

    Args:
        ttl_seconds: Time to live in seconds
        ttl_days: Time to live in days
        key_prefix: Prefix for cache keys
        cache_service: Cache service instance (default: uses global instance)

    Example:
        @cached(ttl_days=7, key_prefix="walk_score")
        async def get_walk_score(lat: float, lon: float):
            # Expensive API call
            return await api. get_score(lat, lon)
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Import here to avoid circular dependency
            from app.db.database import SessionLocal
            from app.services.cache_service import CacheService

            # Use provided cache service or create new one
            if cache_service:
                cache = cache_service
            else:
                db = SessionLocal()
                cache = CacheService(db)

            # Generate cache key
            cache_key = _generate_cache_key(func, key_prefix, *args, **kwargs)

            # Try to get from cache
            cached_value = await cache.get(cache_key)

            if cached_value is not None:
                logger.debug(f"Using cached result for {func.__name__}")
                return cached_value

            # Call function
            result = await func(*args, **kwargs)

            # Cache result
            await cache.set(cache_key, result, ttl_seconds=ttl_seconds, ttl_days=ttl_days)

            logger.debug(f"Cached result for {func.__name__}")

            return result

        return wrapper

    return decorator


def _generate_cache_key(func: Callable, prefix: str, *args, **kwargs) -> str:
    """Generate cache key from function name and arguments."""
    # Start with prefix and function name
    key_parts = [prefix, func.__name__] if prefix else [func.__name__]

    # Add arguments
    key_parts.extend(str(arg) for arg in args)

    # Add keyword arguments (sorted for consistency)
    key_parts.extend(f"{k}={v}" for k, v in sorted(kwargs.items()))

    # Join and hash
    key_string = ":".join(key_parts)

    # For long keys, use hash
    if len(key_string) > 200:
        return f"{prefix}:{hashlib.md5(key_string.encode()).hexdigest()}"

    return key_string
