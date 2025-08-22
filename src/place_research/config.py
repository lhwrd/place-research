import json
from pathlib import Path
from typing import Any, Dict


class Config:
    """Configuration manager for place research application."""

    def __init__(self, config_path: str | Path | None = None):
        self._config_data: Dict[str, Any] = {}
        self._load_config(config_path)

    def _load_config(self, config_path: str | Path | None = None):
        """Load configuration from file."""
        if config_path is None:
            # Look for config.json in the project root
            project_root = Path(__file__).parent.parent.parent
            config_path = project_root / "config.json"

        config_path = Path(config_path)

        if config_path.exists():
            with open(config_path, "r", encoding="utf-8") as f:
                self._config_data = json.load(f)
        else:
            # Create default config if it doesn't exist
            self._config_data = self._get_default_config()
            self._save_config(config_path)

    def _get_default_config(self) -> Dict[str, Any]:
        """Get default configuration values."""
        return {
            "raillines_path": "",
            "cache_enabled": True,
            "cache_ttl_hours": 24,
            "timeout_seconds": 30,
            "providers": {
                "flood_zone": {"enabled": True, "cache_enabled": True},
                "walkbike_score": {"enabled": True, "cache_enabled": True},
                "railroads": {"enabled": True, "cache_enabled": True},
            },
        }

    def _save_config(self, config_path: Path):
        """Save configuration to file."""
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(self._config_data, f, indent=2)

    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value by key (supports dot notation)."""
        keys = key.split(".")
        value = self._config_data

        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default

        return value

    def set(self, key: str, value: Any):
        """Set configuration value by key (supports dot notation)."""
        keys = key.split(".")
        config = self._config_data

        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]

        config[keys[-1]] = value

    def get_provider_config(self, provider_name: str) -> Dict[str, Any]:
        """Get configuration for a specific provider."""
        return self.get(f"providers.{provider_name}", {})

    def is_provider_enabled(self, provider_name: str) -> bool:
        """Check if a provider is enabled."""
        return self.get(f"providers.{provider_name}.enabled", True)

    @property
    def cache_enabled(self) -> bool:
        """Check if caching is enabled globally."""
        return self.get("cache_enabled", True)

    @property
    def timeout_seconds(self) -> int:
        """Get request timeout in seconds."""
        return self.get("timeout_seconds", 30)
