"""
CLMStore — Order Models
Tables: orders, order_items, order_status_history
"""
from __future__ import annotations

from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import (
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import TimestampMixin
from app.utils.constants import OrderStatus, PaymentProvider

if TYPE_CHECKING:
    from app.models.user import User, UserAddress
    from app.models.restaurant import Restaurant
    from app.models.rider import RiderProfile
    from app.models.payment import Payment
    from app.models.coupon import Coupon
    from app.models.delivery import Delivery
    from app.models.review import Review


class Order(Base, TimestampMixin):
    __tablename__ = "orders"
    __table_args__ = (
        Index("ix_orders_user_id", "user_id"),
        Index("ix_orders_restaurant_id", "restaurant_id"),
        Index("ix_orders_rider_id", "rider_id"),
        Index("ix_orders_status", "status"),
        Index("ix_orders_order_number", "order_number"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    order_number: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)  # CLM-20240101-0001
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    restaurant_id: Mapped[int] = mapped_column(Integer, ForeignKey("restaurants.id", ondelete="RESTRICT"), nullable=False)
    rider_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    delivery_address_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("user_addresses.id", ondelete="SET NULL"), nullable=True)
    coupon_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("coupons.id", ondelete="SET NULL"), nullable=True)

    status: Mapped[OrderStatus] = mapped_column(
        SAEnum(OrderStatus, name="order_status_enum"),
        nullable=False,
        default=OrderStatus.PENDING,
    )
    payment_method: Mapped[Optional[PaymentProvider]] = mapped_column(
        SAEnum(PaymentProvider, name="payment_provider_enum_order"), nullable=True
    )
    payment_status: Mapped[str] = mapped_column(String(50), nullable=False, default="pending")

    # Financial breakdown (snapshot at order time)
    subtotal: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    delivery_fee: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    service_fee: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    tax_amount: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    discount_amount: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    total_amount: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    currency: Mapped[str] = mapped_column(String(10), nullable=False, default="SLL")

    # Delivery details (snapshot)
    delivery_address_snapshot: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    delivery_distance_km: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    estimated_delivery_min: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    rejection_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    cancellation_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    customer: Mapped["User"] = relationship("User", foreign_keys=[user_id], back_populates="orders")
    restaurant: Mapped["Restaurant"] = relationship("Restaurant", back_populates="orders")
    rider: Mapped[Optional["User"]] = relationship("User", foreign_keys=[rider_id])
    delivery_address: Mapped[Optional["UserAddress"]] = relationship("UserAddress")
    coupon: Mapped[Optional["Coupon"]] = relationship("Coupon")
    items: Mapped[List["OrderItem"]] = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")
    status_history: Mapped[List["OrderStatusHistory"]] = relationship("OrderStatusHistory", back_populates="order", cascade="all, delete-orphan")
    payment: Mapped[Optional["Payment"]] = relationship("Payment", back_populates="order", uselist=False)
    delivery: Mapped[Optional["Delivery"]] = relationship("Delivery", back_populates="order", uselist=False)
    reviews: Mapped[List["Review"]] = relationship("Review", back_populates="order")

    def __repr__(self) -> str:
        return f"<Order id={self.id} number={self.order_number} status={self.status}>"


class OrderItem(Base):
    __tablename__ = "order_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    order_id: Mapped[int] = mapped_column(Integer, ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True)
    menu_item_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("menu_items.id", ondelete="SET NULL"), nullable=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)  # Snapshot
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    unit_price: Mapped[float] = mapped_column(Float, nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    variants: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)  # [{name, price_modifier}]
    addons: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)   # [{name, price}]
    customizations: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)  # [{group_id, group_name, option_id, option_name, price_modifier}]
    special_instructions: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    subtotal: Mapped[float] = mapped_column(Float, nullable=False)

    order: Mapped["Order"] = relationship("Order", back_populates="items")


class OrderStatusHistory(Base, TimestampMixin):
    __tablename__ = "order_status_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    order_id: Mapped[int] = mapped_column(Integer, ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True)
    status: Mapped[OrderStatus] = mapped_column(SAEnum(OrderStatus, name="order_status_history_enum"), nullable=False)
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    changed_by: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    order: Mapped["Order"] = relationship("Order", back_populates="status_history")
    changed_by_user: Mapped[Optional["User"]] = relationship("User", foreign_keys=[changed_by])
