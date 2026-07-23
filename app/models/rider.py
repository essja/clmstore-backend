"""
CLMStore — Rider Models
Tables: rider_profiles, rider_documents, rider_earnings, rider_withdrawals
"""
from __future__ import annotations

from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import (
    Boolean,
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
from app.utils.constants import VehicleType, DocumentType, EarningsStatus

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.delivery import Delivery


class RiderProfile(Base, TimestampMixin):
    __tablename__ = "rider_profiles"
    __table_args__ = (
        Index("ix_rider_profiles_user_id", "user_id"),
        Index("ix_rider_profiles_is_available", "is_available"),
        Index("ix_rider_profiles_is_verified", "is_verified"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    vehicle_type: Mapped[VehicleType] = mapped_column(SAEnum(VehicleType, name="vehicle_type_enum"), nullable=False, default=VehicleType.MOTORCYCLE)
    vehicle_plate: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    vehicle_model: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    vehicle_color: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    is_available: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    rating: Mapped[float] = mapped_column(Float, nullable=False, default=5.0)
    total_deliveries: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_earnings: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    current_balance: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    # Relationships
    user: Mapped["User"] = relationship("User")
    documents: Mapped[List["RiderDocument"]] = relationship("RiderDocument", back_populates="rider", cascade="all, delete-orphan")
    earnings: Mapped[List["RiderEarning"]] = relationship("RiderEarning", back_populates="rider", cascade="all, delete-orphan")
    withdrawals: Mapped[List["RiderWithdrawal"]] = relationship("RiderWithdrawal", back_populates="rider", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<RiderProfile id={self.id} user_id={self.user_id} verified={self.is_verified}>"


class RiderDocument(Base, TimestampMixin):
    __tablename__ = "rider_documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    rider_id: Mapped[int] = mapped_column(Integer, ForeignKey("rider_profiles.id", ondelete="CASCADE"), nullable=False, index=True)
    doc_type: Mapped[DocumentType] = mapped_column(SAEnum(DocumentType, name="rider_doc_type_enum"), nullable=False)
    file_url: Mapped[str] = mapped_column(String(500), nullable=False)
    file_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    verified_by: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    rider: Mapped["RiderProfile"] = relationship("RiderProfile", back_populates="documents")


class RiderEarning(Base, TimestampMixin):
    __tablename__ = "rider_earnings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    rider_id: Mapped[int] = mapped_column(Integer, ForeignKey("rider_profiles.id", ondelete="CASCADE"), nullable=False, index=True)
    order_id: Mapped[int] = mapped_column(Integer, ForeignKey("orders.id", ondelete="RESTRICT"), nullable=False)
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    commission_deducted: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    net_earning: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[EarningsStatus] = mapped_column(SAEnum(EarningsStatus, name="earnings_status_enum"), nullable=False, default=EarningsStatus.PENDING)

    rider: Mapped["RiderProfile"] = relationship("RiderProfile", back_populates="earnings")


class RiderWithdrawal(Base, TimestampMixin):
    __tablename__ = "rider_withdrawals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    rider_id: Mapped[int] = mapped_column(Integer, ForeignKey("rider_profiles.id", ondelete="CASCADE"), nullable=False, index=True)
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="pending")  # pending, approved, rejected, completed
    payment_method: Mapped[str] = mapped_column(String(50), nullable=False)  # orange_money, afrimoney, bank
    payment_details: Mapped[str] = mapped_column(Text, nullable=False)  # Phone number or bank account details
    transaction_reference: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    processed_at: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    processed_by: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)

    rider: Mapped["RiderProfile"] = relationship("RiderProfile", back_populates="withdrawals")
