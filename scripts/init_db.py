#!/usr/bin/env python3
"""Database initialization script for place-research.

This script initializes the database schema and creates an initial admin user.
Run this after setting up your environment variables.

Usage:
    python scripts/init_db.py
    python scripts/init_db.py --admin-username admin --admin-email admin@example.com
"""

import argparse
import getpass
import logging
import sys
from pathlib import Path

# Add src to path so we can import place_research
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from place_research.config import get_settings
from place_research.database import Base, get_engine, get_session_maker
from place_research.db_models import User
from place_research.models.auth import UserRole
from place_research.security import hash_password

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def init_database():
    """Initialize the database by creating all tables."""
    logger.info("Initializing database...")

    settings = get_settings()
    logger.info("Database URL: %s", settings.database_url.split("@")[-1])

    engine = get_engine()
    Base.metadata.create_all(bind=engine)

    logger.info("✓ Database tables created successfully")


def create_admin_user(username: str, email: str, password: str):
    """Create an admin user.

    Args:
        username: Admin username
        email: Admin email
        password: Admin password
    """
    SessionLocal = get_session_maker()
    db = SessionLocal()

    try:
        # Check if user already exists
        existing_user = db.query(User).filter(User.username == username).first()
        if existing_user:
            logger.error("✗ User '%s' already exists", username)
            return False

        # Create admin user
        admin_user = User(
            username=username,
            email=email,
            hashed_password=hash_password(password),
            role=UserRole.ADMIN,
            is_active=True,
            is_verified=True,
        )

        db.add(admin_user)
        db.commit()

        logger.info("✓ Admin user '%s' created successfully", username)
        logger.info("  Email: %s", email)
        logger.info("  Role: ADMIN")
        return True

    except Exception as e:
        logger.error("✗ Error creating admin user: %s", str(e))
        db.rollback()
        return False
    finally:
        db.close()


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Initialize place-research database and create admin user"
    )
    parser.add_argument(
        "--admin-username",
        default="admin",
        help="Admin username (default: admin)",
    )
    parser.add_argument(
        "--admin-email",
        default="admin@example.com",
        help="Admin email (default: admin@example.com)",
    )
    parser.add_argument(
        "--admin-password",
        help="Admin password (will prompt if not provided)",
    )
    parser.add_argument(
        "--skip-user",
        action="store_true",
        help="Only create database tables, skip user creation",
    )

    args = parser.parse_args()

    # Check for required environment variables
    try:
        settings = get_settings()
        if not settings.jwt_secret_key:
            logger.error("✗ JWT_SECRET_KEY environment variable is required")
            logger.info("  Generate one with: openssl rand -hex 32")
            sys.exit(1)
    except Exception as e:
        logger.error("✗ Error loading settings: %s", str(e))
        logger.info("  Make sure JWT_SECRET_KEY is set in your .env file")
        sys.exit(1)

    # Initialize database
    try:
        init_database()
    except Exception as e:
        logger.error("✗ Error initializing database: %s", str(e))
        sys.exit(1)

    # Create admin user unless skipped
    if not args.skip_user:
        # Get password
        if args.admin_password:
            password = args.admin_password
        else:
            password = getpass.getpass(
                f"Enter password for admin user '{args.admin_username}': "
            )
            confirm = getpass.getpass("Confirm password: ")

            if password != confirm:
                logger.error("✗ Passwords do not match")
                sys.exit(1)

            if len(password) < 8:
                logger.error("✗ Password must be at least 8 characters")
                sys.exit(1)

        success = create_admin_user(args.admin_username, args.admin_email, password)
        if not success:
            sys.exit(1)

    logger.info("\n✓ Database initialization complete!")
    logger.info("\nNext steps:")
    logger.info(
        "  1. Start the API server: uv run uvicorn place_research.api.server:app"
    )
    logger.info("  2. Login at: POST /auth/login")
    logger.info("  3. Create API keys at: POST /auth/keys")


if __name__ == "__main__":
    main()
