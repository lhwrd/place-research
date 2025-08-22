import os
import click
import googlemaps
from dotenv import load_dotenv

from .models import Place
from .engine import ResearchEngine
from .config import Config
from .cache import CacheManager
from .providers import (
    FloodZoneProvider,
    WalkBikeScoreProvider,
    RailroadProvider,
    HighwayProvider,
    AirQualityProvider,
)

load_dotenv()


@click.group()
def cli():
    """Place research CLI tool."""


@cli.command()
@click.argument("address")
@click.option("--config-path", help="Path to configuration file")
@click.option("--no-cache", is_flag=True, help="Disable caching for this request")
def research(address, config_path, no_cache):
    """Research a place by address."""
    click.echo(f"Looking up: {address}")

    # Load configuration
    config = Config(config_path) if config_path else Config()

    # Temporarily disable cache if requested
    if no_cache:
        original_cache = config.get("cache_enabled")
        config.set("cache_enabled", False)

    # Initialize providers with configuration
    providers = []

    if config.is_provider_enabled("flood_zone"):
        providers.append(FloodZoneProvider(config=config))

    if config.is_provider_enabled("walkbike_score"):
        providers.append(WalkBikeScoreProvider(config=config))

    if config.is_provider_enabled("railroads"):
        providers.append(RailroadProvider(config=config))

    if config.is_provider_enabled("highways"):
        providers.append(HighwayProvider(config=config))

    if config.is_provider_enabled("air_quality"):
        providers.append(AirQualityProvider(config=config))

    engine = ResearchEngine(providers, config=config)

    gmaps_api_key = os.getenv("GOOGLE_MAPS_API_KEY")

    gmaps = googlemaps.Client(key=gmaps_api_key)

    geocode_result = gmaps.geocode(address)  # type: ignore
    if not geocode_result:
        click.echo("No results found")
        return

    coordinates = (
        geocode_result[0]["geometry"]["location"]["lat"],
        geocode_result[0]["geometry"]["location"]["lng"],
    )
    place = Place(address, coordinates)

    try:
        place.city = geocode_result[0]["address_components"][2]["long_name"]
    except (IndexError, KeyError):
        place.city = None
    try:
        place.county = geocode_result[0]["address_components"][3]["long_name"]
    except (IndexError, KeyError):
        place.county = None
    try:
        place.state = geocode_result[0]["address_components"][4]["long_name"]
    except (IndexError, KeyError):
        place.state = None

    engine.enrich_place(place)

    click.echo(f"Coordinates: {place.coordinates}")

    # Display results based on what's available
    if "flood_zone" in place.attributes:
        click.echo(f"Flood Zone Data: {place.attributes['flood_zone']}")
        click.echo(f"Flood Risk Data: {place.attributes['flood_risk']}")

    if "walk_score" in place.attributes:
        click.echo(f"Walk Score Data: {place.attributes['walk_score']}")

    if "bike_score" in place.attributes:
        click.echo(f"Bike Score Data: {place.attributes['bike_score']}")

    if "nearby_railroad_distance_m" in place.attributes:
        click.echo(f"Railroad Data Loaded: {place.attributes['railroad_data_loaded']}")
        click.echo(
            f"Nearby Railroad Distance: {place.attributes['nearby_railroad_distance_m']:,}"
        )

    if "highway_distance_m" in place.attributes:
        click.echo(
            f"Highway Distance: {place.attributes['highway_distance_m']:.1f} meters"
        )
        if place.attributes.get("nearest_highway_type"):
            click.echo(
                f"Nearest Highway Type: {place.attributes['nearest_highway_type']}"
            )
        if place.attributes.get("road_noise_level_db"):
            click.echo(
                f"Estimated Road Noise: {place.attributes['road_noise_level_db']} dB ({place.attributes['road_noise_category']})"
            )
        if place.attributes.get("highway_error"):
            click.echo(f"Highway Data Error: {place.attributes['highway_error']}")
            
    if "air_quality" in place.attributes:
        click.echo(f"Air Quality: {place.attributes['air_quality']}")
        click.echo(f"Air Quality Category: {place.attributes['air_quality_category']}")

    # Restore cache setting if it was disabled
    if no_cache:
        config.set("cache_enabled", original_cache)


@cli.command()
@click.option("--config-path", help="Path to configuration file")
def cache_stats(config_path):
    """Show cache statistics."""
    config = Config(config_path) if config_path else Config()
    cache_manager = CacheManager(config=config)

    stats = cache_manager.get_cache_stats()

    click.echo("Cache Statistics:")
    click.echo(f"  Cache Enabled: {stats['cache_enabled']}")
    click.echo(f"  Cache Directory: {stats['cache_dir']}")
    click.echo(f"  Total Cached Items: {stats['total_cached_items']}")
    if "cache_ttl_hours" in stats:
        click.echo(f"  Cache TTL: {stats['cache_ttl_hours']} hours")


@cli.command()
@click.option("--config-path", help="Path to configuration file")
@click.option("--provider", help="Clear cache for specific provider only")
@click.confirmation_option(prompt="Are you sure you want to clear the cache?")
def clear_cache(config_path, provider):
    """Clear the cache."""
    config = Config(config_path) if config_path else Config()
    cache_manager = CacheManager(config=config)

    cache_manager.clear_cache(provider)

    if provider:
        click.echo(f"Cache cleared for provider: {provider}")
    else:
        click.echo("All cache cleared")


# For backward compatibility with the original main function
def main():
    """Entry point for the CLI."""
    cli()


if __name__ == "__main__":
    cli()
