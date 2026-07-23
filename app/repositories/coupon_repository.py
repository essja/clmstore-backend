"""
CLMStore — Coupon Repository
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.coupon import Coupon, CouponUsage
from app.repositories.base import BaseRepository


class CouponRepository(BaseRepository[Coupon]):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(Coupon, db)

    async def get_by_code(self, code: str) -> Optional[Coupon]:
        result = await self.db.execute(
            select(Coupon).filter(Coupon.code == code.upper(), Coupon.is_active == True)
        )
        return result.scalars().first()

    async def get_available_coupons(self, restaurant_id: Optional[int] = None) -> List[Coupon]:
        stmt = select(Coupon).filter(
            Coupon.is_active == True,
            Coupon.expires_at > datetime.now(timezone.utc),
        )
        if restaurant_id is not None:
            # Get global coupons OR coupons specific to this restaurant
            stmt = stmt.filter(
                (Coupon.restaurant_id == None) | (Coupon.restaurant_id == restaurant_id)
            )
        else:
            stmt = stmt.filter(Coupon.restaurant_id == None)

        result = await self.db.execute(stmt)
        return list(result.scalars().all())


class CouponUsageRepository(BaseRepository[CouponUsage]):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(CouponUsage, db)

    async def count_user_usages(self, coupon_id: int, user_id: int) -> int:
        result = await self.db.execute(
            select(func.count(CouponUsage.id)).filter(
                CouponUsage.coupon_id == coupon_id,
                CouponUsage.user_id == user_id,
            )
        )
        return result.scalar() or 0
