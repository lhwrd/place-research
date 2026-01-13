"""Database configuration and session management."""

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import settings

# Create database engine with appropriate configuration
# SQLite doesn't support pool_size and max_overflow parameters
is_sqlite = str(settings.database_url).startswith("sqlite")
is_memory_db = ":memory:" in str(settings.database_url)

if is_sqlite:
    # For in-memory databases, use StaticPool to ensure single connection
    # This is critical for testing - all threads must share the same in-memory database
    if is_memory_db:
        engine = create_engine(
            settings.database_url,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
            echo="DEBUG" in str(settings.log_level).upper(),
        )
    else:
        engine = create_engine(
            settings.database_url,
            connect_args={"check_same_thread": False},  # Allow SQLite to be used across threads
            echo="DEBUG" in str(settings.log_level).upper(),  # Log SQL queries in debug mode
        )
else:
    engine = create_engine(
        settings.database_url,
        pool_pre_ping=True,  # Verify connections before using
        pool_size=10,
        max_overflow=20,
        echo="DEBUG" in str(settings.log_level).upper(),  # Log SQL queries in debug mode
    )

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for models
Base = declarative_base()


def get_db():
    """
    Dependency for getting database sessions.
    Ensures sessions are properly closed after use.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
