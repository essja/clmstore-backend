"""
CLMStore — Payment Models
Tables: payments, transactions, invoices, receipts
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
    UniqueConstraint,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import TimestampMixin
from app.utils.constants import PaymentProvider, PaymentStatus, TransactionType

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.order import Order


class Payment(Base, TimestampMixin):
    __tablename__ = "payments"
    __table_args__ = (
        Index("ix_payments_order_id", "order_id"),
        Index("ix_payments_user_id", "user_id"),
        Index("ix_payments_provider_ref", "provider_ref"),
        Index("ix_payments_status", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    order_id: Mapped[int] = mapped_column(Integer, ForeignKey("orders.id", ondelete="RESTRICT"), nullable=False)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    provider: Mapped[PaymentProvider] = mapped_column(SAEnum(PaymentProvider, name="payment_provider_enum"), nullable=False)
    provider_ref: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)  # External payment ID
    provider_response: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    currency: Mapped[str] = mapped_column(String(10), nullable=False, default="SLL")
    status: Mapped[PaymentStatus] = mapped_column(
        SAEnum(PaymentStatus, name="payment_status_enum"),
        nullable=False,
        default=PaymentStatus.PENDING,
    )
    failure_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    refunded_amount: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    metadata_: Mapped[Optional[dict]] = mapped_column("metadata", JSON, nullable=True)

    order: Mapped["Order"] = relationship("Order", back_populates="payment")
    user: Mapped["User"] = relationship("User")
    transactions: Mapped[List["Transaction"]] = relationship("Transaction", back_populates="payment", cascade="all, delete-orphan")
    invoice: Mapped[Optional["Invoice"]] = relationship("Invoice", back_populates="payment", uselist=False)
    receipt: Mapped[Optional["Receipt"]] = relationship("Receipt", back_populates="payment", uselist=False)

    def __repr__(self) -> str:
        return f"<Payment id={self.id} provider={self.provider} status={self.status}>"


class Transaction(Base, TimestampMixin):
    __tablename__ = "transactions"
    __table_args__ = (
        Index("ix_transactions_payment_id", "payment_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    payment_id: Mapped[int] = mapped_column(Integer, ForeignKey("payments.id", ondelete="CASCADE"), nullable=False)
    type: Mapped[TransactionType] = mapped_column(SAEnum(TransactionType, name="transaction_type_enum"), nullable=False)
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    currency: Mapped[str] = mapped_column(String(10), nullable=False, default="SLL")
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="completed")
    reference: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    payment: Mapped["Payment"] = relationship("Payment", back_populates="transactions")


class Invoice(Base, TimestampMixin):
    __tablename__ = "invoices"
    __table_args__ = (
        UniqueConstraint("order_id", name="uq_invoice_order"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    order_id: Mapped[int] = mapped_column(Integer, ForeignKey("orders.id", ondelete="RESTRICT"), nullable=False)
    payment_id: Mapped[int] = mapped_column(Integer, ForeignKey("payments.id", ondelete="RESTRICT"), nullable=False)
    invoice_number: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    pdf_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    order: Mapped["Order"] = relationship("Order")
    payment: Mapped["Payment"] = relationship("Payment", back_populates="invoice")


class Receipt(Base, TimestampMixin):
    __tablename__ = "receipts"
    __table_args__ = (
        UniqueConstraint("order_id", name="uq_receipt_order"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    order_id: Mapped[int] = mapped_column(Integer, ForeignKey("orders.id", ondelete="RESTRICT"), nullable=False)
    payment_id: Mapped[int] = mapped_column(Integer, ForeignKey("payments.id", ondelete="RESTRICT"), nullable=False)
    receipt_number: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    pdf_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    order: Mapped["Order"] = relationship("Order")
    payment: Mapped["Payment"] = relationship("Payment", back_populates="receipt")
