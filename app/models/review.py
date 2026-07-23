"""
CLMStore — Review Models
Tables: reviews
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    Text,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import TimestampMixin
from app.utils.constants import ReviewTargetType

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.order import Order


class Review(Base, TimestampMixin):
    __tablename__ = "reviews"
    __table_args__ = (
        Index("ix_reviews_user_id", "user_id"),
        Index("ix_reviews_order_id", "order_id"),
        Index("ix_reviews_target", "target_type", "target_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    order_id: Mapped[int] = mapped_column(Integer, ForeignKey("orders.id", ondelete="CASCADE"), nullable=False)
    target_type: Mapped[ReviewTargetType] = mapped_column(SAEnum(ReviewTargetType, name="review_target_type_enum"), nullable=False)
    target_id: Mapped[int] = mapped_column(Integer, nullable=False)  # references Restaurant, RiderProfile or MenuItem depending on target_type
    rating: Mapped[float] = mapped_column(Float, nullable=False)
    comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    images: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)  # List of URLs

    user: Mapped["User"] = relationship("User", back_populates="reviews")
    order: Mapped["Order"] = relationship("Order", back_populates="reviews")

    def __repr__(self) -> str:
        return f"<Review id={self.id} user_id={self.user_id} rating={self.rating}>"
