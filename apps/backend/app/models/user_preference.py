"""User preference model for storing user-specific enrichment preferences."""

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import functions as func

from app.db.database import Base


class UserPreference(Base):
    __tablename__ = "user_preferences"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), unique=True, nullable=False
    )

    # Minimum scores/thresholds
    min_walk_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # e.g., 70
    min_bike_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    min_transit_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Maximum distances (in miles)
    max_grocery_distance: Mapped[Optional[float]] = mapped_column(Float, nullable=True, default=2.0)
    max_park_distance: Mapped[Optional[float]] = mapped_column(Float, nullable=True, default=1.0)
    max_school_distance: Mapped[Optional[float]] = mapped_column(Float, nullable=True, default=3.0)
    max_hospital_distance: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True, default=10.0
    )

    # Maximum commute time (in minutes)
    max_commute_time: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Preferred amenity types (stored as JSON array)
    # e.g., ["organic_grocery", "gym", "coffee_shop", "library"]
    preferred_amenities: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)
    preferred_places: Mapped[Optional[Any]] = mapped_column(
        JSON, nullable=True
    )  # e.g., ["Central Park", "Union Square"]

    # Property preferences
    min_bedrooms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    min_bathrooms: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    min_square_feet: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    max_year_built: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True
    )  # e.g., only properties built after 1990
    preferred_property_types: Mapped[Optional[Any]] = mapped_column(
        JSON, nullable=True
    )  # ["Single Family", "Townhouse"]

    # Budget
    min_price: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    max_price: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Notification preferences
    notify_new_listings: Mapped[bool] = mapped_column(Boolean, default=False)
    notify_price_changes: Mapped[bool] = mapped_column(Boolean, default=False)

    # Metadata
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), onupdate=func.now(), server_default=func.now()
    )

    # Relationships
    user = relationship("User", back_populates="user_preferences")

    def __repr__(self):
        return f"<UserPreference(user_id={self.user_id})>"
