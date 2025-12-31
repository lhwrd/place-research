"""Database models for authentication using SQLModel."""

from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel

from .models.auth import UserRole


class User(SQLModel, table=True):
    """User model for authentication.

    Users authenticate with username/password to receive JWT tokens.
    """

    id: Optional[int] = Field(default=None, primary_key=True, index=True)
    username: str = Field(max_length=100, unique=True, index=True)
    email: str = Field(max_length=255, unique=True, index=True)
    hashed_password: str = Field(max_length=255)
    role: UserRole = Field(default=UserRole.USER)

    # Account status
    is_active: bool = Field(default=True)
    is_verified: bool = Field(default=False)

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    last_login_at: Optional[datetime] = Field(default=None)

    def __repr__(self) -> str:
        return f"<User(username={self.username}, role={self.role})>"
