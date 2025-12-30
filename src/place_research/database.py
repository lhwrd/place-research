"""Database connection and session management."""

import logging
from functools import lru_cache
from typing import Generator

from sqlalchemy.engine import Engine
from sqlmodel import Session, SQLModel, create_engine

from .config import get_settings

logger = logging.getLogger(__name__)


@lru_cache
def get_engine() -> Engine:
    """Get or create the database engine.

    Uses lru_cache to ensure singleton behavior without global variables.
    The engine is created once and cached for subsequent calls.
    """
    settings = get_settings()
    engine = create_engine(
        settings.database_url,
        pool_pre_ping=True,
        echo=settings.log_level == "DEBUG",
    )
    db_url_safe = (
        str(settings.database_url).split("@")[-1]
        if "@" in str(settings.database_url)
        else str(settings.database_url)
    )
    logger.info("Database engine created: %s", db_url_safe)
    return engine


def get_db() -> Generator[Session, None, None]:
    """Get a database session.

    This is a FastAPI dependency that provides a database session
    and ensures it's closed after the request.
    """
    engine = get_engine()
    with Session(engine) as session:
        yield session


def init_db() -> None:
    """Initialize the database by creating all tables."""
    # Import models here to ensure they're registered with SQLModel
    # This is necessary for SQLModel to discover all table definitions
    from . import db_models  # noqa: F401  # type: ignore

    engine = get_engine()
    SQLModel.metadata.create_all(engine)
    logger.info("Database tables created")
