"""
CLMStore — Cart Models
Tables: carts, cart_items
Supports both authenticated users and guest sessions.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import (
    Boolean,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import TimestampMixin

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.restaurant import Restaurant
    from app.models.menu import MenuItem, MenuItemVariant
    from app.models.coupon import Coupon


class Cart(Base, TimestampMixin):
    __tablename__ = "carts"
    __table_args__ = (
        Index("ix_carts_user_id", "user_id"),
        Index("ix_carts_session_id", "session_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=True
    )
    session_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)  # Guest cart
    restaurant_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("restaurants.id", ondelete="SET NULL"), nullable=True
    )
    coupon_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("coupons.id", ondelete="SET NULL"), nullable=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationships
    user: Mapped[Optional["User"]] = relationship("User")
    restaurant: Mapped[Optional["Restaurant"]] = relationship("Restaurant")
    items: Mapped[List["CartItem"]] = relationship(
        "CartItem", back_populates="cart", cascade="all, delete-orphan",
        lazy="selectin",
    )
    coupon: Mapped[Optional["Coupon"]] = relationship("Coupon")

    @property
    def subtotal(self) -> float:
        return round(sum(item.subtotal for item in self.items), 2)

    @property
    def item_count(self) -> int:
        return sum(item.quantity for item in self.items)

    def __repr__(self) -> str:
        return f"<Cart id={self.id} user_id={self.user_id}>"


class CartItem(Base, TimestampMixin):
    __tablename__ = "cart_items"
    __table_args__ = (
        Index("ix_cart_items_cart_id", "cart_id"),
        Index("ix_cart_items_menu_item_id", "menu_item_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    cart_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("carts.id", ondelete="CASCADE"), nullable=False
    )
    menu_item_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("menu_items.id", ondelete="CASCADE"), nullable=False
    )
    variant_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("menu_item_variants.id", ondelete="SET NULL"), nullable=True
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    unit_price: Mapped[float] = mapped_column(Float, nullable=False)  # Snapshot at add time
    addons: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)  # [{id, name, price}]
    customizations: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)  # [{group_id, group_name, option_id, option_name, price_modifier}]
    special_instructions: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    cart: Mapped["Cart"] = relationship("Cart", back_populates="items")
    menu_item: Mapped["MenuItem"] = relationship("MenuItem")
    variant: Mapped[Optional["MenuItemVariant"]] = relationship("MenuItemVariant")

    @property
    def addons_total(self) -> float:
        if not self.addons:
            return 0.0
        return sum(a.get("price", 0) for a in self.addons)

    @property
    def item_price(self) -> float:
        """Unit price including variant modifier."""
        return self.unit_price

    @property
    def subtotal(self) -> float:
        return round((self.item_price + self.addons_total) * self.quantity, 2)
