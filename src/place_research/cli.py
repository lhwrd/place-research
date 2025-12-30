import logging

import click
from dotenv import load_dotenv
import uvicorn

from .config import get_settings

load_dotenv()


@click.group()
@click.pass_context
def cli(ctx):
    """Place research CLI tool."""
    # Set up logging level globally
    settings = get_settings()
    debug = "debug" in str(settings.log_level).lower()
    log_level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(level=log_level, format="%(levelname)s %(name)s: %(message)s")
    # Store debug flag in context for subcommands
    ctx.ensure_object(dict)
    for key, value in settings.model_dump().items():
        ctx.obj[key] = value


@cli.command()
@click.option(
    "--host",
    default=None,
    help="Host to bind to (default from settings or 0.0.0.0)",
)
@click.option(
    "--port",
    type=int,
    default=None,
    help="Port to bind to (default from settings or 8000)",
)
@click.option(
    "--reload",
    is_flag=True,
    default=False,
    help="Enable auto-reload for development",
)
@click.option(
    "--log-level",
    default="info",
    type=click.Choice(["debug", "info", "warning", "error", "critical"]),
    help="Logging level",
)
def main(host: str, port: int, reload: bool, log_level: str):
    """Start the Place Research API server."""
    settings = get_settings()

    # Use settings or defaults
    host = host or settings.api_host
    port = port or settings.api_port

    # Configure logging
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    logger = logging.getLogger(__name__)
    logger.info("Starting Place Research API on %s:%s", host, port)
    logger.info("Auto-reload: %s", reload)
    logger.info("Log level: %s", log_level)

    # Run the server
    uvicorn.run(
        "place_research.api:app",
        host=host,
        port=port,
        reload=reload,
        log_level=log_level,
    )


if __name__ == "__main__":
    cli()  # pylint: disable=no-value-for-parameter
