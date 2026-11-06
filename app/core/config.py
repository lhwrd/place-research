"""Configuration management for place-research.

This module provides centralized, type-safe configuration using Pydantic Settings.
All provider API keys and file paths are defined here instead of scattered os.getenv() calls.
"""

from pathlib import Path
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables.

    All settings have optional defaults to allow partial configuration.
    Providers should handle missing config gracefully.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = Field("place-research", alias="APP_NAME")

    # API Keys for external services
    walkscore_api_key: Optional[str] = Field(None, alias="WALKSCORE_API_KEY")
    google_maps_api_key: Optional[str] = Field(None, alias="GOOGLE_MAPS_API_KEY")
    national_flood_data_api_key: Optional[str] = Field(None, alias="NATIONAL_FLOOD_DATA_API_KEY")

    # File paths for data sources
    raillines_path: Optional[Path] = Field(None, alias="RAILLINES_PATH")
    annual_climate_path: Optional[Path] = Field(None, alias="ANNUAL_CLIMATE_PATH")

    # Baserow configuration (source of truth for properties, locations and settings)
    baserow_url: Optional[str] = Field(None, alias="BASEROW_URL")
    baserow_api_token: Optional[str] = Field(None, alias="BASEROW_API_TOKEN")
    baserow_database_id: Optional[int] = Field(None, alias="BASEROW_DATABASE_ID")
    baserow_properties_table_id: Optional[int] = Field(None, alias="BASEROW_PROPERTIES_TABLE_ID")
    baserow_locations_table_id: Optional[int] = Field(None, alias="BASEROW_LOCATIONS_TABLE_ID")
    baserow_settings_table_id: Optional[int] = Field(None, alias="BASEROW_SETTINGS_TABLE_ID")
    baserow_webhook_secret: Optional[str] = Field(None, alias="BASEROW_WEBHOOK_SECRET")
    baserow_sweep_interval_seconds: int = Field(
        900,
        alias="BASEROW_SWEEP_INTERVAL_SECONDS",
        description="How often to enrich rows a webhook may have missed (default: 900 = 15 min)",
    )

    # Static bearer token for the iOS Shortcut ingest endpoints
    ingest_api_token: Optional[str] = Field(None, alias="INGEST_API_TOKEN")

    @property
    def baserow_configured(self) -> bool:
        """Whether enough Baserow config exists to sync properties."""
        return bool(
            self.baserow_url and self.baserow_api_token and self.baserow_properties_table_id
        )

    # Application settings
    testing: bool = Field(
        False,
        alias="TESTING",
        description="Whether app is running in test mode (default: False)",
    )
    log_level: str = Field("INFO", alias="LOG_LEVEL")

    # Logging & Observability settings
    log_format: str = Field(
        "json",
        alias="LOG_FORMAT",
        description="Log format: 'json' for production, 'text' or 'color' for dev (default: json)",
    )
    log_requests: bool = Field(
        True,
        alias="LOG_REQUESTS",
        description="Log HTTP requests (default: True)",
    )
    log_responses: bool = Field(
        True,
        alias="LOG_RESPONSES",
        description="Log HTTP responses (default: True)",
    )

    # In-process cache for provider and geocoding results

    cache_enabled: bool = Field(
        True,
        alias="CACHE_ENABLED",
        description="Enable caching for provider results (default: True)",
    )


def get_settings() -> Settings:
    """Create and return a Settings instance.

    This is intended to be used as a FastAPI dependency.
    For testing, you can override this dependency or pass Settings directly.
    """
    return Settings()  # type: ignore[call-arg]


settings = get_settings()
