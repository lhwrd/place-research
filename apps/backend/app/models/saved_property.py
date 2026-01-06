"""Saved property model for user's favorite/saved properties."""

from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import functions as func

from app.db.database import Base


class SavedProperty(Base):
    __tablename__ = "saved_properties"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    property_id: Mapped[int] = mapped_column(Integer, ForeignKey("properties.id"), nullable=False)

    # User notes
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    rating: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # 1-5 stars

    # Tags for organization
    tags: Mapped[Optional[str]] = mapped_column(
        String, nullable=True
    )  # Comma-separated:  "favorite,close-to-work,good-schools"

    # Status tracking
    is_favorite: Mapped[bool] = mapped_column(Boolean, default=False)
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False)

    # Viewing information
    viewed_in_person: Mapped[bool] = mapped_column(Boolean, default=False)
    viewing_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Metadata
    saved_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), onupdate=func.now(), server_default=func.now()
    )

    # Relationships
    user = relationship("User", back_populates="saved_properties")
    property = relationship("Property", back_populates="saved_by")

    # Constraints
    __table_args__ = (UniqueConstraint("user_id", "property_id", name="unique_user_property"),)

    def __repr__(self):
        return f"<SavedProperty(user_id={self.user_id}, property_id={self.property_id})>"
