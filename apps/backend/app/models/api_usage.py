"""API usage tracking for rate limiting and cost management."""

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import functions as func

from app.db.database import Base


class APIUsage(Base):
    __tablename__ = "api_usage"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)

    # API call details
    service_name: Mapped[str] = mapped_column(
        String, nullable=False
    )  # "walk_score", "google_maps", etc.
    endpoint: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    # Usage tracking
    calls_count: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    estimated_cost: Mapped[Optional[float]] = mapped_column(Float, nullable=True)  # In USD

    # Request details
    request_params: Mapped[Optional[str]] = mapped_column(String, nullable=True)  # For debugging
    response_status: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True
    )  # HTTP status code

    # Timestamps
    called_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    user = relationship("User")

    # Indexes for rate limiting queries
    __table_args__ = (
        Index("ix_api_usage_user_service_time", "user_id", "service_name", "called_at"),
    )

    def __repr__(self):
        return f"<APIUsage(user_id={self.user_id}, service={self.service_name})>"
