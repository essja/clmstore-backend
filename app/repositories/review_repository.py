"""
CLMStore — Review Repository
"""
from __future__ import annotations

from typing import List, Optional, Tuple

from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.review import Review
from app.repositories.base import BaseRepository
from app.utils.constants import ReviewTargetType


class ReviewRepository(BaseRepository[Review]):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(Review, db)

    async def get_by_target(
        self,
        target_type: ReviewTargetType,
        target_id: int,
        skip: int = 0,
        limit: int = 20,
    ) -> List[Review]:
        result = await self.db.execute(
            select(Review)
            .filter(
                Review.target_type == target_type,
                Review.target_id == target_id,
            )
            .order_by(Review.created_at.desc())
            .offset(skip)
            .limit(limit)
            .options(selectinload(Review.user))
        )
        return list(result.scalars().all())

    async def count_by_target(self, target_type: ReviewTargetType, target_id: int) -> int:
        result = await self.db.execute(
            select(func.count(Review.id)).filter(
                Review.target_type == target_type,
                Review.target_id == target_id,
            )
        )
        return result.scalar() or 0

    async def get_average_rating(self, target_type: ReviewTargetType, target_id: int) -> Tuple[float, int]:
        """Return (average_rating, total_count) for target."""
        result = await self.db.execute(
            select(
                func.avg(Review.rating),
                func.count(Review.id),
            ).filter(
                Review.target_type == target_type,
                Review.target_id == target_id,
            )
        )
        row = result.first()
        if row and row[0] is not None:
            return round(float(row[0]), 2), int(row[1])
        return 0.0, 0
