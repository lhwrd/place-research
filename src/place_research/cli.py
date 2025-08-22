import os

import click
import googlemaps
from dotenv import load_dotenv

from .cache import CacheManager
from .config import Config
from .engine import ResearchEngine
from .models import Place, City, County
from .providers import (
    AirQualityProvider,
    CensusProvider,
    FloodZoneProvider,
    HighwayProvider,
    RailroadProvider,
    WalkBikeScoreProvider,
    WalmartProvider,
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

    if config.is_provider_enabled("census"):
        providers.append(CensusProvider(config=config))

    if config.is_provider_enabled("walmart"):
        providers.append(WalmartProvider(config=config))

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

    # Extract city, county, and state information from geocoding result
    city_name = None
    county_name = None
    state_name = None

    try:
        city_name = geocode_result[0]["address_components"][2]["long_name"]
    except (IndexError, KeyError):
        pass

    try:
        county_name = geocode_result[0]["address_components"][3]["long_name"]
    except (IndexError, KeyError):
        pass

    try:
        state_name = geocode_result[0]["address_components"][4]["long_name"]
    except (IndexError, KeyError):
        pass

    # Create City and County objects if we have the necessary information
    if city_name and state_name:
        place.city = City(city_name, state_name)

    if county_name and state_name:
        place.county = County(county_name, state_name)

    if state_name:
        place.state = state_name

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

    # Display census data
    if "census_population" in place.attributes:
        click.echo("\nCensus Data:")
        if place.attributes.get("census_population"):
            click.echo(f"  Population: {place.attributes['census_population']:,}")
        if place.attributes.get("census_median_income"):
            click.echo(
                f"  Median Household Income: ${place.attributes['census_median_income']:,}"
            )
        if place.attributes.get("census_median_home_value"):
            click.echo(
                f"  Median Home Value: ${place.attributes['census_median_home_value']:,}"
            )
        if place.attributes.get("census_housing_units"):
            click.echo(f"  Housing Units: {place.attributes['census_housing_units']:,}")
        if place.attributes.get("census_homeownership_rate"):
            click.echo(
                f"  Homeownership Rate: {place.attributes['census_homeownership_rate']}%"
            )
        if place.attributes.get("census_higher_education_rate"):
            click.echo(
                f"  Higher Education Rate: {place.attributes['census_higher_education_rate']}%"
            )
        if place.attributes.get("census_public_transit_commuters"):
            click.echo(
                f"  Public Transit Commuters: {place.attributes['census_public_transit_commuters']:,}"
            )
        if place.attributes.get("census_work_from_home"):
            click.echo(
                f"  Work From Home: {place.attributes['census_work_from_home']:,}"
            )

    if place.attributes.get("census_error"):
        click.echo(f"Census Data Error: {place.attributes['census_error']}")

    # Display Walmart data
    if "walmart_supercenter_driving_distance_m" in place.attributes:
        if place.attributes["walmart_supercenter_driving_distance_m"] is not None:
            driving_distance_m = place.attributes[
                "walmart_supercenter_driving_distance_m"
            ]
            driving_distance_km = place.attributes[
                "walmart_supercenter_driving_distance_km"
            ]
            driving_time_min = place.attributes[
                "walmart_supercenter_driving_time_minutes"
            ]
            straight_distance_m = place.attributes.get(
                "walmart_supercenter_straight_line_distance_m"
            )

            click.echo("\nWalmart Supercenter Data:")
            click.echo(
                f"  Driving Distance: {driving_distance_m:,} meters ({driving_distance_km} km)"
            )
            click.echo(f"  Driving Time: {driving_time_min} minutes")

            if straight_distance_m:
                straight_distance_km = straight_distance_m / 1000
                click.echo(
                    f"  Straight-line Distance: {straight_distance_m:.1f} meters ({straight_distance_km:.2f} km)"
                )

            click.echo(
                f"  Category: {place.attributes.get('walmart_supercenter_distance_category', 'Unknown')}"
            )

            if place.attributes.get("nearest_walmart_supercenter_name"):
                click.echo(
                    f"  Name: {place.attributes['nearest_walmart_supercenter_name']}"
                )

            if place.attributes.get("nearest_walmart_supercenter_address"):
                click.echo(
                    f"  Address: {place.attributes['nearest_walmart_supercenter_address']}"
                )

            if place.attributes.get("nearest_walmart_supercenter_rating"):
                click.echo(
                    f"  Rating: {place.attributes['nearest_walmart_supercenter_rating']}/5"
                )

            open_status = place.attributes.get("nearest_walmart_supercenter_open_now")
            if open_status is not None:
                status_text = "Open" if open_status else "Closed"
                click.echo(f"  Currently: {status_text}")
        else:
            click.echo(
                "\nWalmart Supercenter Data: No Walmart Supercenter found within 50km"
            )

    if place.attributes.get("walmart_error"):
        click.echo(f"Walmart Data Error: {place.attributes['walmart_error']}")

    # Display city-specific census data
    if place.city and hasattr(place.city, "attributes") and place.city.attributes:
        city_census = {
            k: v for k, v in place.city.attributes.items() if k.startswith("census_")
        }
        if city_census:
            click.echo(f"\nCity Census Data ({place.city.name}, {place.city.state}):")
            for key, value in city_census.items():
                if key != "census_error" and value is not None:
                    display_name = key.replace("census_", "").replace("_", " ").title()
                    if isinstance(value, int) and value > 1000:
                        click.echo(f"  {display_name}: {value:,}")
                    else:
                        click.echo(f"  {display_name}: {value}")

    # Display county-specific census data
    if place.county and hasattr(place.county, "attributes") and place.county.attributes:
        county_census = {
            k: v for k, v in place.county.attributes.items() if k.startswith("census_")
        }
        if county_census:
            click.echo(
                f"\nCounty Census Data ({place.county.name}, {place.county.state}):"
            )
            for key, value in county_census.items():
                if key != "census_error" and value is not None:
                    display_name = key.replace("census_", "").replace("_", " ").title()
                    if isinstance(value, int) and value > 1000:
                        click.echo(f"  {display_name}: {value:,}")
                    else:
                        click.echo(f"  {display_name}: {value}")

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
