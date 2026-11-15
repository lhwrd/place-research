"""Configuration management for place-research.

This module provides centralized, type-safe configuration using Pydantic Settings.
All provider API keys and file paths are defined here instead of scattered os.getenv() calls.
"""

from pathlib import Path
from typing import Optional

from pydantic import Field, field_validator
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
    # Sent to the browser for the Street View embed. Use a key restricted to the Maps Embed
    # API (and your UI's address); falls back to GOOGLE_MAPS_API_KEY if unset.
    google_maps_embed_key: Optional[str] = Field(None, alias="GOOGLE_MAPS_EMBED_KEY")
    census_api_key: Optional[str] = Field(None, alias="CENSUS_API_KEY")
    census_acs_year: int = Field(
        2024,
        alias="CENSUS_ACS_YEAR",
        description="ACS 5-year release to use (2024 = 2020-2024 estimates, out Dec 2025)",
    )

    # File paths for data sources
    raillines_path: Optional[Path] = Field(None, alias="RAILLINES_PATH")
    # Census TIGER primary/secondary roads, built by scripts/build_highways.py
    highways_path: Optional[Path] = Field(None, alias="HIGHWAYS_PATH")

    # SQLite database holding properties, photos, locations and settings
    database_path: Path = Field(
        Path("db/place-research.db"),
        alias="DATABASE_PATH",
        description="SQLite file; its directory is created if missing",
    )

    @field_validator("raillines_path", "highways_path", mode="before")
    @classmethod
    def _blank_path_is_unset(cls, value):
        """`RAILLINES_PATH=` in .env means "not set", not the current directory."""
        return None if isinstance(value, str) and not value.strip() else value

    # Static bearer token for the iOS Shortcut ingest endpoints
    ingest_api_token: Optional[str] = Field(None, alias="INGEST_API_TOKEN")

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
