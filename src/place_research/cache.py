import json
import hashlib
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .config import Config
    from .models import Place


class CacheManager:
    """Manages caching of place data to avoid redundant API calls."""

    def __init__(self, config: "Config | None" = None):
        self.config = config
        self._cache_dir = self._get_cache_dir()
        self._ensure_cache_dir()

    def _get_cache_dir(self) -> Path:
        """Get the cache directory path."""
        # Use cache directory relative to project root
        project_root = Path(__file__).parent.parent.parent
        return project_root / "cache"

    def _ensure_cache_dir(self):
        """Ensure cache directory exists."""
        self._cache_dir.mkdir(exist_ok=True)

    def _get_cache_key(self, place: "Place", provider_name: str) -> str:
        """Generate a unique cache key for a place and provider combination."""
        # Create a unique key based on coordinates and provider
        key_data = (
            f"{place.coordinates[0]:.6f},{place.coordinates[1]:.6f},{provider_name}"
        )
        return hashlib.sha1(key_data.encode()).hexdigest()

    def _get_cache_file_path(self, cache_key: str) -> Path:
        """Get the path to a cache file."""
        return self._cache_dir / f"{cache_key}.json"

    def _is_cache_valid(self, cache_data: Dict[str, Any]) -> bool:
        """Check if cached data is still valid based on TTL."""
        if not self.config or not self.config.cache_enabled:
            return False

        if "timestamp" not in cache_data:
            return False

        cached_time = datetime.fromisoformat(cache_data["timestamp"])
        ttl_hours = self.config.get("cache_ttl_hours", 24)
        expiry_time = cached_time + timedelta(hours=ttl_hours)

        return datetime.now() < expiry_time

    def get_cached_data(
        self, place: "Place", provider_name: str
    ) -> Optional[Dict[str, Any]]:
        """Retrieve cached data for a place and provider if available and valid."""
        if not self.config or not self.config.cache_enabled:
            return None

        if not self.config.get(f"providers.{provider_name}.cache_enabled", True):
            return None

        cache_key = self._get_cache_key(place, provider_name)
        cache_file = self._get_cache_file_path(cache_key)

        if not cache_file.exists():
            return None

        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                cache_data = json.load(f)

            if self._is_cache_valid(cache_data):
                return cache_data.get("data")
            else:
                # Cache expired, remove the file
                cache_file.unlink(missing_ok=True)
                return None

        except (json.JSONDecodeError, KeyError, OSError):
            # Invalid cache file, remove it
            cache_file.unlink(missing_ok=True)
            return None

    def cache_data(self, place: "Place", provider_name: str, data: Dict[str, Any]):
        """Cache data for a place and provider."""
        if not self.config or not self.config.cache_enabled:
            return

        if not self.config.get(f"providers.{provider_name}.cache_enabled", True):
            return

        cache_key = self._get_cache_key(place, provider_name)
        cache_file = self._get_cache_file_path(cache_key)

        cache_data = {
            "timestamp": datetime.now().isoformat(),
            "coordinates": place.coordinates,
            "provider": provider_name,
            "data": data,
        }

        try:
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(cache_data, f, indent=2)
        except OSError:
            # Failed to write cache, continue without caching
            pass

    def clear_cache(self, provider_name: Optional[str] = None):
        """Clear cache files. If provider_name is specified, only clear cache for that provider."""
        if provider_name:
            # Clear cache for specific provider - would need to track this better
            # For now, just clear all cache
            pattern = "*.json"
        else:
            pattern = "*.json"

        for cache_file in self._cache_dir.glob(pattern):
            try:
                cache_file.unlink()
            except OSError:
                continue

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get statistics about cached data."""
        cache_files = list(self._cache_dir.glob("*.json"))

        stats = {
            "total_cached_items": len(cache_files),
            "cache_dir": str(self._cache_dir),
            "cache_enabled": self.config.cache_enabled if self.config else False,
        }

        if self.config:
            stats["cache_ttl_hours"] = self.config.get("cache_ttl_hours", 24)

        return stats
