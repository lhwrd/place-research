"""User service for user management operations."""

import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.core.security import get_password_hash, verify_password
from app.models.user import User
from app.models.user_preference import UserPreference

logger = logging.getLogger(__name__)


class UserService:
    """Service for user-related operations."""

    def __init__(self, db: Session):
        self.db = db

    def get_user_by_email(self, email: str) -> Optional[User]:
        """Get user by email address."""
        return self.db.query(User).filter(User.email == email).first()

    def get_user_by_id(self, user_id: int) -> Optional[User]:
        """Get user by ID."""
        return self.db.query(User).filter(User.id == user_id).first()

    def create_user(self, email: str, password: str, full_name: Optional[str] = None) -> User:
        """
        Create a new user.

        Args:
            email:  User email
            password: Plain text password (will be hashed)
            full_name: Optional full name

        Returns:
            Created user object
        """
        user = User(
            email=email,
            hashed_password=get_password_hash(password),
            full_name=full_name,
            is_active=True,
            is_superuser=False,
        )

        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)

        # Create default user preferences
        preferences = UserPreference(user_id=user.id)
        self.db.add(preferences)
        self.db.commit()

        logger.info("Created user: %s", email)

        return user

    def authenticate_user(self, email: str, password: str) -> Optional[User]:
        """
        Authenticate a user with email and password.

        Args:
            email:  User email
            password: Plain text password

        Returns:
            User object if authentication successful, None otherwise
        """
        user = self.get_user_by_email(email)

        if not user:
            return None

        if not verify_password(password, user.hashed_password):
            return None

        return user

    def update_user(self, user_id: int, updates: dict) -> User:
        """
        Update user information.

        Args:
            user_id: User ID
            updates: Dictionary of fields to update

        Returns:
            Updated user object
        """
        user = self.get_user_by_id(user_id)

        for key, value in updates.items():
            if hasattr(user, key):
                setattr(user, key, value)

        user.updated_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(user)

        return user

    def update_password(self, user_id: int, new_password: str) -> None:
        """
        Update user password.

        Args:
            user_id: User ID
            new_password: New plain text password (will be hashed)
        """
        user = self.get_user_by_id(user_id)
        user.hashed_password = get_password_hash(new_password)
        user.updated_at = datetime.now(timezone.utc)

        self.db.commit()

    def update_last_login(self, user_id: int) -> None:
        """Update user's last login timestamp."""
        user = self.get_user_by_id(user_id)
        user.last_login = datetime.now(timezone.utc)
        self.db.commit()

    def deactivate_user(self, user_id: int) -> None:
        """Deactivate a user account (soft delete)."""
        user = self.get_user_by_id(user_id)
        user.is_active = False
        user.updated_at = datetime.now(timezone.utc)

        self.db.commit()

        logger.info("Deactivated user: %s", user.email)

    def activate_user(self, user_id: int) -> None:
        """Reactivate a user account."""
        user = self.get_user_by_id(user_id)
        user.is_active = True
        user.updated_at = datetime.now(timezone.utc)

        self.db.commit()

        logger.info("Activated user: %s", user.email)
