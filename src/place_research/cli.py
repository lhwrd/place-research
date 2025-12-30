import logging
import click
from dotenv import load_dotenv

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
def serve(_, debug, host: str, port: int, reload: bool):
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
    if debug:
        sys.argv.extend(["--log-level", "debug"])

    serve_main.callback(host, port, reload, "info")


if __name__ == "__main__":
    cli()
