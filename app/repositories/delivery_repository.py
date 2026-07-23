"""
CLMStore — Delivery Repository
"""
from __future__ import annotations

from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.delivery import Delivery, RiderLocation
from app.repositories.base import BaseRepository
from app.utils.constants import DeliveryStatus


class DeliveryRepository(BaseRepository[Delivery]):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(Delivery, db)

    async def get_by_order(self, order_id: int) -> Optional[Delivery]:
        result = await self.db.execute(select(Delivery).filter(Delivery.order_id == order_id))
        return result.scalars().first()

    async def get_by_order_id(self, order_id: int) -> Optional[Delivery]:
        return await self.get_by_order(order_id)

    async def get_active_deliveries_for_rider(self, rider_id: int) -> List[Delivery]:
        result = await self.db.execute(
            select(Delivery).filter(
                Delivery.rider_id == rider_id,
                Delivery.status.in_(
                    [
                        DeliveryStatus.ASSIGNED,
                        DeliveryStatus.ACCEPTED,
                        DeliveryStatus.PICKING_UP,
                        DeliveryStatus.PICKED_UP,
                        DeliveryStatus.ON_THE_WAY,
                    ]
                ),
            )
        )
        return list(result.scalars().all())


class RiderLocationRepository(BaseRepository[RiderLocation]):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(RiderLocation, db)

    async def get_by_rider(self, rider_id: int) -> Optional[RiderLocation]:
        result = await self.db.execute(
            select(RiderLocation).filter(RiderLocation.rider_id == rider_id)
        )
        return result.scalars().first()
