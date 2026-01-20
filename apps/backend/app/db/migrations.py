"""Database initialization and migration utilities.

This module handles database migrations using Alembic programmatically.
Instead of relying on shell scripts, migrations are run as part of the
application startup process.
"""

import logging
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import text

from app.core.config import get_settings
from app.db.database import engine

logger = logging.getLogger(__name__)


def get_alembic_config() -> Config:
    """Get Alembic configuration.

    Returns:
        Alembic Config object configured with the correct paths
    """
    # Get the backend directory (where alembic.ini is located)
    backend_dir = Path(__file__).parent.parent.parent
    alembic_ini_path = backend_dir / "alembic.ini"

    if not alembic_ini_path.exists():
        raise FileNotFoundError(f"alembic.ini not found at {alembic_ini_path}")

    alembic_cfg = Config(str(alembic_ini_path))

    # Set the sqlalchemy.url to match our current database URL
    settings = get_settings()
    alembic_cfg.set_main_option("sqlalchemy.url", settings.database_url)

    return alembic_cfg


def check_database_connection() -> bool:
    """Check if database is accessible.

    Returns:
        True if database connection is successful, False otherwise
    """
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        logger.info("Database connection successful")
        return True
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        return False


def run_migrations() -> None:
    """Run Alembic migrations to latest version.

    This is called during application startup to ensure the database
    schema is up to date.

    Raises:
        Exception: If migrations fail
    """
    try:
        logger.info("Running database migrations...")
        alembic_cfg = get_alembic_config()

        # Run migrations to head
        command.upgrade(alembic_cfg, "head")

        logger.info("Database migrations completed successfully")
    except Exception as e:
        logger.error(f"Failed to run migrations: {e}")
        raise


def check_migration_status() -> str:
    """Get current migration status.

    Returns:
        Current migration revision ID
    """
    try:
        alembic_cfg = get_alembic_config()

        # This is a bit hacky but works to get current revision
        with engine.connect() as conn:
            result = conn.execute(text("SELECT version_num FROM alembic_version LIMIT 1"))
            row = result.fetchone()
            if row:
                return row[0]
        return "No migrations applied"
    except Exception as e:
        logger.warning(f"Could not check migration status: {e}")
        return "Unknown"


def init_db() -> None:
    """Initialize the database.

    This function:
    1. Checks database connectivity
    2. Runs Alembic migrations
    3. Logs the current migration status

    This should be called during application startup.
    """
    logger.info("Initializing database...")

    # Check database connection
    if not check_database_connection():
        raise RuntimeError("Cannot connect to database")

    # Run migrations
    run_migrations()

    # Log current status
    current_revision = check_migration_status()
    logger.info(f"Database initialized. Current migration: {current_revision}")
