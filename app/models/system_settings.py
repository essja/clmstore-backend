"""
CLMStore — System Settings Model
Single-row table the super admin edits via the dashboard.
Values override the .env defaults for every new order.
"""
from __future__ import annotations

from sqlalchemy import Boolean, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.base import TimestampMixin


class SystemSettings(Base, TimestampMixin):
    """
    Always contains exactly ONE row (id=1).
    Use SystemSettings.load(db) to fetch it; it creates the row on first call.
    """
    __tablename__ = "system_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)

    # Financial rates
    commission_rate: Mapped[float] = mapped_column(Float, nullable=False, default=0.15)
    service_fee: Mapped[float] = mapped_column(Float, nullable=False, default=5000.0)   # flat SLL
    tax_rate: Mapped[float] = mapped_column(Float, nullable=False, default=0.08)

    # Delivery defaults
    default_delivery_fee: Mapped[float] = mapped_column(Float, nullable=False, default=10000.0)  # flat SLL
    max_delivery_radius_km: Mapped[float] = mapped_column(Float, nullable=False, default=30.0)

    # Platform config
    currency_symbol: Mapped[str] = mapped_column(String(10), nullable=False, default="Le")
    currency_code: Mapped[str] = mapped_column(String(10), nullable=False, default="SLL")
    min_withdrawal_amount: Mapped[float] = mapped_column(Float, nullable=False, default=50000.0)
    platform_name: Mapped[str] = mapped_column(String(100), nullable=False, default="CLMStore")

    @classmethod
    async def load(cls, db) -> "SystemSettings":
        """
        Fetch the single settings row, creating it with defaults if it doesn't exist yet.
        Always use this instead of db.get(SystemSettings, 1).
        """
        from sqlalchemy import select
        result = await db.execute(select(cls).where(cls.id == 1))
        settings = result.scalars().first()
        if settings is None:
            settings = cls(id=1)
            db.add(settings)
            await db.flush()
        return settings
