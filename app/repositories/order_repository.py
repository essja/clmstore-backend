"""
CLMStore — Order Repository
"""
from __future__ import annotations

from typing import List, Optional

from sqlalchemy import select, and_, or_, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.order import Order, OrderItem, OrderStatusHistory
from app.repositories.base import BaseRepository
from app.utils.constants import OrderStatus


class OrderRepository(BaseRepository[Order]):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(Order, db)

    async def get_with_details(self, id: int) -> Optional[Order]:
        result = await self.db.execute(
            select(Order)
            .filter(Order.id == id)
            .options(
                selectinload(Order.items),
                selectinload(Order.status_history),
                selectinload(Order.customer),
                selectinload(Order.restaurant),
                selectinload(Order.rider),
                selectinload(Order.payment),
                selectinload(Order.delivery),
            )
        )
        return result.scalars().first()

    async def get_by_order_number(self, order_number: str) -> Optional[Order]:
        result = await self.db.execute(
            select(Order)
            .filter(Order.order_number == order_number)
            .options(
                selectinload(Order.items),
                selectinload(Order.status_history),
            )
        )
        return result.scalars().first()

    async def get_by_customer(
        self,
        user_id: int,
        status: Optional[OrderStatus] = None,
        skip: int = 0,
        limit: int = 20,
    ) -> List[Order]:
        stmt = select(Order).filter(Order.user_id == user_id)
        if status is not None:
            stmt = stmt.filter(Order.status == status)
        stmt = stmt.order_by(Order.created_at.desc()).offset(skip).limit(limit)
        stmt = stmt.options(selectinload(Order.items))

        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def count_by_customer(self, user_id: int, status: Optional[OrderStatus] = None) -> int:
        stmt = select(func.count(Order.id)).filter(Order.user_id == user_id)
        if status is not None:
            stmt = stmt.filter(Order.status == status)
        result = await self.db.execute(stmt)
        return result.scalar() or 0

    async def get_by_restaurant(
        self,
        restaurant_id: int,
        status: Optional[OrderStatus] = None,
        skip: int = 0,
        limit: int = 20,
    ) -> List[Order]:
        stmt = select(Order).filter(Order.restaurant_id == restaurant_id)
        if status is not None:
            stmt = stmt.filter(Order.status == status)
        stmt = stmt.order_by(Order.created_at.desc()).offset(skip).limit(limit)
        stmt = stmt.options(selectinload(Order.items), selectinload(Order.customer))

        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def count_by_restaurant(self, restaurant_id: int, status: Optional[OrderStatus] = None) -> int:
        stmt = select(func.count(Order.id)).filter(Order.restaurant_id == restaurant_id)
        if status is not None:
            stmt = stmt.filter(Order.status == status)
        result = await self.db.execute(stmt)
        return result.scalar() or 0

    async def list_admin_orders(
        self,
        status: Optional[OrderStatus] = None,
        restaurant_id: Optional[int] = None,
        user_id: Optional[int] = None,
        skip: int = 0,
        limit: int = 20,
    ) -> List[Order]:
        stmt = select(Order)
        if status is not None:
            stmt = stmt.filter(Order.status == status)
        if restaurant_id is not None:
            stmt = stmt.filter(Order.restaurant_id == restaurant_id)
        if user_id is not None:
            stmt = stmt.filter(Order.user_id == user_id)
        stmt = stmt.order_by(Order.created_at.desc()).offset(skip).limit(limit)

        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def count_admin_orders(
        self,
        status: Optional[OrderStatus] = None,
        restaurant_id: Optional[int] = None,
        user_id: Optional[int] = None,
    ) -> int:
        stmt = select(func.count(Order.id))
        if status is not None:
            stmt = stmt.filter(Order.status == status)
        if restaurant_id is not None:
            stmt = stmt.filter(Order.restaurant_id == restaurant_id)
        if user_id is not None:
            stmt = stmt.filter(Order.user_id == user_id)
        result = await self.db.execute(stmt)
        return result.scalar() or 0

    # ── Router-facing aliases ─────────────────────────────────────────────────

    async def get_user_orders(
        self,
        user_id: int,
        status_filter: Optional[OrderStatus] = None,
        skip: int = 0,
        limit: int = 20,
    ) -> tuple[list, int]:
        orders = await self.get_by_customer(user_id, status_filter, skip, limit)
        total = await self.count_by_customer(user_id, status_filter)
        return orders, total

    async def get_restaurant_orders(
        self,
        restaurant_id: int,
        status_filter: Optional[OrderStatus] = None,
        skip: int = 0,
        limit: int = 20,
    ) -> tuple[list, int]:
        orders = await self.get_by_restaurant(restaurant_id, status_filter, skip, limit)
        total = await self.count_by_restaurant(restaurant_id, status_filter)
        return orders, total

    async def admin_list_orders(
        self,
        status_filter: Optional[str] = None,
        restaurant_id: Optional[int] = None,
        user_id: Optional[int] = None,
        skip: int = 0,
        limit: int = 20,
    ) -> tuple[list, int]:
        status = OrderStatus(status_filter) if status_filter else None
        orders = await self.list_admin_orders(status, restaurant_id, user_id, skip, limit)
        total = await self.count_admin_orders(status, restaurant_id, user_id)
        return orders, total


class OrderItemRepository(BaseRepository[OrderItem]):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(OrderItem, db)


class OrderStatusHistoryRepository(BaseRepository[OrderStatusHistory]):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(OrderStatusHistory, db)
        
    async def get_by_order(self, order_id: int) -> List[OrderStatusHistory]:
        result = await self.db.execute(
            select(OrderStatusHistory)
            .filter(OrderStatusHistory.order_id == order_id)
            .order_by(OrderStatusHistory.created_at.asc())
        )
        return list(result.scalars().all())
