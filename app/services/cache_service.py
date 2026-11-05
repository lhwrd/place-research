"""In-process TTL cache for enrichment and geocoding results.

The backend keeps no database: results of record live in Baserow. This cache only saves
repeat external API calls (e.g. geocoding the same drive-time locations on every
enrichment) for the lifetime of the process.
"""

import logging
import time
from typing import Any, Dict, Optional, Tuple

from app.core.config import get_settings

logger = logging.getLogger(__name__)

SECONDS_PER_DAY = 86400

# Shared by every CacheService instance: key -> (expires_at monotonic seconds or None, value)
_store: Dict[str, Tuple[Optional[float], Any]] = {}


class CacheService:
    """Async-compatible TTL cache backed by a process-wide dict. Respects cache_enabled."""

    def __init__(self):
        self._cache_enabled = get_settings().cache_enabled

    async def get(self, key: str, default: Optional[Any] = None) -> Optional[Any]:
        """Return the cached value, or default if missing, expired, or caching is disabled."""
        if not self._cache_enabled:
            return default

        entry = _store.get(key)
        if entry is None:
            logger.debug("Cache miss: %s", key)
            return default

        expires_at, value = entry
        if expires_at is not None and expires_at < time.monotonic():
            logger.debug("Cache expired: %s", key)
            _store.pop(key, None)
            return default

        logger.debug("Cache hit: %s", key)
        return value

    async def set(
        self,
        key: str,
        value: Any,
        ttl_seconds: Optional[int] = None,
        ttl_days: Optional[int] = None,
    ) -> None:
        """Store a value. With no TTL it lives until the process exits."""
        if not self._cache_enabled:
            return

        ttl = ttl_seconds if ttl_seconds is not None else (ttl_days or 0) * SECONDS_PER_DAY
        expires_at = time.monotonic() + ttl if ttl else None
        _store[key] = (expires_at, value)

    async def delete(self, key: str) -> bool:
        """Remove a key. Returns True if it existed."""
        return _store.pop(key, None) is not None

    async def clear_all(self) -> int:
        """Remove every entry. Returns how many were removed."""
        count = len(_store)
        _store.clear()
        return count
