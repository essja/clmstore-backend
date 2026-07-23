"""
CLMStore — Coupon Service
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions.custom import NotFoundException, BusinessRuleException
from app.models.coupon import Coupon
from app.repositories.coupon_repository import CouponRepository, CouponUsageRepository
from app.schemas.coupon import CouponCreate, CouponUpdate


class CouponService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.coupon_repo = CouponRepository(db)
        self.usage_repo = CouponUsageRepository(db)

    async def create_coupon(self, schema: CouponCreate) -> Coupon:
        coupon = Coupon(
            code=schema.code.upper(),
            type=schema.type,
            value=schema.value,
            min_order_value=schema.min_order_value,
            max_discount=schema.max_discount,
            restaurant_id=schema.restaurant_id,
            expires_at=schema.expires_at,
            usage_limit=schema.usage_limit,
            user_usage_limit=schema.user_usage_limit,
            is_active=schema.is_active,
        )
        return await self.coupon_repo.create(coupon)

    async def update_coupon(self, coupon_id: int, schema: CouponUpdate) -> Coupon:
        coupon = await self.coupon_repo.get(coupon_id)
        if not coupon:
            raise NotFoundException("Coupon")
        return await self.coupon_repo.update(coupon, schema)

    async def delete_coupon(self, coupon_id: int) -> None:
        await self.coupon_repo.delete(coupon_id)

    async def get_coupon(self, coupon_id: int) -> Coupon:
        coupon = await self.coupon_repo.get(coupon_id)
        if not coupon:
            raise NotFoundException("Coupon")
        return coupon

    async def get_available_coupons(self, restaurant_id: Optional[int] = None) -> List[Coupon]:
        return await self.coupon_repo.get_available_coupons(restaurant_id)

    async def list_coupons(
        self,
        restaurant_id: Optional[int] = None,
        is_active: Optional[bool] = None,
        skip: int = 0,
        limit: int = 20,
    ) -> tuple[list, int]:
        from sqlalchemy import select, func
        from app.models.coupon import Coupon as CouponModel
        stmt = select(CouponModel)
        if restaurant_id is not None:
            stmt = stmt.filter(CouponModel.restaurant_id == restaurant_id)
        if is_active is not None:
            stmt = stmt.filter(CouponModel.is_active == is_active)
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total_res = await self.db.execute(count_stmt)
        total = total_res.scalar() or 0
        stmt = stmt.order_by(CouponModel.created_at.desc()).offset(skip).limit(limit)
        result = await self.db.execute(stmt)
        return list(result.scalars().all()), total

    async def deactivate_coupon(self, coupon_id: int) -> None:
        coupon = await self.coupon_repo.get(coupon_id)
        if not coupon:
            raise NotFoundException("Coupon")
        coupon.is_active = False
        self.db.add(coupon)

    async def validate_coupon(self, code: str, user_id: int, order_subtotal: float, restaurant_id: int) -> Coupon:
        coupon = await self.coupon_repo.get_by_code(code)
        if not coupon:
            raise NotFoundException("Coupon")

        if not coupon.is_active:
            raise BusinessRuleException("Coupon is not active")

        # Expiry Check
        if coupon.expires_at < datetime.now(timezone.utc):
            raise BusinessRuleException("Coupon has expired")

        # Min order check
        if order_subtotal < coupon.min_order_value:
            raise BusinessRuleException(
                f"Minimum order subtotal of Le {coupon.min_order_value:,.0f} required"
            )

        # Restaurant constraint check
        if coupon.restaurant_id is not None and coupon.restaurant_id != restaurant_id:
            raise BusinessRuleException("Coupon is not valid for this restaurant's items")

        # Global usage limits check
        if coupon.usage_limit is not None and coupon.used_count >= coupon.usage_limit:
            raise BusinessRuleException("Coupon usage limit reached")

        # Per user usage limits check
        user_usage_count = await self.usage_repo.count_user_usages(coupon.id, user_id)
        if user_usage_count >= coupon.user_usage_limit:
            raise BusinessRuleException(
                f"You have reached the usage limit for this coupon ({coupon.user_usage_limit} time(s))"
            )

        return coupon
