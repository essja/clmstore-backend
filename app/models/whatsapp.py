"""
CLMStore — WhatsApp Bot Models
Tables: whatsapp_customers, whatsapp_sessions
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional, Any, List, Dict

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import TimestampMixin


class WhatsAppSessionState(str, Enum):
    WELCOME = "welcome"
    AWAITING_NAME = "awaiting_name"
    MAIN_MENU = "main_menu"
    SELECT_RESTAURANT = "select_restaurant"
    SELECT_MENU_ITEM = "select_menu_item"
    CART_VIEW = "cart_view"
    ENTER_ADDRESS = "enter_address"
    SELECT_PAYMENT = "select_payment"
    AWAITING_PAYMENT = "awaiting_payment"
    TRACKING = "tracking"
    SUPPORT = "support"


class WhatsAppCustomer(Base, TimestampMixin):
    __tablename__ = "whatsapp_customers"
    __table_args__ = (
        Index("ix_whatsapp_customers_number", "whatsapp_number", unique=True),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    whatsapp_number: Mapped[str] = mapped_column(String(32), nullable=False, unique=True, index=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    user_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    default_address: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    default_latitude: Mapped[Optional[float]] = mapped_column(nullable=True)
    default_longitude: Mapped[Optional[float]] = mapped_column(nullable=True)
    last_active: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now(), onupdate=func.now())

    user: Mapped[Optional[Any]] = relationship("User", foreign_keys=[user_id])


class WhatsAppSession(Base, TimestampMixin):
    __tablename__ = "whatsapp_sessions"
    __table_args__ = (
        Index("ix_whatsapp_sessions_number", "whatsapp_number", unique=True),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    whatsapp_number: Mapped[str] = mapped_column(String(32), nullable=False, unique=True, index=True)
    customer_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("whatsapp_customers.id", ondelete="CASCADE"), nullable=True)
    current_state: Mapped[WhatsAppSessionState] = mapped_column(
        SAEnum(WhatsAppSessionState, name="whatsapp_session_state_enum", native_enum=False),
        default=WhatsAppSessionState.WELCOME,
        nullable=False
    )
    selected_restaurant_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    cart_items: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict) # {"items": [{menu_item_id, name, price, quantity}]}
    delivery_address: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    last_order_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    last_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    customer: Mapped[Optional[WhatsAppCustomer]] = relationship("WhatsAppCustomer", foreign_keys=[customer_id])
