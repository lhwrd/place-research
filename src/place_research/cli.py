import logging
import click
from dotenv import load_dotenv

from .engine import ResearchEngine
from .nocodb import NocoDB, TableRecordsQuery
from .models import Place
from .providers import (
    WalkBikeScoreProvider,
    WalmartProvider,
    AnnualAverageClimateProvider,
    FloodZoneProvider,
    HighwayProvider,
    RailroadProvider,
    AirQualityProvider,
    ProximityToFamilyProvider,
)

load_dotenv()


@click.group()
@click.option("--debug/--no-debug", default=False, help="Enable debug logging.")
@click.pass_context
def cli(ctx, debug):
    """Place research CLI tool."""
    # Set up logging level globally
    log_level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(level=log_level, format="%(levelname)s %(name)s: %(message)s")
    # Store debug flag in context for subcommands
    ctx.ensure_object(dict)
    ctx.obj["DEBUG"] = debug


@cli.command()
@click.option("--api-key", envvar="NOCODB_API_KEY", required=True)
@click.option("--base-url", envvar="NOCODB_BASE_URL", required=True)
@click.option("--table-id", envvar="NOCODB_TABLE_ID", required=True)
@click.option("--verify-ssl/--no-verify-ssl", default=True)
@click.pass_context
def update(ctx, api_key, base_url, table_id, verify_ssl):
    """Update the empty values in the NocoDB Table."""
    click.echo("Updating NocoDB Table...")

    if not verify_ssl:
        click.echo("Warning: SSL verification is disabled.")
        import warnings

        warnings.filterwarnings("ignore")

    debug = ctx.obj.get("DEBUG", False)
    if debug:
        logging.getLogger().setLevel(logging.DEBUG)
        logging.debug("Debug logging enabled for update command.")

    noco = NocoDB(base_url=base_url, api_key=api_key, verify_ssl=verify_ssl)

    table_records = noco.list_table_records(TableRecordsQuery(table_id=table_id))
    table_records = table_records.get("list", [])

    # Perform the update logic here
    for record in table_records:
        if not record.get("Address"):
            logging.error("Address is required for place ID %s", record.get("Id"))
            continue

        place = Place.model_validate(record)
        original_place = place.model_dump()

        # Reverse geocode first
        if (
            not place.geolocation
            or place.geolocation == "0;0"
            or not place.city
            or not place.county
            or not place.state
        ):
            place.reverse_geocode()
            logging.debug("Reverse geocoded place: %s", place.geolocation)

        providers = [
            RailroadProvider(),
            WalkBikeScoreProvider(),
            WalmartProvider(),
            HighwayProvider(),
            FloodZoneProvider(),
            AirQualityProvider(),
            AnnualAverageClimateProvider(),
            ProximityToFamilyProvider(),
        ]

        engine = ResearchEngine(providers=providers)

        engine.enrich_place(place)
        logging.debug("Enriched place: %s", place)

        # Update the record if it's been changed
        if place.model_dump() != original_place:
            updated_data = place.model_dump(
                by_alias=True, exclude={"created_at", "updated_at"}, exclude_none=True
            )
            logging.debug("Updating record: %s", updated_data)
            noco.update_table_record(table_id=table_id, data=updated_data)
            click.echo(f"Updated Place ID {place.id}")
        print("\n")


if __name__ == "__main__":
    cli()
