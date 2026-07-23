"""
CLMStore — Menu Models
Tables: food_categories, menu_items, menu_item_variants, menu_item_addons,
        menu_option_groups, menu_options
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
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import TimestampMixin

if TYPE_CHECKING:
    from app.models.restaurant import Restaurant
    from app.models.cart import CartItem
    from app.models.order import OrderItem


class FoodCategory(Base, TimestampMixin):
    __tablename__ = "food_categories"
    __table_args__ = (
        Index("ix_food_categories_restaurant_id", "restaurant_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    restaurant_id: Mapped[int] = mapped_column(Integer, ForeignKey("restaurants.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    image: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    restaurant: Mapped["Restaurant"] = relationship("Restaurant", back_populates="categories")
    items: Mapped[List["MenuItem"]] = relationship("MenuItem", back_populates="category")


class MenuItem(Base, TimestampMixin):
    __tablename__ = "menu_items"
    __table_args__ = (
        Index("ix_menu_items_restaurant_id", "restaurant_id"),
        Index("ix_menu_items_category_id", "category_id"),
        Index("ix_menu_items_is_available", "is_available"),
        Index("ix_menu_items_is_popular", "is_popular"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    restaurant_id: Mapped[int] = mapped_column(Integer, ForeignKey("restaurants.id", ondelete="CASCADE"), nullable=False)
    category_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("food_categories.id", ondelete="SET NULL"), nullable=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    price: Mapped[float] = mapped_column(Float, nullable=False)
    image: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    is_available: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_popular: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_recommended: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_vegan: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_vegetarian: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_spicy: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    discount_percentage: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    stock_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # None = unlimited
    preparation_time_min: Mapped[int] = mapped_column(Integer, nullable=False, default=15)
    calories: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_orders: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    avg_rating: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    restaurant: Mapped["Restaurant"] = relationship("Restaurant", back_populates="menu_items")
    category: Mapped[Optional["FoodCategory"]] = relationship("FoodCategory", back_populates="items")
    variants: Mapped[List["MenuItemVariant"]] = relationship("MenuItemVariant", back_populates="menu_item", cascade="all, delete-orphan")
    addons: Mapped[List["MenuItemAddon"]] = relationship("MenuItemAddon", back_populates="menu_item", cascade="all, delete-orphan")
    option_groups: Mapped[List["MenuOptionGroup"]] = relationship(
        "MenuOptionGroup", back_populates="menu_item", cascade="all, delete-orphan",
        order_by="MenuOptionGroup.display_order",
    )

    @property
    def effective_price(self) -> float:
        if self.discount_percentage > 0:
            return round(self.price * (1 - self.discount_percentage / 100), 2)
        return self.price

    def __repr__(self) -> str:
        return f"<MenuItem id={self.id} name={self.name} price={self.price}>"


class MenuItemVariant(Base, TimestampMixin):
    __tablename__ = "menu_item_variants"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    menu_item_id: Mapped[int] = mapped_column(Integer, ForeignKey("menu_items.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)  # e.g. "Small", "Large", "Extra Large"
    price_modifier: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)  # Added to base price
    is_available: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    menu_item: Mapped["MenuItem"] = relationship("MenuItem", back_populates="variants")


class MenuItemAddon(Base, TimestampMixin):
    __tablename__ = "menu_item_addons"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    menu_item_id: Mapped[int] = mapped_column(Integer, ForeignKey("menu_items.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)  # e.g. "Extra Sauce", "Cheese"
    price: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    is_required: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    max_selections: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    is_available: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    menu_item: Mapped["MenuItem"] = relationship("MenuItem", back_populates="addons")


class MenuOptionGroup(Base, TimestampMixin):
    """Groups of customization choices on a menu item.

    group_type:
      'single'   — customer picks exactly one (e.g. Choose Protein)
      'multiple' — customer picks one or more (e.g. Add-ons)
      'removal'  — customer removes ingredients (e.g. No Onion)
    """
    __tablename__ = "menu_option_groups"
    __table_args__ = (
        Index("ix_menu_option_groups_item_id", "menu_item_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    menu_item_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("menu_items.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    group_type: Mapped[str] = mapped_column(String(20), nullable=False, default="multiple")
    is_required: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    min_selections: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_selections: Mapped[int] = mapped_column(Integer, nullable=False, default=1)  # 0 = unlimited
    display_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    menu_item: Mapped["MenuItem"] = relationship("MenuItem", back_populates="option_groups")
    options: Mapped[List["MenuOption"]] = relationship(
        "MenuOption", back_populates="group", cascade="all, delete-orphan",
        order_by="MenuOption.display_order",
    )

    def __repr__(self) -> str:
        return f"<MenuOptionGroup id={self.id} name={self.name} type={self.group_type}>"


class MenuOption(Base, TimestampMixin):
    """A single selectable option inside a MenuOptionGroup."""
    __tablename__ = "menu_options"
    __table_args__ = (
        Index("ix_menu_options_group_id", "option_group_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    option_group_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("menu_option_groups.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    price_modifier: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_available: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    display_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    group: Mapped["MenuOptionGroup"] = relationship("MenuOptionGroup", back_populates="options")

    def __repr__(self) -> str:
        return f"<MenuOption id={self.id} name={self.name} modifier={self.price_modifier}>"
