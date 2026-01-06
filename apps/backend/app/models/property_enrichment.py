"""Updated property enrichment model with dynamic data support."""

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import functions as func

from app.db.database import Base


class PropertyEnrichment(Base):
    __tablename__ = "property_enrichments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    property_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("properties.id"), unique=True, nullable=False
    )

    # Structure: {"provider_name": {... data...}, "another_provider": {...data...}}
    dynamic_enrichment_data: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)

    # Cache management
    is_cached: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    cache_expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Metadata
    enriched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), onupdate=func.now(), server_default=func.now()
    )

    # API call tracking
    api_calls_made: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)

    # Relationships
    property = relationship("Property", back_populates="enrichment")

    def __repr__(self):
        return f"<PropertyEnrichment(property_id={self.property_id})>"
