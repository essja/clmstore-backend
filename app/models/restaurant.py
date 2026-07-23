"""
CLMStore — Restaurant Models
Tables: restaurants, restaurant_documents, opening_hours, restaurant_employees
"""
from __future__ import annotations

from datetime import time
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import (
    Boolean,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    Time,
    UniqueConstraint,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import TimestampMixin
from app.utils.constants import DayOfWeek, DocumentType, OperatingStatus, RestaurantStatus, StoreType

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.menu import FoodCategory, MenuItem
    from app.models.order import Order


class Restaurant(Base, TimestampMixin):
    __tablename__ = "restaurants"
    __table_args__ = (
        Index("ix_restaurants_owner_id", "owner_id"),
        Index("ix_restaurants_status", "status"),
        Index("ix_restaurants_slug", "slug"),
        Index("ix_restaurants_location", "latitude", "longitude"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    owner_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(220), unique=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    logo: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    cover_image: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    store_type: Mapped[StoreType] = mapped_column(
        SAEnum(StoreType, name="store_type_enum"),
        nullable=False,
        default=StoreType.RESTAURANT,
    )
    cuisine_type: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[RestaurantStatus] = mapped_column(
        SAEnum(RestaurantStatus, name="restaurant_status_enum"),
        nullable=False,
        default=RestaurantStatus.PENDING,
    )
    is_open: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    operating_status: Mapped[str] = mapped_column(String(30), nullable=False, default=OperatingStatus.OPEN.value, server_default="open")
    is_featured: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Location
    address: Mapped[str] = mapped_column(Text, nullable=False)
    city: Mapped[str] = mapped_column(String(100), nullable=False, default="Freetown")
    latitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    longitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Business Settings
    phone: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    min_order: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    delivery_fee: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    delivery_radius_km: Mapped[float] = mapped_column(Float, nullable=False, default=5.0)
    min_delivery_time_min: Mapped[int] = mapped_column(Integer, nullable=False, default=20)
    avg_delivery_time_min: Mapped[int] = mapped_column(Integer, nullable=False, default=35)
    commission_rate: Mapped[float] = mapped_column(Float, nullable=False, default=0.15)

    # Wallet (settled automatically when orders are delivered)
    current_balance: Mapped[float] = mapped_column(Float, nullable=False, default=0.0, server_default="0")
    total_earnings: Mapped[float] = mapped_column(Float, nullable=False, default=0.0, server_default="0")

    # Ratings (denormalised for fast queries)
    avg_rating: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    total_reviews: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_orders: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Admin fields
    approved_at: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    approved_by: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    suspension_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    owner: Mapped["User"] = relationship("User", foreign_keys=[owner_id])
    documents: Mapped[List["RestaurantDocument"]] = relationship("RestaurantDocument", back_populates="restaurant", cascade="all, delete-orphan")
    opening_hours: Mapped[List["OpeningHours"]] = relationship("OpeningHours", back_populates="restaurant", cascade="all, delete-orphan")
    employees: Mapped[List["RestaurantEmployee"]] = relationship("RestaurantEmployee", back_populates="restaurant", cascade="all, delete-orphan")
    categories: Mapped[List["FoodCategory"]] = relationship("FoodCategory", back_populates="restaurant")
    menu_items: Mapped[List["MenuItem"]] = relationship("MenuItem", back_populates="restaurant")
    orders: Mapped[List["Order"]] = relationship("Order", back_populates="restaurant")
    earnings: Mapped[List["RestaurantEarning"]] = relationship("RestaurantEarning", back_populates="restaurant", cascade="all, delete-orphan")
    withdrawals: Mapped[List["RestaurantWithdrawal"]] = relationship("RestaurantWithdrawal", back_populates="restaurant", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Restaurant id={self.id} name={self.name} status={self.status}>"


class RestaurantEarning(Base, TimestampMixin):
    __tablename__ = "restaurant_earnings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    restaurant_id: Mapped[int] = mapped_column(Integer, ForeignKey("restaurants.id", ondelete="CASCADE"), nullable=False, index=True)
    order_id: Mapped[int] = mapped_column(Integer, ForeignKey("orders.id", ondelete="RESTRICT"), nullable=False)
    gross_amount: Mapped[float] = mapped_column(Float, nullable=False)
    commission_rate: Mapped[float] = mapped_column(Float, nullable=False)
    commission_amount: Mapped[float] = mapped_column(Float, nullable=False)
    net_amount: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="settled")

    restaurant: Mapped["Restaurant"] = relationship("Restaurant", back_populates="earnings")


class RestaurantWithdrawal(Base, TimestampMixin):
    __tablename__ = "restaurant_withdrawals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    restaurant_id: Mapped[int] = mapped_column(Integer, ForeignKey("restaurants.id", ondelete="CASCADE"), nullable=False, index=True)
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="pending")
    payment_method: Mapped[str] = mapped_column(String(50), nullable=False)
    payment_details: Mapped[str] = mapped_column(Text, nullable=False)
    transaction_reference: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    processed_at: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    processed_by: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)

    restaurant: Mapped["Restaurant"] = relationship("Restaurant", back_populates="withdrawals")


class RestaurantDocument(Base, TimestampMixin):
    __tablename__ = "restaurant_documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    restaurant_id: Mapped[int] = mapped_column(Integer, ForeignKey("restaurants.id", ondelete="CASCADE"), nullable=False, index=True)
    doc_type: Mapped[DocumentType] = mapped_column(SAEnum(DocumentType, name="doc_type_enum"), nullable=False)
    file_url: Mapped[str] = mapped_column(String(500), nullable=False)
    file_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    verified_by: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    restaurant: Mapped["Restaurant"] = relationship("Restaurant", back_populates="documents")


class OpeningHours(Base):
    __tablename__ = "opening_hours"
    __table_args__ = (
        UniqueConstraint("restaurant_id", "day_of_week", name="uq_restaurant_day"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    restaurant_id: Mapped[int] = mapped_column(Integer, ForeignKey("restaurants.id", ondelete="CASCADE"), nullable=False, index=True)
    day_of_week: Mapped[DayOfWeek] = mapped_column(SAEnum(DayOfWeek, name="day_of_week_enum"), nullable=False)
    open_time: Mapped[Optional[time]] = mapped_column(Time, nullable=True)
    close_time: Mapped[Optional[time]] = mapped_column(Time, nullable=True)
    is_closed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    restaurant: Mapped["Restaurant"] = relationship("Restaurant", back_populates="opening_hours")


class RestaurantEmployee(Base, TimestampMixin):
    __tablename__ = "restaurant_employees"
    __table_args__ = (
        UniqueConstraint("restaurant_id", "user_id", name="uq_restaurant_employee"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    restaurant_id: Mapped[int] = mapped_column(Integer, ForeignKey("restaurants.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    role: Mapped[str] = mapped_column(String(50), nullable=False, default="staff")  # manager, cashier, staff
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    restaurant: Mapped["Restaurant"] = relationship("Restaurant", back_populates="employees")
    user: Mapped["User"] = relationship("User")
