"""Tests for the in-memory cache service."""

from unittest.mock import patch

import pytest

from app.services.cache_service import CacheService


@pytest.fixture
def cache():
    return CacheService()


@pytest.mark.asyncio
async def test_set_and_get(cache):
    await cache.set("key", {"a": 1}, ttl_days=1)
    assert await cache.get("key") == {"a": 1}


@pytest.mark.asyncio
async def test_shared_between_instances(cache):
    await cache.set("key", "value")
    assert await CacheService().get("key") == "value"


@pytest.mark.asyncio
async def test_missing_returns_default(cache):
    assert await cache.get("missing", default="fallback") == "fallback"


@pytest.mark.asyncio
async def test_expired_entry_is_dropped(cache):
    with patch("app.services.cache_service.time.monotonic", return_value=1000.0):
        await cache.set("key", "value", ttl_seconds=10)
    with patch("app.services.cache_service.time.monotonic", return_value=1011.0):
        assert await cache.get("key") is None
    assert await cache.delete("key") is False


@pytest.mark.asyncio
async def test_delete_and_clear(cache):
    await cache.set("a", 1)
    await cache.set("b", 2)

    assert await cache.delete("a") is True
    assert await cache.clear_all() == 1
    assert await cache.get("b") is None


@pytest.mark.asyncio
async def test_disabled_cache_stores_nothing(cache):
    cache._cache_enabled = False
    await cache.set("key", "value")
    assert await cache.get("key") is None
