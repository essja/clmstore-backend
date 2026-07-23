"""
CLMStore — Coupon Models
Tables: coupons, coupon_usages
"""
from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import TimestampMixin
from app.utils.constants import CouponType

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.order import Order
    from app.models.restaurant import Restaurant


class Coupon(Base, TimestampMixin):
    __tablename__ = "coupons"
    __table_args__ = (
        Index("ix_coupons_code", "code"),
        Index("ix_coupons_is_active", "is_active"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    type: Mapped[CouponType] = mapped_column(SAEnum(CouponType, name="coupon_type_enum"), nullable=False, default=CouponType.PERCENTAGE)
    value: Mapped[float] = mapped_column(Float, nullable=False)  # Percentage amount or fixed value
    min_order_value: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    max_discount: Mapped[Optional[float]] = mapped_column(Float, nullable=True)  # Applicable to percentage coupons
    restaurant_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("restaurants.id", ondelete="CASCADE"), nullable=True)  # Null = Global coupon
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    usage_limit: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # Total limit of usages globally
    user_usage_limit: Mapped[int] = mapped_column(Integer, nullable=False, default=1)  # Limit of usages per user
    used_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    restaurant: Mapped[Optional["Restaurant"]] = relationship("Restaurant")
    usages: Mapped[List["CouponUsage"]] = relationship("CouponUsage", back_populates="coupon", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Coupon id={self.id} code={self.code} type={self.type} active={self.is_active}>"


class CouponUsage(Base, TimestampMixin):
    __tablename__ = "coupon_usages"
    __table_args__ = (
        Index("ix_coupon_usages_coupon_id", "coupon_id"),
        Index("ix_coupon_usages_user_id", "user_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    coupon_id: Mapped[int] = mapped_column(Integer, ForeignKey("coupons.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    order_id: Mapped[int] = mapped_column(Integer, ForeignKey("orders.id", ondelete="CASCADE"), nullable=False)
    discount_amount: Mapped[float] = mapped_column(Float, nullable=False)

    coupon: Mapped["Coupon"] = relationship("Coupon", back_populates="usages")
    user: Mapped["User"] = relationship("User")
    order: Mapped["Order"] = relationship("Order")
