"""Authentication and authorization models.

This module defines the data models for API keys, users, and permissions.
"""

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class UserRole(str, Enum):
    """User roles for authorization."""

    ADMIN = "admin"  # Full access to all endpoints and management
    USER = "user"  # Standard access to enrichment endpoints
    READONLY = "readonly"  # Read-only access (no write operations)


class RateLimitTier(str, Enum):
    """Rate limit tiers for different API key types."""

    FREE = "free"  # 100 requests/hour
    BASIC = "basic"  # 1,000 requests/hour
    PREMIUM = "premium"  # 10,000 requests/hour
    UNLIMITED = "unlimited"  # No rate limit


class APIKey(BaseModel):
    """API Key model for authentication.

    API keys are used to authenticate requests to the API.
    Each key has an associated role, rate limit tier, and usage tracking.
    """

    key: str = Field(..., description="The API key string")
    name: str = Field(..., description="Human-readable name for the key")
    role: UserRole = Field(default=UserRole.USER, description="Role for authorization")
    tier: RateLimitTier = Field(
        default=RateLimitTier.FREE, description="Rate limit tier"
    )

    # Usage tracking
    created_at: datetime = Field(default_factory=datetime.now)
    last_used_at: Optional[datetime] = None
    request_count: int = Field(
        default=0, description="Total requests made with this key"
    )

    # Optional restrictions
    enabled: bool = Field(default=True, description="Whether the key is active")
    expires_at: Optional[datetime] = None
    allowed_ips: Optional[list[str]] = Field(
        default=None,
        description="IP addresses allowed to use this key (None = all IPs)",
    )

    def is_expired(self) -> bool:
        """Check if the API key is expired."""
        if self.expires_at is None:
            return False
        return datetime.now() > self.expires_at

    def is_valid(self) -> bool:
        """Check if the API key is valid (enabled and not expired)."""
        return self.enabled and not self.is_expired()

    def get_rate_limit(self) -> int:
        """Get the requests per hour limit for this key."""
        limits = {
            RateLimitTier.FREE: 100,
            RateLimitTier.BASIC: 1000,
            RateLimitTier.PREMIUM: 10000,
            RateLimitTier.UNLIMITED: 999999999,  # Effectively unlimited
        }
        return limits[self.tier]


class AuthenticatedUser(BaseModel):
    """Represents an authenticated user/API key.

    This is the model passed through the request context after authentication.
    """

    api_key: str = Field(..., description="The API key used")
    role: UserRole = Field(..., description="User's role")
    tier: RateLimitTier = Field(..., description="Rate limit tier")
    name: str = Field(..., description="Name of the API key")

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


class CreateAPIKeyRequest(BaseModel):
    """Request model for creating a new API key."""

    name: str = Field(
        ..., min_length=3, max_length=100, description="Name for the API key"
    )
    role: UserRole = Field(default=UserRole.USER, description="Role to assign")
    tier: RateLimitTier = Field(
        default=RateLimitTier.FREE, description="Rate limit tier"
    )
    expires_in_days: Optional[int] = Field(
        None, gt=0, le=3650, description="Days until expiration (None = never expires)"
    )
    allowed_ips: Optional[list[str]] = None


class APIKeyResponse(BaseModel):
    """Response model for API key operations."""

    key: str
    name: str
    role: UserRole
    tier: RateLimitTier
    created_at: datetime
    expires_at: Optional[datetime]
    enabled: bool
    request_count: int
    rate_limit_per_hour: int
