"""Authentication and authorization models.

This module defines the data models for users, JWT tokens, and permissions.
"""

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, EmailStr, Field


class UserRole(str, Enum):
    """User roles for authorization."""

    ADMIN = "admin"  # Full access to all endpoints and management
    USER = "user"  # Standard access to enrichment endpoints
    READONLY = "readonly"  # Read-only access (no write operations)


class AuthenticatedUser(BaseModel):
    """Represents an authenticated user.

    This is the model passed through the request context after authentication.
    For backward compatibility, includes api_key and tier fields (unused).
    """

    api_key: str = Field(default="", description="Deprecated - not used")
    role: UserRole = Field(..., description="User's role")
    tier: str = Field(default="unlimited", description="Access tier")
    name: str = Field(..., description="Username")

    def has_role(self, required_role: UserRole) -> bool:
        """Check if user has at least the required role.

        Role hierarchy: ADMIN > USER > READONLY
        """
        role_hierarchy = {
            UserRole.READONLY: 0,
            UserRole.USER: 1,
            UserRole.ADMIN: 2,
        }
        return role_hierarchy[self.role] >= role_hierarchy[required_role]

    def can_write(self) -> bool:
        """Check if user can perform write operations."""
        return self.role in [UserRole.USER, UserRole.ADMIN]

    def is_admin(self) -> bool:
        """Check if user is an admin."""
        return self.role == UserRole.ADMIN


# OAuth2 and User Management Models


class UserCreate(BaseModel):
    """Request model for creating a new user."""

    username: str = Field(
        ..., min_length=3, max_length=50, description="Unique username"
    )
    email: EmailStr = Field(..., description="Email address")
    password: str = Field(..., min_length=8, max_length=100, description="Password")
    role: UserRole = Field(default=UserRole.USER, description="User role")


class UserLogin(BaseModel):
    """Request model for user login."""

    username: str = Field(..., description="Username")
    password: str = Field(..., description="Password")


class UserResponse(BaseModel):
    """Response model for user operations."""

    id: int
    username: str
    email: str
    role: UserRole
    is_active: bool
    is_verified: bool
    created_at: datetime
    last_login_at: Optional[datetime]

    class Config:
        from_attributes = True


class Token(BaseModel):
    """OAuth2 token response."""

    access_token: str
    token_type: str = "bearer"
    expires_in: int
    refresh_token: Optional[str] = None


class TokenData(BaseModel):
    """Data extracted from JWT token."""

    user_id: int
    username: str
    role: UserRole
