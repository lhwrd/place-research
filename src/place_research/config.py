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

    # API Keys for external services
    walkscore_api_key: Optional[str] = Field(None, alias="WALKSCORE_API_KEY")
    airnow_api_key: Optional[str] = Field(None, alias="AIRNOW_API_KEY")
    google_maps_api_key: Optional[str] = Field(None, alias="GOOGLE_MAPS_API_KEY")
    national_flood_data_api_key: Optional[str] = Field(
        None, alias="NATIONAL_FLOOD_DATA_API_KEY"
    )

    # File paths for data sources
    raillines_path: Optional[Path] = Field(None, alias="RAILLINES_PATH")
    annual_climate_path: Optional[Path] = Field(None, alias="ANNUAL_CLIMATE_PATH")
    distance_config_path: Optional[Path] = Field(None, alias="DISTANCE_CONFIG_PATH")

    # NocoDB configuration
    nocodb_url: Optional[str] = Field(None, alias="NOCODB_URL")
    nocodb_token: Optional[str] = Field(None, alias="NOCODB_TOKEN")
    nocodb_table_id: Optional[str] = Field(None, alias="NOCODB_TABLE_ID")

    # Application settings
    log_level: str = Field("INFO", alias="LOG_LEVEL")
    api_host: str = Field("0.0.0.0", alias="API_HOST")
    api_port: int = Field(8000, alias="API_PORT")

    def validate_provider_config(self, provider_name: str) -> list[str]:
        """Validate that required config for a provider exists.

        Args:
            provider_name: Name of the provider to validate

        Returns:
            List of missing configuration keys (empty if all present)
        """
        missing = []

        if provider_name == "WalkBikeScoreProvider":
            if not self.walkscore_api_key:
                missing.append("WALKSCORE_API_KEY")
        elif provider_name == "AirQualityProvider":
            if not self.airnow_api_key:
                missing.append("AIRNOW_API_KEY")
        elif provider_name == "FloodZoneProvider":
            if not self.national_flood_data_api_key:
                missing.append("NATIONAL_FLOOD_DATA_API_KEY")
        elif provider_name == "WalmartProvider":
            if not self.google_maps_api_key:
                missing.append("GOOGLE_MAPS_API_KEY")
        elif provider_name == "DistanceProvider":
            if not self.google_maps_api_key:
                missing.append("GOOGLE_MAPS_API_KEY")
            if not self.distance_config_path:
                missing.append("DISTANCE_CONFIG_PATH")
        elif provider_name == "RailroadProvider":
            if not self.raillines_path:
                missing.append("RAILLINES_PATH")
        elif provider_name == "AnnualAverageClimateProvider":
            if not self.annual_climate_path:
                missing.append("ANNUAL_CLIMATE_PATH")

        return missing


def get_settings() -> Settings:
    """Create and return a Settings instance.

    This is intended to be used as a FastAPI dependency.
    For testing, you can override this dependency or pass Settings directly.
    """
    return Settings()  # type: ignore[call-arg]
