"""
Caching layer for place enrichment data.

Supports multiple backends:
- InMemoryCache: Simple dict-based cache for development
- RedisCache: Redis-backed cache for production

Cache keys are generated from provider name + location coordinates.
"""

import json
import logging
import time
from abc import ABC, abstractmethod
from typing import Any, Optional

logger = logging.getLogger(__name__)


class CacheBackend(ABC):
    """Abstract base class for cache backends."""

    @abstractmethod
    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache."""

    @abstractmethod
    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Set value in cache with optional TTL (seconds)."""

    @abstractmethod
    async def delete(self, key: str) -> None:
        """Delete value from cache."""

    @abstractmethod
    async def clear(self) -> None:
        """Clear all cache entries."""

    @abstractmethod
    async def exists(self, key: str) -> bool:
        """Check if key exists in cache."""

    @abstractmethod
    async def get_stats(self) -> dict:
        """Get cache statistics."""


class InMemoryCache(CacheBackend):
    """
    In-memory cache implementation using a dictionary.

    Suitable for development and single-instance deployments.
    Data is lost when the process restarts.
    """

    def __init__(self):
        self._cache: dict[str, tuple[Any, Optional[float]]] = {}
        self._hits = 0
        self._misses = 0
        self._sets = 0
        logger.info("Initialized InMemoryCache")

    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache, checking expiration."""
        if key not in self._cache:
            self._misses += 1
            logger.debug("Cache miss: %s", key)
            return None

        value, expires_at = self._cache[key]

        # Check expiration
        if expires_at is not None and time.time() > expires_at:
            del self._cache[key]
            self._misses += 1
            logger.debug("Cache miss (expired): %s", key)
            return None

        self._hits += 1
        logger.debug("Cache hit: %s", key)
        return value

    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Set value in cache with optional TTL."""
        expires_at = time.time() + ttl if ttl else None
        self._cache[key] = (value, expires_at)
        self._sets += 1
        logger.debug("Cache set: %s (TTL: %ss)", key, ttl)

    async def delete(self, key: str) -> None:
        """Delete value from cache."""
        if key in self._cache:
            del self._cache[key]
            logger.debug("Cache delete: %s", key)

    async def clear(self) -> None:
        """Clear all cache entries."""
        count = len(self._cache)
        self._cache.clear()
        logger.info("Cache cleared: %s entries removed", count)

    async def exists(self, key: str) -> bool:
        """Check if key exists and is not expired."""
        if key not in self._cache:
            return False

        _, expires_at = self._cache[key]
        if expires_at is not None and time.time() > expires_at:
            del self._cache[key]
            return False

        return True

    async def get_stats(self) -> dict:
        """Get cache statistics."""
        # Clean expired entries
        expired_keys = []
        current_time = time.time()
        for key, (_, expires_at) in self._cache.items():
            if expires_at is not None and current_time > expires_at:
                expired_keys.append(key)

        for key in expired_keys:
            del self._cache[key]

        total_requests = self._hits + self._misses
        hit_rate = self._hits / total_requests if total_requests > 0 else 0

        return {
            "backend": "memory",
            "size": len(self._cache),
            "hits": self._hits,
            "misses": self._misses,
            "sets": self._sets,
            "hit_rate": round(hit_rate, 3),
            "total_requests": total_requests,
        }


class RedisCache(CacheBackend):
    """
    Redis-backed cache implementation.

    Suitable for production with multiple instances.
    Requires Redis server to be running.
    """

    def __init__(self, redis_url: str):
        """
        Initialize Redis cache.

        Args:
            redis_url: Redis connection URL (e.g., redis://localhost:6379/0)
        """
        try:
            import redis.asyncio as redis

            self._redis_module = redis
        except ImportError as exc:
            raise ImportError(
                "redis package is required for RedisCache. "
                "Install with: pip install redis"
            ) from exc

        self.redis_url = redis_url
        self._client: Optional[Any] = None
        self._hits = 0
        self._misses = 0
        self._sets = 0
        logger.info("Initialized RedisCache with URL: %s", redis_url)

    async def _get_client(self):
        """Lazy initialization of Redis client."""
        if self._client is None:
            self._client = self._redis_module.from_url(
                self.redis_url,
                encoding="utf-8",
                decode_responses=False,  # We'll handle JSON serialization
            )
        return self._client

    async def get(self, key: str) -> Optional[Any]:
        """Get value from Redis cache."""
        try:
            client = await self._get_client()
            value = await client.get(key)

            if value is None:
                self._misses += 1
                logger.debug("Cache miss: %s", key)
                return None

            self._hits += 1
            logger.debug("Cache hit: %s", key)

            # Deserialize JSON
            return json.loads(value)
        except (json.JSONDecodeError, ConnectionError, TimeoutError) as e:
            logger.error("Redis get error for key %s: %s", key, e)
            self._misses += 1
            return None

    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Set value in Redis cache with optional TTL."""
        try:
            client = await self._get_client()

            # Serialize to JSON
            serialized = json.dumps(value)

            if ttl:
                await client.setex(key, ttl, serialized)
            else:
                await client.set(key, serialized)

            self._sets += 1
            logger.debug("Cache set: %s (TTL: %ss)", key, ttl)
        except (json.JSONDecodeError, ConnectionError, TimeoutError) as e:
            logger.error("Redis set error for key %s: %s", key, e)

    async def delete(self, key: str) -> None:
        """Delete value from Redis cache."""
        try:
            client = await self._get_client()
            await client.delete(key)
            logger.debug("Cache delete: %s", key)
        except (ConnectionError, TimeoutError) as e:
            logger.error("Redis delete error for key %s: %s", key, e)

    async def clear(self) -> None:
        """Clear all cache entries (flushdb)."""
        try:
            client = await self._get_client()
            await client.flushdb()
            logger.info("Cache cleared: Redis flushdb executed")
        except (ConnectionError, TimeoutError) as e:
            logger.error("Redis clear error: %s", e)

    async def exists(self, key: str) -> bool:
        """Check if key exists in Redis."""
        try:
            client = await self._get_client()
            return await client.exists(key) > 0
        except (ConnectionError, TimeoutError) as e:
            logger.error("Redis exists error for key %s: %s", key, e)
            return False

    async def get_stats(self) -> dict:
        """Get cache statistics."""
        try:
            client = await self._get_client()
            info = await client.info("stats")
            dbsize = await client.dbsize()

            total_requests = self._hits + self._misses
            hit_rate = self._hits / total_requests if total_requests > 0 else 0

            return {
                "backend": "redis",
                "size": dbsize,
                "hits": self._hits,
                "misses": self._misses,
                "sets": self._sets,
                "hit_rate": round(hit_rate, 3),
                "total_requests": total_requests,
                "redis_stats": {
                    "keyspace_hits": info.get("keyspace_hits", 0),
                    "keyspace_misses": info.get("keyspace_misses", 0),
                    "used_memory_human": info.get("used_memory_human", "unknown"),
                },
            }
        except (ConnectionError, TimeoutError) as e:
            logger.error("Redis stats error: %s", e)
            total_requests = self._hits + self._misses
            hit_rate = self._hits / total_requests if total_requests > 0 else 0

            return {
                "backend": "redis",
                "hits": self._hits,
                "misses": self._misses,
                "sets": self._sets,
                "hit_rate": round(hit_rate, 3),
                "total_requests": total_requests,
                "error": str(e),
            }

    async def close(self):
        """Close Redis connection."""
        if self._client:
            await self._client.close()
            logger.info("Redis connection closed")


class CacheManager:
    """
    Manages caching for place enrichment data.

    Generates cache keys from provider name and location coordinates.
    Supports configurable TTLs per provider.
    """

    def __init__(
        self,
        backend: CacheBackend,
        default_ttl: int = 3600,
        provider_ttls: Optional[dict[str, int]] = None,
    ):
        """
        Initialize cache manager.

        Args:
            backend: Cache backend to use
            default_ttl: Default TTL in seconds (default: 1 hour)
            provider_ttls: Custom TTLs per provider (e.g., {"air_quality": 1800})
        """
        self.backend = backend
        self.default_ttl = default_ttl
        self.provider_ttls = provider_ttls or {}
        logger.info(
            "Initialized CacheManager (default TTL: %ss, custom TTLs: %s)",
            default_ttl,
            len(self.provider_ttls),
        )

    def _generate_cache_key(
        self,
        provider: str,
        latitude: float,
        longitude: float,
        precision: int = 4,
    ) -> str:
        """
        Generate cache key from provider and coordinates.

        Args:
            provider: Provider name (e.g., "air_quality")
            latitude: Latitude coordinate
            longitude: Longitude coordinate
            precision: Decimal precision for coordinates (default: 4 = ~11m accuracy)

        Returns:
            Cache key string
        """
        # Round coordinates to reduce cache fragmentation
        # precision=4 gives ~11 meter accuracy
        lat_rounded = round(latitude, precision)
        lng_rounded = round(longitude, precision)

        # Create cache key: provider:lat:lng
        key = f"{provider}:{lat_rounded}:{lng_rounded}"

        return key

    def _get_ttl(self, provider: str) -> int:
        """Get TTL for provider (custom or default)."""
        return self.provider_ttls.get(provider, self.default_ttl)

    async def get_provider_result(
        self,
        provider: str,
        latitude: float,
        longitude: float,
    ) -> Optional[dict]:
        """
        Get cached provider result.

        Args:
            provider: Provider name
            latitude: Latitude coordinate
            longitude: Longitude coordinate

        Returns:
            Cached result dict or None if not cached
        """
        key = self._generate_cache_key(provider, latitude, longitude)
        result = await self.backend.get(key)

        if result:
            logger.info("Cache hit for %s at (%s, %s)", provider, latitude, longitude)
        else:
            logger.info("Cache miss for %s at (%s, %s)", provider, latitude, longitude)

        return result

    async def set_provider_result(
        self,
        provider: str,
        latitude: float,
        longitude: float,
        result: dict,
    ) -> None:
        """
        Cache provider result.

        Args:
            provider: Provider name
            latitude: Latitude coordinate
            longitude: Longitude coordinate
            result: Provider result to cache
        """
        key = self._generate_cache_key(provider, latitude, longitude)
        ttl = self._get_ttl(provider)

        await self.backend.set(key, result, ttl=ttl)
        logger.info(
            "Cached %s result at (%s, %s) with TTL %ss",
            provider,
            latitude,
            longitude,
            ttl,
        )

    async def invalidate_provider_result(
        self,
        provider: str,
        latitude: float,
        longitude: float,
    ) -> None:
        """
        Invalidate cached provider result.

        Args:
            provider: Provider name
            latitude: Latitude coordinate
            longitude: Longitude coordinate
        """
        key = self._generate_cache_key(provider, latitude, longitude)
        await self.backend.delete(key)
        logger.info(
            "Invalidated cache for %s at (%s, %s)", provider, latitude, longitude
        )

    async def clear_all(self) -> None:
        """Clear all cache entries."""
        await self.backend.clear()

    async def get_stats(self) -> dict:
        """Get cache statistics."""
        return await self.backend.get_stats()


# Singleton cache manager instance
_cache_manager: Optional[CacheManager] = None


def get_cache_manager() -> Optional[CacheManager]:
    """Get the global cache manager instance."""
    return _cache_manager


def initialize_cache(
    backend_type: str = "memory",
    redis_url: Optional[str] = None,
    default_ttl: int = 3600,
    provider_ttls: Optional[dict[str, int]] = None,
) -> CacheManager:
    """
    Initialize the global cache manager.

    Args:
        backend_type: "memory" or "redis"
        redis_url: Redis connection URL (required for redis backend)
        default_ttl: Default TTL in seconds
        provider_ttls: Custom TTLs per provider

    Returns:
        Initialized CacheManager
    """
    global _cache_manager

    if backend_type == "memory":
        backend = InMemoryCache()
    elif backend_type == "redis":
        if not redis_url:
            raise ValueError("redis_url is required for redis backend")
        backend = RedisCache(redis_url)
    else:
        raise ValueError(f"Unknown backend type: {backend_type}")

    _cache_manager = CacheManager(
        backend=backend,
        default_ttl=default_ttl,
        provider_ttls=provider_ttls,
    )

    logger.info("Cache initialized with %s backend", backend_type)
    return _cache_manager
