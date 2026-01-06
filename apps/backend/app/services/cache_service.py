"""Cache service for storing and retrieving enrichment data."""

import hashlib
import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import and_
from sqlalchemy.orm import Session

from app.models.cache_entry import CacheEntry

logger = logging.getLogger(__name__)


class CacheService:
    """
    Service for caching enrichment data to reduce external API calls.

    Supports:
    - TTL-based expiration
    - Key-based storage
    - Automatic cleanup of expired entries
    - JSON serialization
    - Cache statistics
    """

    def __init__(self, db: Session):
        self.db = db

    async def get(self, key: str, default: Optional[Any] = None) -> Optional[Any]:
        """
        Get a value from cache.

        Args:
            key: Cache key
            default:  Default value if key not found or expired

        Returns:
            Cached value or default
        """
        cache_entry = self._get_cache_entry(key)

        if not cache_entry:
            logger.debug(f"Cache miss: {key}")
            return default

        # Check if expired
        if cache_entry.expires_at and cache_entry.expires_at < datetime.now(timezone.utc):
            logger.debug(f"Cache expired: {key}")
            await self.delete(key)
            return default

        # Update access tracking
        cache_entry.access_count += 1
        cache_entry.last_accessed_at = datetime.now(timezone.utc)
        self.db.commit()

        logger.debug(f"Cache hit: {key}")

        # Deserialize and return value
        return self._deserialize(cache_entry.value)

    async def set(
        self,
        key: str,
        value: Any,
        ttl_seconds: Optional[int] = None,
        ttl_days: Optional[int] = None,
    ) -> None:
        """
        Set a value in cache.

        Args:
            key: Cache key
            value:  Value to cache (must be JSON serializable)
            ttl_seconds: Time to live in seconds
            ttl_days: Time to live in days
        """
        # Calculate expiration
        expires_at = None
        if ttl_seconds:
            expires_at = datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds)
        elif ttl_days:
            expires_at = datetime.now(timezone.utc) + timedelta(days=ttl_days)

        # Serialize value
        serialized_value = self._serialize(value)

        # Check if entry exists
        cache_entry = self._get_cache_entry(key)

        if cache_entry:
            # Update existing entry
            cache_entry.value = serialized_value
            cache_entry.expires_at = expires_at
            cache_entry.updated_at = datetime.now(timezone.utc)
        else:
            # Create new entry
            cache_entry = CacheEntry(key=key, value=serialized_value, expires_at=expires_at)
            self.db.add(cache_entry)

        self.db.commit()
        logger.debug(f"Cache set: {key} (expires: {expires_at})")

    async def delete(self, key: str) -> bool:
        """
        Delete a value from cache.

        Args:
            key: Cache key

        Returns:
            True if deleted, False if not found
        """
        cache_entry = self._get_cache_entry(key)

        if not cache_entry:
            return False

        self.db.delete(cache_entry)
        self.db.commit()

        logger.debug(f"Cache deleted: {key}")
        return True

    async def exists(self, key: str) -> bool:
        """
        Check if a key exists in cache and is not expired.

        Args:
            key: Cache key

        Returns:
            True if exists and not expired, False otherwise
        """
        cache_entry = self._get_cache_entry(key)

        if not cache_entry:
            return False

        # Check expiration
        if cache_entry.expires_at and cache_entry.expires_at < datetime.now(timezone.utc):
            await self.delete(key)
            return False

        return True

    async def get_many(self, keys: List[str]) -> Dict[str, Any]:
        """
        Get multiple values from cache.

        Args:
            keys: List of cache keys

        Returns:
            Dictionary mapping keys to values (only includes found keys)
        """
        results = {}

        for key in keys:
            value = await self.get(key)
            if value is not None:
                results[key] = value

        return results

    async def set_many(
        self,
        items: Dict[str, Any],
        ttl_seconds: Optional[int] = None,
        ttl_days: Optional[int] = None,
    ) -> None:
        """
        Set multiple values in cache.

        Args:
            items: Dictionary mapping keys to values
            ttl_seconds: Time to live in seconds
            ttl_days: Time to live in days
        """
        for key, value in items.items():
            await self.set(key, value, ttl_seconds=ttl_seconds, ttl_days=ttl_days)

    async def clear_expired(self) -> int:
        """
        Remove all expired cache entries.

        Returns:
            Number of entries deleted
        """
        count = (
            self.db.query(CacheEntry)
            .filter(
                and_(
                    CacheEntry.expires_at.isnot(None),
                    CacheEntry.expires_at < datetime.now(timezone.utc),
                )
            )
            .delete()
        )

        self.db.commit()

        if count > 0:
            logger.info(f"Cleared {count} expired cache entries")

        return count

    async def clear_all(self) -> int:
        """
        Clear all cache entries.

        Returns:
            Number of entries deleted
        """
        count = self.db.query(CacheEntry).delete()
        self.db.commit()

        logger.info(f"Cleared all cache entries ({count} total)")
        return count

    async def get_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.

        Returns:
            Dictionary with cache statistics
        """
        total_entries = self.db.query(CacheEntry).count()

        expired_entries = (
            self.db.query(CacheEntry)
            .filter(
                and_(
                    CacheEntry.expires_at.isnot(None),
                    CacheEntry.expires_at < datetime.now(timezone.utc),
                )
            )
            .count()
        )

        # Get total access count
        total_accesses = self.db.query(self.db.func.sum(CacheEntry.access_count)).scalar() or 0

        # Get average access count
        avg_accesses = self.db.query(self.db.func.avg(CacheEntry.access_count)).scalar() or 0

        # Get most accessed entries
        most_accessed = (
            self.db.query(CacheEntry).order_by(CacheEntry.access_count.desc()).limit(10).all()
        )

        return {
            "total_entries": total_entries,
            "active_entries": total_entries - expired_entries,
            "expired_entries": expired_entries,
            "total_accesses": int(total_accesses),
            "average_accesses": round(float(avg_accesses), 2),
            "most_accessed": [
                {
                    "key": entry.key,
                    "access_count": entry.access_count,
                    "created_at": entry.created_at.isoformat(),
                    "last_accessed_at": (
                        entry.last_accessed_at.isoformat() if entry.last_accessed_at else None
                    ),
                }
                for entry in most_accessed
            ],
        }

    def generate_key(self, *args, **kwargs) -> str:
        """
        Generate a cache key from arguments.

        Useful for creating consistent cache keys from function arguments.

        Args:
            *args:  Positional arguments
            **kwargs:  Keyword arguments

        Returns:
            MD5 hash of the arguments

        Example:
            key = cache. generate_key("property", lat=47.6062, lon=-122.3321)
        """
        # Create a string representation of all arguments
        key_parts = [str(arg) for arg in args]
        key_parts.extend(f"{k}={v}" for k, v in sorted(kwargs.items()))
        key_string = ": ".join(key_parts)

        # Generate MD5 hash
        return hashlib.md5(key_string.encode()).hexdigest()

    # Private helper methods

    def _get_cache_entry(self, key: str) -> Optional[CacheEntry]:
        """Get cache entry from database."""
        return self.db.query(CacheEntry).filter(CacheEntry.key == key).first()

    def _serialize(self, value: Any) -> str:
        """Serialize value to JSON string."""
        try:
            return json.dumps(value)
        except (TypeError, ValueError) as e:
            logger.error(f"Failed to serialize value:  {e}")
            raise ValueError(f"Value is not JSON serializable: {type(value)}")

    def _deserialize(self, value: str) -> Any:
        """Deserialize JSON string to value."""
        try:
            return json.loads(value)
        except (TypeError, ValueError) as e:
            logger.error(f"Failed to deserialize value: {e}")
            return None
