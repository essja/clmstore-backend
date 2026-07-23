"""
CLMStore — Support and Dispute Models
Tables: support_tickets, disputes
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
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
from app.utils.constants import TicketStatus, DisputeStatus

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.order import Order


class SupportTicket(Base, TimestampMixin):
    __tablename__ = "support_tickets"
    __table_args__ = (
        Index("ix_support_tickets_user_id", "user_id"),
        Index("ix_support_tickets_status", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    subject: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[TicketStatus] = mapped_column(SAEnum(TicketStatus, name="ticket_status_enum"), nullable=False, default=TicketStatus.OPEN)
    priority: Mapped[str] = mapped_column(String(20), nullable=False, default="medium")  # low, medium, high
    assigned_to: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    user: Mapped["User"] = relationship("User", foreign_keys=[user_id])
    assigned_agent: Mapped[Optional["User"]] = relationship("User", foreign_keys=[assigned_to])


class Dispute(Base, TimestampMixin):
    __tablename__ = "disputes"
    __table_args__ = (
        Index("ix_disputes_order_id", "order_id"),
        Index("ix_disputes_user_id", "user_id"),
        Index("ix_disputes_status", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    order_id: Mapped[int] = mapped_column(Integer, ForeignKey("orders.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[DisputeStatus] = mapped_column(SAEnum(DisputeStatus, name="dispute_status_enum"), nullable=False, default=DisputeStatus.OPEN)
    resolution: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    resolved_by: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    order: Mapped["Order"] = relationship("Order")
    user: Mapped["User"] = relationship("User", foreign_keys=[user_id])
    resolver: Mapped[Optional["User"]] = relationship("User", foreign_keys=[resolved_by])
