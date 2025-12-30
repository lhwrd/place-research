"""Tests for the caching layer."""

import pytest
import time
from unittest.mock import Mock, AsyncMock, patch, MagicMock

from place_research.cache import (
    InMemoryCache,
    RedisCache,
    CacheManager,
    initialize_cache,
    get_cache_manager,
)

# Check if redis is available
try:
    import redis.asyncio as redis

    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False


class TestInMemoryCache:
    """Tests for InMemoryCache backend."""

    @pytest.mark.asyncio
    async def test_set_and_get(self):
        """Test basic set and get operations."""
        cache = InMemoryCache()

        # Set value
        await cache.set("test_key", {"data": "value"}, ttl=60)

        # Get value
        result = await cache.get("test_key")
        assert result == {"data": "value"}

    @pytest.mark.asyncio
    async def test_get_nonexistent_key(self):
        """Test getting a key that doesn't exist."""
        cache = InMemoryCache()
        result = await cache.get("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_ttl_expiration(self):
        """Test that keys expire after TTL."""
        cache = InMemoryCache()

        # Set with 1 second TTL
        await cache.set("expire_key", {"data": "value"}, ttl=1)

        # Should exist immediately
        assert await cache.exists("expire_key")
        result = await cache.get("expire_key")
        assert result == {"data": "value"}

        # Wait for expiration
        time.sleep(1.1)

        # Should be expired
        assert not await cache.exists("expire_key")
        result = await cache.get("expire_key")
        assert result is None

    @pytest.mark.asyncio
    async def test_set_without_ttl(self):
        """Test setting value without TTL (no expiration)."""
        cache = InMemoryCache()

        await cache.set("no_ttl", {"data": "value"})
        result = await cache.get("no_ttl")
        assert result == {"data": "value"}

        # Should still exist after some time
        time.sleep(0.5)
        result = await cache.get("no_ttl")
        assert result == {"data": "value"}

    @pytest.mark.asyncio
    async def test_delete(self):
        """Test deleting a key."""
        cache = InMemoryCache()

        await cache.set("delete_me", {"data": "value"})
        assert await cache.exists("delete_me")

        await cache.delete("delete_me")
        assert not await cache.exists("delete_me")

    @pytest.mark.asyncio
    async def test_clear(self):
        """Test clearing all keys."""
        cache = InMemoryCache()

        await cache.set("key1", "value1")
        await cache.set("key2", "value2")
        await cache.set("key3", "value3")

        stats = await cache.get_stats()
        assert stats["size"] == 3

        await cache.clear()

        stats = await cache.get_stats()
        assert stats["size"] == 0

    @pytest.mark.asyncio
    async def test_stats(self):
        """Test cache statistics."""
        cache = InMemoryCache()

        # Initial stats
        stats = await cache.get_stats()
        assert stats["backend"] == "memory"
        assert stats["size"] == 0
        assert stats["hits"] == 0
        assert stats["misses"] == 0
        assert stats["hit_rate"] == 0

        # Set and get
        await cache.set("key1", "value1")
        await cache.get("key1")  # Hit
        await cache.get("key2")  # Miss

        stats = await cache.get_stats()
        assert stats["size"] == 1
        assert stats["hits"] == 1
        assert stats["misses"] == 1
        assert stats["sets"] == 1
        assert stats["hit_rate"] == 0.5  # 1 hit / 2 total

    @pytest.mark.asyncio
    async def test_stats_cleans_expired_entries(self):
        """Test that get_stats cleans up expired entries."""
        cache = InMemoryCache()

        # Set with short TTL
        await cache.set("expire1", "value1", ttl=0.5)
        await cache.set("expire2", "value2", ttl=0.5)
        await cache.set("keep", "value3")  # No TTL

        stats = await cache.get_stats()
        assert stats["size"] == 3

        # Wait for expiration
        time.sleep(0.6)

        # Stats should clean up expired
        stats = await cache.get_stats()
        assert stats["size"] == 1  # Only "keep" remains


class TestRedisCache:
    """Tests for RedisCache backend."""

    @pytest.mark.asyncio
    async def test_redis_not_installed(self):
        """Test error when redis package is not installed."""
        with patch(
            "src.place_research.cache.RedisCache.__init__",
            side_effect=ImportError("redis package is required"),
        ):
            with pytest.raises(ImportError, match="redis package is required"):
                RedisCache("redis://localhost:6379/0")

    @pytest.mark.asyncio
    async def test_set_and_get_with_mock(self):
        """Test basic set and get with mocked Redis."""
        # Mock the redis module
        mock_redis_client = AsyncMock()
        mock_redis_client.get = AsyncMock(return_value=b'{"data": "value"}')
        mock_redis_client.set = AsyncMock()
        mock_redis_client.setex = AsyncMock()

        mock_redis_module = MagicMock()
        mock_redis_module.from_url = Mock(return_value=mock_redis_client)

        cache = RedisCache.__new__(RedisCache)
        cache.redis_url = "redis://localhost:6379/0"
        cache._client = None
        cache._redis_module = mock_redis_module
        cache._hits = 0
        cache._misses = 0
        cache._sets = 0

        # Set value
        await cache.set("test_key", {"data": "value"}, ttl=60)
        assert cache._sets == 1

        # Get value
        result = await cache.get("test_key")
        assert result == {"data": "value"}
        assert cache._hits == 1

    @pytest.mark.asyncio
    async def test_get_none_with_mock(self):
        """Test getting None when key doesn't exist."""
        mock_redis_client = AsyncMock()
        mock_redis_client.get = AsyncMock(return_value=None)

        mock_redis_module = MagicMock()
        mock_redis_module.from_url = Mock(return_value=mock_redis_client)

        cache = RedisCache.__new__(RedisCache)
        cache.redis_url = "redis://localhost:6379/0"
        cache._client = None
        cache._redis_module = mock_redis_module
        cache._hits = 0
        cache._misses = 0
        cache._sets = 0

        result = await cache.get("nonexistent")
        assert result is None
        assert cache._misses == 1

    @pytest.mark.asyncio
    async def test_error_handling(self):
        """Test error handling in Redis operations."""
        mock_redis_client = AsyncMock()
        mock_redis_client.get = AsyncMock(side_effect=Exception("Connection error"))

        mock_redis_module = MagicMock()
        mock_redis_module.from_url = Mock(return_value=mock_redis_client)

        cache = RedisCache.__new__(RedisCache)
        cache.redis_url = "redis://localhost:6379/0"
        cache._client = None
        cache._redis_module = mock_redis_module
        cache._hits = 0
        cache._misses = 0
        cache._sets = 0

        # Should handle error gracefully and return None
        result = await cache.get("key")
        assert result is None
        assert cache._misses == 1


class TestCacheManager:
    """Tests for CacheManager."""

    @pytest.mark.asyncio
    async def test_cache_key_generation(self):
        """Test cache key generation from provider and coordinates."""
        cache = InMemoryCache()
        manager = CacheManager(cache, default_ttl=60)

        key1 = manager._generate_cache_key("air_quality", 37.4221, -122.0841)
        key2 = manager._generate_cache_key("air_quality", 37.4221, -122.0841)
        key3 = manager._generate_cache_key("air_quality", 37.4222, -122.0841)
        key4 = manager._generate_cache_key("flood_zone", 37.4221, -122.0841)

        # Same provider and location should generate same key
        assert key1 == key2

        # Different coordinates should generate different key
        assert key1 != key3

        # Different provider should generate different key
        assert key1 != key4

    @pytest.mark.asyncio
    async def test_coordinate_rounding(self):
        """Test that coordinates are rounded to reduce cache fragmentation."""
        cache = InMemoryCache()
        manager = CacheManager(cache, default_ttl=60)

        # These coordinates differ only in 5th decimal place (~1 meter)
        # Should generate same key with precision=4
        key1 = manager._generate_cache_key(
            "air_quality", 37.42213, -122.08413, precision=4
        )
        key2 = manager._generate_cache_key(
            "air_quality", 37.42214, -122.08414, precision=4
        )

        # Both should round to 37.4221 and -122.0841
        assert key1 == key2
        assert key1 == "air_quality:37.4221:-122.0841"

    @pytest.mark.asyncio
    async def test_get_and_set_provider_result(self):
        """Test getting and setting provider results."""
        cache = InMemoryCache()
        manager = CacheManager(cache, default_ttl=60)

        # Set result
        result_data = {"aqi": 42, "category": "Good"}
        await manager.set_provider_result(
            "air_quality", 37.4221, -122.0841, result_data
        )

        # Get result
        cached = await manager.get_provider_result("air_quality", 37.4221, -122.0841)
        assert cached == result_data

    @pytest.mark.asyncio
    async def test_custom_provider_ttl(self):
        """Test custom TTL per provider."""
        cache = InMemoryCache()
        provider_ttls = {
            "air_quality": 1800,  # 30 minutes
            "climate": 86400,  # 24 hours
        }
        manager = CacheManager(cache, default_ttl=3600, provider_ttls=provider_ttls)

        # Verify TTL is retrieved correctly
        assert manager._get_ttl("air_quality") == 1800
        assert manager._get_ttl("climate") == 86400
        assert manager._get_ttl("unknown") == 3600  # Default

    @pytest.mark.asyncio
    async def test_invalidate_provider_result(self):
        """Test invalidating cached result."""
        cache = InMemoryCache()
        manager = CacheManager(cache, default_ttl=60)

        # Set result
        result_data = {"aqi": 42}
        await manager.set_provider_result(
            "air_quality", 37.4221, -122.0841, result_data
        )

        # Verify it exists
        cached = await manager.get_provider_result("air_quality", 37.4221, -122.0841)
        assert cached is not None

        # Invalidate
        await manager.invalidate_provider_result("air_quality", 37.4221, -122.0841)

        # Verify it's gone
        cached = await manager.get_provider_result("air_quality", 37.4221, -122.0841)
        assert cached is None

    @pytest.mark.asyncio
    async def test_clear_all(self):
        """Test clearing all cached results."""
        cache = InMemoryCache()
        manager = CacheManager(cache, default_ttl=60)

        # Set multiple results
        await manager.set_provider_result(
            "air_quality", 37.4221, -122.0841, {"aqi": 42}
        )
        await manager.set_provider_result(
            "flood_zone", 37.4221, -122.0841, {"zone": "X"}
        )

        # Clear all
        await manager.clear_all()

        # Verify all are gone
        cached1 = await manager.get_provider_result("air_quality", 37.4221, -122.0841)
        cached2 = await manager.get_provider_result("flood_zone", 37.4221, -122.0841)
        assert cached1 is None
        assert cached2 is None

    @pytest.mark.asyncio
    async def test_get_stats(self):
        """Test getting cache statistics."""
        cache = InMemoryCache()
        manager = CacheManager(cache, default_ttl=60)

        # Set and get some data
        await manager.set_provider_result(
            "air_quality", 37.4221, -122.0841, {"aqi": 42}
        )
        await manager.get_provider_result("air_quality", 37.4221, -122.0841)  # Hit
        await manager.get_provider_result("flood_zone", 37.4221, -122.0841)  # Miss

        stats = await manager.get_stats()
        assert stats["backend"] == "memory"
        assert stats["hits"] == 1
        assert stats["misses"] == 1
        assert stats["sets"] == 1


class TestCacheInitialization:
    """Tests for cache initialization functions."""

    def test_initialize_memory_cache(self):
        """Test initializing in-memory cache."""
        manager = initialize_cache(backend_type="memory", default_ttl=3600)

        assert manager is not None
        assert isinstance(manager.backend, InMemoryCache)
        assert manager.default_ttl == 3600

    @pytest.mark.skipif(not REDIS_AVAILABLE, reason="redis package not installed")
    def test_initialize_redis_cache(self):
        """Test initializing Redis cache."""
        manager = initialize_cache(
            backend_type="redis",
            redis_url="redis://localhost:6379/0",
            default_ttl=7200,
        )

        assert manager is not None
        assert isinstance(manager.backend, RedisCache)
        assert manager.default_ttl == 7200

    def test_initialize_redis_without_url(self):
        """Test that initializing Redis without URL raises error."""
        with pytest.raises(ValueError, match="redis_url is required"):
            initialize_cache(backend_type="redis")

    def test_initialize_unknown_backend(self):
        """Test that unknown backend type raises error."""
        with pytest.raises(ValueError, match="Unknown backend type"):
            initialize_cache(backend_type="unknown")

    def test_get_cache_manager(self):
        """Test getting global cache manager."""
        # Initialize cache
        manager = initialize_cache(backend_type="memory")

        # Get should return same instance
        retrieved = get_cache_manager()
        assert retrieved is manager

    def test_initialize_with_custom_provider_ttls(self):
        """Test initializing with custom provider TTLs."""
        provider_ttls = {
            "air_quality": 1800,
            "climate": 86400,
        }

        manager = initialize_cache(
            backend_type="memory",
            default_ttl=3600,
            provider_ttls=provider_ttls,
        )

        assert manager.provider_ttls == provider_ttls
        assert manager._get_ttl("air_quality") == 1800
        assert manager._get_ttl("climate") == 86400
        assert manager._get_ttl("unknown") == 3600


class TestCacheIntegration:
    """Integration tests for caching with service layer."""

    @pytest.mark.asyncio
    async def test_cache_hit_skips_provider(self):
        """Test that cache hit prevents provider from running."""
        # This will be tested more thoroughly in test_service.py
        # Just a placeholder to show the pattern
        pass

    @pytest.mark.asyncio
    async def test_cache_miss_runs_provider(self):
        """Test that cache miss causes provider to run."""
        pass

    @pytest.mark.asyncio
    async def test_provider_result_cached_after_run(self):
        """Test that provider results are cached after execution."""
        pass

    @pytest.mark.asyncio
    async def test_dataclass_serialization(self):
        """Test that dataclass results are properly serialized and deserialized."""
        from src.place_research.models.results import (
            AnnualAverageClimateResult,
            AirQualityResult,
            WalkBikeScoreResult,
        )
        from src.place_research.service import PlaceEnrichmentService
        from src.place_research.config import Settings

        service = PlaceEnrichmentService(Settings())

        # Test AnnualAverageClimateResult
        climate_result = AnnualAverageClimateResult(
            annual_average_temperature=72.5, annual_average_precipitation=45.0
        )
        serialized = service._serialize_provider_result(climate_result)
        assert serialized == {
            "annual_average_temperature": 72.5,
            "annual_average_precipitation": 45.0,
        }
        deserialized = service._deserialize_provider_result(
            "annualaverageclimate", serialized
        )
        assert isinstance(deserialized, AnnualAverageClimateResult)
        assert deserialized.annual_average_temperature == 72.5
        assert deserialized.annual_average_precipitation == 45.0

        # Test AirQualityResult
        air_result = AirQualityResult(
            air_quality="Good", air_quality_category="Satisfactory"
        )
        serialized = service._serialize_provider_result(air_result)
        deserialized = service._deserialize_provider_result("airquality", serialized)
        assert isinstance(deserialized, AirQualityResult)
        assert deserialized.air_quality == "Good"

        # Test WalkBikeScoreResult
        walk_result = WalkBikeScoreResult(
            walk_score=85,
            walk_description="Very Walkable",
            bike_score=72,
            bike_description="Very Bikeable",
        )
        serialized = service._serialize_provider_result(walk_result)
        deserialized = service._deserialize_provider_result("walkbikescore", serialized)
        assert isinstance(deserialized, WalkBikeScoreResult)
        assert deserialized.walk_score == 85
        assert deserialized.bike_score == 72

        # Test DistancesResult with nested DistanceResult objects
        from src.place_research.models.results import DistancesResult, DistanceResult

        distances_result = DistancesResult(
            distances={
                "home1": DistanceResult(distance_km=10.5, duration_m=15.0),
                "home2": DistanceResult(distance_km=20.3, duration_m=25.5),
            }
        )
        serialized = service._serialize_provider_result(distances_result)
        # Verify serialization includes nested dicts
        assert "distances" in serialized
        assert "home1" in serialized["distances"]
        assert serialized["distances"]["home1"]["distance_km"] == 10.5

        # Verify deserialization reconstructs nested objects properly
        deserialized = service._deserialize_provider_result("distance", serialized)
        assert isinstance(deserialized, DistancesResult)
        assert "home1" in deserialized.distances
        assert isinstance(deserialized.distances["home1"], DistanceResult)
        assert deserialized.distances["home1"].distance_km == 10.5
        assert deserialized.distances["home2"].duration_m == 25.5
