"""
CLMStore — Rider Repository
"""
from __future__ import annotations

from typing import List, Optional

from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.rider import RiderProfile, RiderDocument, RiderEarning, RiderWithdrawal
from app.repositories.base import BaseRepository


class RiderProfileRepository(BaseRepository[RiderProfile]):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(RiderProfile, db)

    async def get_by_user(self, user_id: int) -> Optional[RiderProfile]:
        result = await self.db.execute(
            select(RiderProfile)
            .filter(RiderProfile.user_id == user_id)
            .options(
                selectinload(RiderProfile.documents),
                selectinload(RiderProfile.user),
            )
        )
        return result.scalars().first()

    async def get_available_riders(self) -> List[RiderProfile]:
        result = await self.db.execute(
            select(RiderProfile)
            .filter(RiderProfile.is_available == True, RiderProfile.is_verified == True)
            .options(selectinload(RiderProfile.user))
        )
        return list(result.scalars().all())


class RiderDocumentRepository(BaseRepository[RiderDocument]):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(RiderDocument, db)

    async def get_by_rider(self, rider_id: int) -> List[RiderDocument]:
        result = await self.db.execute(
            select(RiderDocument).filter(RiderDocument.rider_id == rider_id)
        )
        return list(result.scalars().all())


class RiderEarningRepository(BaseRepository[RiderEarning]):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(RiderEarning, db)

    async def get_by_rider(self, rider_id: int) -> List[RiderEarning]:
        result = await self.db.execute(
            select(RiderEarning)
            .filter(RiderEarning.rider_id == rider_id)
            .order_by(RiderEarning.created_at.desc())
        )
        return list(result.scalars().all())


class RiderWithdrawalRepository(BaseRepository[RiderWithdrawal]):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(RiderWithdrawal, db)

    async def get_by_rider(self, rider_id: int) -> List[RiderWithdrawal]:
        result = await self.db.execute(
            select(RiderWithdrawal)
            .filter(RiderWithdrawal.rider_id == rider_id)
            .order_by(RiderWithdrawal.created_at.desc())
        )
        return list(result.scalars().all())

    async def list_all(
        self,
        status: Optional[str] = None,
        skip: int = 0,
        limit: int = 20,
    ) -> tuple[list, int]:
        stmt = select(RiderWithdrawal)
        if status:
            stmt = stmt.filter(RiderWithdrawal.status == status)
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total_res = await self.db.execute(count_stmt)
        total = total_res.scalar() or 0
        stmt = stmt.order_by(RiderWithdrawal.created_at.desc()).offset(skip).limit(limit)
        result = await self.db.execute(stmt)
        return list(result.scalars().all()), total


class RiderRepository(RiderProfileRepository):
    """Admin-facing alias that adds search and lookup-by-user-id."""

    async def get_by_user_id(self, user_id: int) -> Optional[RiderProfile]:
        return await self.get_by_user(user_id)

    async def search_riders(
        self,
        is_verified: Optional[bool] = None,
        is_available: Optional[bool] = None,
        skip: int = 0,
        limit: int = 20,
    ) -> tuple[list, int]:
        stmt = select(RiderProfile)
        if is_verified is not None:
            stmt = stmt.filter(RiderProfile.is_verified == is_verified)
        if is_available is not None:
            stmt = stmt.filter(RiderProfile.is_available == is_available)
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total_res = await self.db.execute(count_stmt)
        total = total_res.scalar() or 0
        stmt = stmt.order_by(RiderProfile.created_at.desc()).offset(skip).limit(limit)
        result = await self.db.execute(stmt)
        return list(result.scalars().all()), total
