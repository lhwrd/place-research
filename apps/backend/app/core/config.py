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
    base_url: str = Field("http://localhost:8000", alias="BASE_URL")

    # API Keys for external services
    walkscore_api_key: Optional[str] = Field(None, alias="WALKSCORE_API_KEY")
    airnow_api_key: Optional[str] = Field(None, alias="AIRNOW_API_KEY")
    google_maps_api_key: Optional[str] = Field(None, alias="GOOGLE_MAPS_API_KEY")
    national_flood_data_api_key: Optional[str] = Field(None, alias="NATIONAL_FLOOD_DATA_API_KEY")

    # File paths for data sources
    raillines_path: Optional[Path] = Field(None, alias="RAILLINES_PATH")
    annual_climate_path: Optional[Path] = Field(None, alias="ANNUAL_CLIMATE_PATH")
    distance_config_path: Optional[Path] = Field(None, alias="DISTANCE_CONFIG_PATH")

    # Authentication settings
    require_authentication: bool = Field(
        False,
        alias="REQUIRE_AUTHENTICATION",
        description="Whether API authentication is required (default: False for dev)",
    )
    allow_api_key_creation: bool = Field(
        True,
        alias="ALLOW_API_KEY_CREATION",
        description="Whether new API keys can be created via API (default: True)",
    )

    # Database settings
    database_url: str = Field(
        "sqlite:///./place_research.db",
        alias="DATABASE_URL",
        description="Database connection URL (default: sqlite:///./place_research.db)",
    )

    # JWT settings
    jwt_secret_key: str = Field(
        ...,
        alias="JWT_SECRET_KEY",
        description="Secret key for JWT token signing (REQUIRED - generate with: openssl rand -hex 32)",
    )
    jwt_algorithm: str = Field(
        "HS256",
        alias="JWT_ALGORITHM",
        description="Algorithm for JWT token signing (default: HS256)",
    )
    jwt_access_token_expire_minutes: int = Field(
        30,
        alias="JWT_ACCESS_TOKEN_EXPIRE_MINUTES",
        description="Access token expiration in minutes (default: 30)",
    )
    jwt_refresh_token_expire_days: int = Field(
        7,
        alias="JWT_REFRESH_TOKEN_EXPIRE_DAYS",
        description="Refresh token expiration in days (default: 7)",
    )

    # NocoDB configuration
    nocodb_url: Optional[str] = Field(None, alias="NOCODB_URL")
    nocodb_token: Optional[str] = Field(None, alias="NOCODB_TOKEN")
    nocodb_table_id: Optional[str] = Field(None, alias="NOCODB_TABLE_ID")

    # Application settings
    log_level: str = Field("INFO", alias="LOG_LEVEL")
    api_host: str = Field("0.0.0.0", alias="API_HOST")
    api_port: int = Field(8000, alias="API_PORT")

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
    log_provider_metrics: bool = Field(
        True,
        alias="LOG_PROVIDER_METRICS",
        description="Log provider execution metrics (default: True)",
    )
    log_cache_operations: bool = Field(
        False,
        alias="LOG_CACHE_OPERATIONS",
        description="Log cache operations - useful for debugging (default: False)",
    )

    # Cache settings
    cache_enabled: bool = Field(
        True,
        alias="CACHE_ENABLED",
        description="Enable caching for provider results (default: True)",
    )
    cache_backend: str = Field(
        "memory",
        alias="CACHE_BACKEND",
        description="Cache backend: 'memory' or 'redis' (default: memory)",
    )
    cache_default_ttl: int = Field(
        3600,
        alias="CACHE_DEFAULT_TTL",
        description="Default cache TTL in seconds (default: 3600 = 1 hour)",
    )
    redis_url: Optional[str] = Field(
        None,
        alias="REDIS_URL",
        description="Redis connection URL (e.g., redis://localhost:6379/0)",
    )

    # Per-provider cache TTLs (in seconds)
    # Air quality changes frequently
    cache_ttl_air_quality: int = Field(
        1800,
        alias="CACHE_TTL_AIR_QUALITY",
        description="Cache TTL for air quality data (default: 1800 = 30 min)",
    )
    # Climate data is annual averages, rarely changes
    cache_ttl_climate: int = Field(
        86400,
        alias="CACHE_TTL_CLIMATE",
        description="Cache TTL for climate data (default: 86400 = 24 hours)",
    )
    # Flood zones rarely change
    cache_ttl_flood: int = Field(
        86400,
        alias="CACHE_TTL_FLOOD",
        description="Cache TTL for flood zone data (default: 86400 = 24 hours)",
    )
    # Infrastructure (highways, railroads) rarely changes
    cache_ttl_infrastructure: int = Field(
        86400,
        alias="CACHE_TTL_INFRASTRUCTURE",
        description="Cache TTL for infrastructure data (default: 86400 = 24 hours)",
    )
    # Walk/bike scores change with development but not frequently
    cache_ttl_walkability: int = Field(
        7200,
        alias="CACHE_TTL_WALKABILITY",
        description="Cache TTL for walk/bike scores (default: 7200 = 2 hours)",
    )

    property_data_provider: str = Field(
        "attom", alias="PROPERTY_DATA_PROVIDER"
    )  # "attom", "zillow", "realty_mole", "mock"
    property_data_api_key: Optional[str] = Field(None, alias="PROPERTY_DATA_API_KEY")
    property_data_api_base_url: str = Field(
        "https://api.gateway.attomdata.com/propertyapi/v1.0.0",
        alias="PROPERTY_DATA_API_BASE_URL",
    )

    # Provider-specific settings
    attom_api_key: Optional[str] = Field(None, alias="ATTOM_API_KEY")
    zillow_rapid_api_key: Optional[str] = Field(None, alias="ZILLOW_RAPID_API_KEY")
    realty_mole_api_key: Optional[str] = Field(None, alias="REALTY_MOLE_API_KEY")

    # Use mock data in development
    use_mock_property_data: bool = Field(False, alias="USE_MOCK_PROPERTY_DATA")

    # Email settings
    email_smtp_server: str = Field("smtp.example.com", alias="EMAIL_SMTP_SERVER")
    email_smtp_port: int = Field(587, alias="EMAIL_SMTP_PORT")
    email_username: str = Field(..., alias="EMAIL_USERNAME")
    email_password: str = Field(..., alias="EMAIL_PASSWORD")
    email_from_address: str = Field(..., alias="EMAIL_FROM_ADDRESS")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        # Set provider-specific API key (only override if provider-specific key exists)
        if self.property_data_provider == "attom" and self.attom_api_key:
            self.property_data_api_key = self.attom_api_key
        elif self.property_data_provider == "zillow" and self.zillow_rapid_api_key:
            self.property_data_api_key = self.zillow_rapid_api_key
            self.property_data_api_base_url = "https://zillow-com1.p.rapidapi.com"
        elif self.property_data_provider == "realty_mole" and self.realty_mole_api_key:
            self.property_data_api_key = self.realty_mole_api_key
            self.property_data_api_base_url = "https://realty-mole-property-api.p.rapidapi.com"

    def get_provider_ttls(self) -> dict[str, int]:
        """Get mapping of provider names to cache TTLs."""
        return {
            "air_quality": self.cache_ttl_air_quality,
            "annual_average_climate": self.cache_ttl_climate,
            "flood_zone": self.cache_ttl_flood,
            "highways": self.cache_ttl_infrastructure,
            "railroads": self.cache_ttl_infrastructure,
            "proximity_to_family": self.cache_ttl_infrastructure,
            "walkbike_score": self.cache_ttl_walkability,
            "walmart": self.cache_ttl_infrastructure,
        }

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


settings = get_settings()
