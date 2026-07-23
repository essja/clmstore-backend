"""
CLMStore — Notification Repository
"""
from __future__ import annotations

from typing import List, Optional

from sqlalchemy import select, and_, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notification import Notification
from app.repositories.base import BaseRepository


class NotificationRepository(BaseRepository[Notification]):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(Notification, db)

    async def get_by_user(
        self,
        user_id: int,
        only_unread: bool = False,
        skip: int = 0,
        limit: int = 50,
    ) -> List[Notification]:
        stmt = select(Notification).filter(Notification.user_id == user_id)
        if only_unread:
            stmt = stmt.filter(Notification.is_read == False)
        stmt = stmt.order_by(Notification.created_at.desc()).offset(skip).limit(limit)

        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def mark_all_as_read(self, user_id: int) -> None:
        await self.db.execute(
            update(Notification)
            .where(Notification.user_id == user_id, Notification.is_read == False)
            .values(is_read=True)
        )
        await self.db.flush()
