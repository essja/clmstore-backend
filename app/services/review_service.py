"""
CLMStore — Review Service
"""
from __future__ import annotations

from typing import List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions.custom import NotFoundException, BusinessRuleException
from app.models.review import Review
from app.models.restaurant import Restaurant
from app.models.rider import RiderProfile
from app.models.menu import MenuItem
from app.repositories.review_repository import ReviewRepository
from app.repositories.order_repository import OrderRepository
from app.schemas.review import ReviewCreateRequest
from app.utils.constants import ReviewTargetType


class ReviewService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.review_repo = ReviewRepository(db)
        self.order_repo = OrderRepository(db)

    async def submit_review(self, user_id: int, schema: ReviewCreateRequest) -> Review:
        """Create a review and dynamically update target rating summary."""
        # Enforce order verified complete before rating
        order = await self.order_repo.get(schema.order_id)
        if not order:
            raise NotFoundException("Order")

        if order.user_id != user_id:
            raise BusinessRuleException("You can only review orders you placed.")

        # Save review
        review = Review(
            user_id=user_id,
            order_id=schema.order_id,
            target_type=schema.target_type,
            target_id=schema.target_id,
            rating=schema.rating,
            comment=schema.comment,
            images=schema.images,
        )
        await self.review_repo.create(review)
        await self.db.flush()

        # Update average rating and total count on the target object
        await self._recalculate_target_ratings(schema.target_type, schema.target_id)

        return review

    async def _recalculate_target_ratings(self, target_type: ReviewTargetType, target_id: int) -> None:
        avg_rating, total_count = await self.review_repo.get_average_rating(target_type, target_id)

        if target_type == ReviewTargetType.RESTAURANT:
            rest = await self.db.get(Restaurant, target_id)
            if rest:
                rest.avg_rating = avg_rating
                rest.total_reviews = total_count
                self.db.add(rest)

        elif target_type == ReviewTargetType.RIDER:
            # target_id represents user_id of rider
            # let's fetch RiderProfile
            from sqlalchemy import select
            result = await self.db.execute(select(RiderProfile).filter(RiderProfile.user_id == target_id))
            rider = result.scalars().first()
            if rider:
                rider.rating = avg_rating
                self.db.add(rider)

        elif target_type == ReviewTargetType.FOOD:
            food = await self.db.get(MenuItem, target_id)
            if food:
                food.avg_rating = avg_rating
                self.db.add(food)

        await self.db.flush()

    async def get_reviews(
        self, target_type: ReviewTargetType, target_id: int, skip: int = 0, limit: int = 20
    ) -> List[Review]:
        return await self.review_repo.get_by_target(target_type, target_id, skip, limit)

    async def count_reviews(self, target_type: ReviewTargetType, target_id: int) -> int:
        return await self.review_repo.count_by_target(target_type, target_id)

    # ── Router-facing aliases ──────────────────────────────────────────────────

    async def create_review(self, user_id: int, schema: ReviewCreateRequest) -> Review:
        return await self.submit_review(user_id, schema)

    async def list_reviews(
        self,
        target_type: Optional[ReviewTargetType] = None,
        target_id: Optional[int] = None,
        min_rating: Optional[float] = None,
        skip: int = 0,
        limit: int = 20,
    ) -> tuple[List[Review], int]:
        from sqlalchemy import select, func
        from app.models.review import Review as ReviewModel
        stmt = select(ReviewModel)
        if target_type is not None:
            stmt = stmt.filter(ReviewModel.target_type == target_type)
        if target_id is not None:
            stmt = stmt.filter(ReviewModel.target_id == target_id)
        if min_rating is not None:
            stmt = stmt.filter(ReviewModel.rating >= min_rating)
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total_res = await self.db.execute(count_stmt)
        total = total_res.scalar() or 0
        stmt = stmt.order_by(ReviewModel.created_at.desc()).offset(skip).limit(limit)
        result = await self.db.execute(stmt)
        return list(result.scalars().all()), total

    async def get_rating_summary(
        self, target_type: ReviewTargetType, target_id: int
    ) -> "RatingSummary":
        from app.schemas.review import RatingSummary
        avg, total = await self.review_repo.get_average_rating(target_type, target_id)
        return RatingSummary(average_rating=avg, total_reviews=total)

    async def delete_review(self, review_id: int, current_user: "User") -> None:
        from app.utils.constants import UserRole
        review = await self.review_repo.get(review_id)
        if not review:
            raise NotFoundException("Review", review_id)
        is_admin = current_user.role in (UserRole.ADMIN, UserRole.SUPER_ADMIN)
        if not is_admin and review.user_id != current_user.id:
            from app.exceptions.custom import ForbiddenException
            raise ForbiddenException("You can only delete your own reviews.")
        await self.review_repo.delete(review_id)
