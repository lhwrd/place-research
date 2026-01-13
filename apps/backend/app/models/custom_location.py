"""Custom location model for storing family/friends addresses."""

from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import functions as func

from app.db.database import Base


class CustomLocation(Base):
    __tablename__ = "custom_locations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)

    # Location details
    name: Mapped[str] = mapped_column(
        String, nullable=False
    )  # e.g., "Mom's House", "Best Friend's Apt"
    description: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    # Address
    address: Mapped[str] = mapped_column(String, nullable=False)
    city: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    state: Mapped[Optional[str]] = mapped_column(String(2), nullable=True)
    zip_code: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)

    # Geolocation
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)

    # Configuration
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False
    )  # Can temporarily disable
    priority: Mapped[int] = mapped_column(
        Integer, default=0
    )  # For sorting (higher = more important)

    # Location type (for categorization)
    location_type: Mapped[Optional[str]] = mapped_column(
        String, nullable=True
    )  # "family", "friend", "work", "other"

    # Metadata
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), onupdate=func.now(), server_default=func.now()
    )

    # Relationships
    user = relationship("User", back_populates="custom_locations")

    def __repr__(self):
        return f"<CustomLocation(id={self.id}, name={self.name}, user_id={self.user_id})>"
