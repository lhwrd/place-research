import logging
import click
from dotenv import load_dotenv

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
    default="0.0.0.0",
    help="Host to bind to",
)
@click.option(
    "--port",
    type=int,
    default=8000,
    help="Port to bind to",
)
@click.option(
    "--reload",
    is_flag=True,
    default=False,
    help="Enable auto-reload for development",
)
@click.pass_context
def serve(ctx, host: str, port: int, reload: bool):
    """Start the Place Research API server."""
    from .api.server import main as serve_main

    # Call the server's main function with the provided parameters
    import sys

    sys.argv = ["serve"]
    if host != "0.0.0.0":
        sys.argv.extend(["--host", host])
    if port != 8000:
        sys.argv.extend(["--port", str(port)])
    if reload:
        sys.argv.append("--reload")
    log_level = ctx.obj.get("log_level", "INFO").lower()
    if log_level.lower() != "info":
        sys.argv.extend(["--log-level", log_level.lower()])

    serve_main.callback(host, port, reload, log_level)


if __name__ == "__main__":
    cli()
