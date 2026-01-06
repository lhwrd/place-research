"""Property model for storing property information."""

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import functions as func

from app.db.database import Base


class Property(Base):
    __tablename__ = "properties"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)

    # Address information
    address: Mapped[str] = mapped_column(String, nullable=False)
    city: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    state: Mapped[Optional[str]] = mapped_column(String(2), nullable=True)
    zip_code: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    county: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    # Geolocation
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)

    # Property details
    bedrooms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    bathrooms: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    square_feet: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    lot_size: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # in square feet
    year_built: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    property_type: Mapped[Optional[str]] = mapped_column(
        String, nullable=True
    )  # "Single Family", "Condo", etc.

    # Financial information
    estimated_value: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    last_sold_price: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    last_sold_date: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    tax_assessed_value: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    annual_tax: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Additional details
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    parcel_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)  # APN/Parcel number

    # External IDs (for caching/deduplication)
    zillow_id: Mapped[Optional[str]] = mapped_column(String, unique=True, nullable=True, index=True)

    # Metadata
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), onupdate=func.now(), server_default=func.now()
    )
    last_enriched_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    user = relationship("User", back_populates="properties")
    enrichment = relationship(
        "PropertyEnrichment",
        back_populates="property",
        uselist=False,
        cascade="all, delete-orphan",
    )
    saved_by = relationship(
        "SavedProperty", back_populates="property", cascade="all, delete-orphan"
    )

    # Indexes for common queries
    __table_args__ = (
        Index("ix_properties_user_created", "user_id", "created_at"),
        Index("ix_properties_location", "latitude", "longitude"),
    )

    def __repr__(self):
        return f"<Property(id={self.id}, address={self.address})>"
