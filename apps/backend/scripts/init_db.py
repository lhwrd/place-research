"""Setup script to initialize the database with new tables."""

import logging

from place_research.config import get_settings
from sqlmodel import SQLModel, create_engine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def init_db():
    """Initialize database with new tables."""
    settings = get_settings()
    engine = create_engine(settings.database_url, echo=True)

    logger.info("Creating database tables...")
    SQLModel.metadata.create_all(engine)
    logger.info("Database tables created successfully!")


if __name__ == "__main__":
    init_db()
