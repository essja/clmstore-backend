"""
CLMStore — Delivery Models
Tables: deliveries, rider_locations
"""
from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import TimestampMixin
from app.utils.constants import DeliveryStatus

if TYPE_CHECKING:
    from app.models.order import Order
    from app.models.user import User


class Delivery(Base, TimestampMixin):
    __tablename__ = "deliveries"
    __table_args__ = (
        Index("ix_deliveries_order_id", "order_id"),
        Index("ix_deliveries_rider_id", "rider_id"),
        Index("ix_deliveries_status", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    order_id: Mapped[int] = mapped_column(Integer, ForeignKey("orders.id", ondelete="CASCADE"), nullable=False)
    rider_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    status: Mapped[DeliveryStatus] = mapped_column(SAEnum(DeliveryStatus, name="delivery_status_enum"), nullable=False, default=DeliveryStatus.PENDING)

    # GPS coordinates
    pickup_latitude: Mapped[float] = mapped_column(Float, nullable=False)
    pickup_longitude: Mapped[float] = mapped_column(Float, nullable=False)
    dropoff_latitude: Mapped[float] = mapped_column(Float, nullable=False)
    dropoff_longitude: Mapped[float] = mapped_column(Float, nullable=False)

    distance_km: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    estimated_duration_min: Mapped[int] = mapped_column(Integer, nullable=False, default=15)

    # Timestamps
    assigned_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    accepted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    picked_up_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    delivered_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    failed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    failure_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    order: Mapped["Order"] = relationship("Order", back_populates="delivery")
    rider: Mapped[Optional["User"]] = relationship("User")


class RiderLocation(Base):
    __tablename__ = "rider_locations"
    __table_args__ = (
        Index("ix_rider_locations_rider_id", "rider_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    rider_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    bearing: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    rider: Mapped["User"] = relationship("User")
