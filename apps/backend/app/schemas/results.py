"""Result objects for all providers.

Instead of providers directly mutating Place objects, they return these typed results.
This allows for:
- Better testability (can test provider logic independently)
- Type safety (clear contracts for what each provider returns)
- Composability (results can be used in different contexts)
- Error handling (can return None or error states)
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class WalkBikeScoreResult:
    """Result from WalkBikeScoreProvider."""

    walk_score: Optional[int] = None
    walk_description: Optional[str] = None
    bike_score: Optional[int] = None
    bike_description: Optional[str] = None


@dataclass
class AirQualityResult:
    """Result from AirQualityProvider."""

    air_quality: Optional[str] = None
    air_quality_category: Optional[str] = None


@dataclass
class FloodZoneResult:
    """Result from FloodZoneProvider."""

    flood_zone: Optional[str] = None
    flood_risk: Optional[str] = None


@dataclass
class HighwayResult:
    """Result from HighwayProvider."""

    highway_distance_m: Optional[int] = None
    nearest_highway_type: Optional[str] = None
    road_noise_level_db: Optional[float] = None
    road_noise_category: Optional[str] = None


@dataclass
class RailroadResult:
    """Result from RailroadProvider."""

    distance_to_railroad_m: Optional[int] = None


@dataclass
class WalmartResult:
    """Result from WalmartProvider."""

    distance_km: Optional[float] = None
    duration_m: Optional[float] = None
    distance_category: Optional[str] = None
    duration_category: Optional[str] = None
    rating: Optional[float] = None


@dataclass
class DistanceResult:
    distance_km: Optional[float] = None
    duration_m: Optional[float] = None


@dataclass
class DistancesResult:
    """Result from DistanceProvider."""

    distances: dict[str, DistanceResult] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict) -> "DistancesResult":
        """Create DistancesResult from dict, reconstructing nested DistanceResult objects."""
        if "distances" in data and isinstance(data["distances"], dict):
            distances = {}
            for key, value in data["distances"].items():
                if isinstance(value, dict):
                    # Reconstruct DistanceResult from dict
                    distances[key] = DistanceResult(**value)
                else:
                    # Already a DistanceResult object
                    distances[key] = value
            return cls(distances=distances)
        else:
            return cls(**data)


@dataclass
class AnnualAverageClimateResult:
    """Result from AnnualAverageClimateProvider."""

    annual_average_temperature: Optional[float] = None
    annual_average_precipitation: Optional[float] = None


@dataclass
class ProviderError:
    """Represents an error from a provider.

    Providers can return this when they encounter errors instead of raising exceptions.
    This allows the service layer to collect partial results even when some providers fail.
    """

    provider_name: str
    error_message: str
    error_type: str  # e.g., "API_ERROR", "CONFIG_ERROR", "DATA_ERROR"


@dataclass
class EnrichmentResult:
    """Combined result from all providers for a single place.

    This is what the service layer returns after running all providers.
    Contains both successful results and any errors encountered.
    """

    place_id: str
    walk_bike_score: Optional[WalkBikeScoreResult] = None
    air_quality: Optional[AirQualityResult] = None
    flood_zone: Optional[FloodZoneResult] = None
    highway: Optional[HighwayResult] = None
    railroad: Optional[RailroadResult] = None
    walmart: Optional[WalmartResult] = None
    distances: Optional[DistancesResult] = None
    climate: Optional[AnnualAverageClimateResult] = None
    errors: list[ProviderError] = field(default_factory=list)

    def __post_init__(self):
        """Initialize errors list if not provided."""
        if self.errors is None:
            self.errors = []

    def has_errors(self) -> bool:
        """Check if any providers failed."""
        return len(self.errors) > 0

    def is_complete(self) -> bool:
        """Check if all providers returned data (no errors and all fields populated)."""
        return not self.has_errors() and all(
            [
                self.walk_bike_score,
                self.air_quality,
                self.flood_zone,
                self.highway,
                self.railroad,
                self.walmart,
                self.distances,
                self.climate,
            ]
        )

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        result = {
            "place_id": self.place_id,
            "errors": [
                {
                    "provider": e.provider_name,
                    "message": e.error_message,
                    "type": e.error_type,
                }
                for e in self.errors
            ],
        }

        # Add non-None results
        if self.walk_bike_score:
            result["walk_bike_score"] = {
                "walk_score": self.walk_bike_score.walk_score,
                "walk_description": self.walk_bike_score.walk_description,
                "bike_score": self.walk_bike_score.bike_score,
                "bike_description": self.walk_bike_score.bike_description,
            }

        if self.air_quality:
            result["air_quality"] = {
                "aqi": self.air_quality.air_quality,
                "category": self.air_quality.air_quality_category,
            }

        if self.flood_zone:
            result["flood_zone"] = {
                "flood_zone": self.flood_zone.flood_zone,
                "flood_risk": self.flood_zone.flood_risk,
            }

        if self.highway:
            result["highway"] = {
                "distance_m": self.highway.highway_distance_m,
                "nearest_type": self.highway.nearest_highway_type,
                "road_noise_db": self.highway.road_noise_level_db,
                "road_noise_category": self.highway.road_noise_category,
            }

        if self.railroad:
            result["railroad"] = {
                "distance_m": self.railroad.distance_to_railroad_m,
            }

        if self.walmart:
            result["walmart"] = {
                "distance_km": self.walmart.distance_km,
                "duration_m": self.walmart.duration_m,
                "distance_category": self.walmart.distance_category,
                "duration_category": self.walmart.duration_category,
                "rating": self.walmart.rating,
            }

        if self.distances:
            result["distances"] = {
                name: {
                    "distance_km": dist.distance_km,
                    "duration_m": dist.duration_m,
                }
                for name, dist in self.distances.distances.items()
            }

        if self.climate:
            result["climate"] = {
                "avg_temperature": self.climate.annual_average_temperature,
                "avg_precipitation": self.climate.annual_average_precipitation,
            }

        return result
