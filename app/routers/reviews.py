"""
CLMStore — Reviews & Ratings Router
"""
from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, Path, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies.auth import get_current_active_user
from app.dependencies.pagination import PaginationParams
from app.models.user import User
from app.schemas.common import MessageResponse, PaginatedResponse
from app.schemas.review import RatingSummary, ReviewCreateRequest, ReviewResponse
from app.services.review_service import ReviewService
from app.utils.constants import ReviewTargetType

router = APIRouter()


# ── POST /api/v1/reviews ─────────────────────────────────────────────────────
@router.post(
    "",
    response_model=ReviewResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit a review",
    description=(
        "Customers can leave reviews for restaurants, specific food items, or riders. "
        "A review is only allowed once per completed order per target."
    ),
)
async def create_review(
    body: ReviewCreateRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> ReviewResponse:
    """
    **Request Body:**
    ```json
    {
        "order_id": 15,
        "target_type": "restaurant",
        "target_id": 3,
        "rating": 4.5,
        "comment": "Amazing jollof rice! Fast delivery.",
        "images": ["https://cdn.clmstore.sl/reviews/img1.jpg"]
    }
    ```

    **Target Types:** `restaurant` | `food` | `rider`
    """
    service = ReviewService(db)
    review = await service.create_review(current_user.id, body)
    return ReviewResponse.model_validate(review)


# ── GET /api/v1/reviews ───────────────────────────────────────────────────────
@router.get(
    "",
    response_model=PaginatedResponse[ReviewResponse],
    summary="List reviews with filters",
)
async def list_reviews(
    target_type: Optional[ReviewTargetType] = Query(default=None),
    target_id: Optional[int] = Query(default=None),
    min_rating: Optional[float] = Query(default=None, ge=1.0, le=5.0),
    pagination: PaginationParams = Depends(),
    db: AsyncSession = Depends(get_db),
) -> PaginatedResponse[ReviewResponse]:
    """
    **Examples:**
    - `GET /api/v1/reviews?target_type=restaurant&target_id=3` — Restaurant reviews
    - `GET /api/v1/reviews?target_type=rider&target_id=7&min_rating=4` — Rider reviews ≥ 4 stars
    """
    service = ReviewService(db)
    reviews, total = await service.list_reviews(
        target_type=target_type,
        target_id=target_id,
        min_rating=min_rating,
        skip=pagination.skip,
        limit=pagination.limit,
    )
    return PaginatedResponse(
        data=[ReviewResponse.model_validate(r) for r in reviews],
        pagination=pagination.meta(total),
    )


# ── GET /api/v1/reviews/restaurants/{restaurant_id} ──────────────────────────
@router.get(
    "/restaurants/{restaurant_id}",
    response_model=PaginatedResponse[ReviewResponse],
    summary="Get restaurant reviews",
)
async def restaurant_reviews(
    restaurant_id: int = Path(..., ge=1),
    pagination: PaginationParams = Depends(),
    db: AsyncSession = Depends(get_db),
) -> PaginatedResponse[ReviewResponse]:
    service = ReviewService(db)
    reviews, total = await service.list_reviews(
        target_type=ReviewTargetType.RESTAURANT,
        target_id=restaurant_id,
        skip=pagination.skip,
        limit=pagination.limit,
    )
    return PaginatedResponse(
        data=[ReviewResponse.model_validate(r) for r in reviews],
        pagination=pagination.meta(total),
    )


# ── GET /api/v1/reviews/restaurants/{restaurant_id}/rating ───────────────────
@router.get(
    "/restaurants/{restaurant_id}/rating",
    response_model=RatingSummary,
    summary="Get restaurant average rating",
)
async def restaurant_rating(
    restaurant_id: int = Path(..., ge=1),
    db: AsyncSession = Depends(get_db),
) -> RatingSummary:
    service = ReviewService(db)
    return await service.get_rating_summary(ReviewTargetType.RESTAURANT, restaurant_id)


# ── GET /api/v1/reviews/food/{menu_item_id} ──────────────────────────────────
@router.get(
    "/food/{menu_item_id}",
    response_model=PaginatedResponse[ReviewResponse],
    summary="Get food item reviews",
)
async def food_reviews(
    menu_item_id: int = Path(..., ge=1),
    pagination: PaginationParams = Depends(),
    db: AsyncSession = Depends(get_db),
) -> PaginatedResponse[ReviewResponse]:
    service = ReviewService(db)
    reviews, total = await service.list_reviews(
        target_type=ReviewTargetType.FOOD,
        target_id=menu_item_id,
        skip=pagination.skip,
        limit=pagination.limit,
    )
    return PaginatedResponse(
        data=[ReviewResponse.model_validate(r) for r in reviews],
        pagination=pagination.meta(total),
    )


# ── GET /api/v1/reviews/riders/{rider_id} ────────────────────────────────────
@router.get(
    "/riders/{rider_id}",
    response_model=PaginatedResponse[ReviewResponse],
    summary="Get rider reviews",
)
async def rider_reviews(
    rider_id: int = Path(..., ge=1),
    pagination: PaginationParams = Depends(),
    db: AsyncSession = Depends(get_db),
) -> PaginatedResponse[ReviewResponse]:
    service = ReviewService(db)
    reviews, total = await service.list_reviews(
        target_type=ReviewTargetType.RIDER,
        target_id=rider_id,
        skip=pagination.skip,
        limit=pagination.limit,
    )
    return PaginatedResponse(
        data=[ReviewResponse.model_validate(r) for r in reviews],
        pagination=pagination.meta(total),
    )


# ── GET /api/v1/reviews/{review_id} ──────────────────────────────────────────
@router.get(
    "/{review_id}",
    response_model=ReviewResponse,
    summary="Get a single review",
)
async def get_review(
    review_id: int = Path(..., ge=1),
    db: AsyncSession = Depends(get_db),
) -> ReviewResponse:
    from app.repositories.review_repository import ReviewRepository
    from app.exceptions.custom import NotFoundException
    repo = ReviewRepository(db)
    review = await repo.get(review_id)
    if not review:
        raise NotFoundException("Review", review_id)
    return ReviewResponse.model_validate(review)


# ── DELETE /api/v1/reviews/{review_id} ───────────────────────────────────────
@router.delete(
    "/{review_id}",
    response_model=MessageResponse,
    summary="Delete a review (owner or admin)",
)
async def delete_review(
    review_id: int = Path(..., ge=1),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    service = ReviewService(db)
    await service.delete_review(review_id, current_user)
    return MessageResponse(message="Review removed successfully.")
