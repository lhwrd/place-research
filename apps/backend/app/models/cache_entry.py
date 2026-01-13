"""Cache entry model for storing cached data."""

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import functions as func

from app.db.database import Base


class CacheEntry(Base):
    """Model for storing cache entries."""

    __tablename__ = "cache_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    # Cache key (unique identifier)
    key: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)

    # Cached value (stored as JSON string)
    value: Mapped[str] = mapped_column(Text, nullable=False)

    # Expiration
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Access tracking
    access_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_accessed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Metadata
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), onupdate=func.now(), server_default=func.now()
    )

    # Indexes for efficient queries
    __table_args__ = (
        Index("ix_cache_entries_expires_at", "expires_at"),
        Index("ix_cache_entries_key_expires", "key", "expires_at"),
    )

    def __repr__(self):
        return f"<CacheEntry(key={self.key}, expires_at={self.expires_at})>"
