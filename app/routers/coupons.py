"""
CLMStore — Coupons Router
Manages coupon CRUD, validation, and usage tracking.
"""
from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, Path, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies.auth import get_current_active_user
from app.dependencies.pagination import PaginationParams
from app.exceptions.custom import ForbiddenException
from app.models.user import User
from app.schemas.common import MessageResponse, PaginatedResponse
from app.schemas.coupon import (
    CouponCreate,
    CouponResponse,
    CouponUpdate,
    CouponValidateRequest,
)
from app.services.coupon_service import CouponService
from app.utils.constants import UserRole

router = APIRouter()


def _require_admin(user: User) -> None:
    if user.role not in (UserRole.ADMIN, UserRole.SUPER_ADMIN, UserRole.RESTAURANT_OWNER):
        raise ForbiddenException("Admin or restaurant owner access required.")


# ── GET /api/v1/coupons ───────────────────────────────────────────────────────
@router.get(
    "",
    response_model=PaginatedResponse[CouponResponse],
    summary="List all coupons (admin)",
)
async def list_coupons(
    restaurant_id: Optional[int] = Query(default=None, description="Filter by restaurant (null = global)"),
    is_active: Optional[bool] = Query(default=None),
    pagination: PaginationParams = Depends(),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> PaginatedResponse[CouponResponse]:
    _require_admin(current_user)
    service = CouponService(db)
    coupons, total = await service.list_coupons(
        restaurant_id=restaurant_id,
        is_active=is_active,
        skip=pagination.skip,
        limit=pagination.limit,
    )
    return PaginatedResponse(
        data=[CouponResponse.model_validate(c) for c in coupons],
        pagination=pagination.meta(total),
    )


# ── POST /api/v1/coupons ──────────────────────────────────────────────────────
@router.post(
    "",
    response_model=CouponResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a coupon",
)
async def create_coupon(
    body: CouponCreate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> CouponResponse:
    """
    **Request Body (Percentage Coupon):**
    ```json
    {
        "code": "SAVE20",
        "type": "percentage",
        "value": 20.0,
        "min_order_value": 30000.0,
        "max_discount": 15000.0,
        "restaurant_id": null,
        "expires_at": "2024-12-31T23:59:59Z",
        "usage_limit": 100,
        "user_usage_limit": 1,
        "is_active": true
    }
    ```

    **Request Body (Fixed Coupon):**
    ```json
    {
        "code": "FLAT5000",
        "type": "fixed",
        "value": 5000.0,
        "min_order_value": 25000.0,
        "expires_at": "2024-12-31T23:59:59Z"
    }
    ```
    """
    _require_admin(current_user)
    service = CouponService(db)
    coupon = await service.create_coupon(body)
    return CouponResponse.model_validate(coupon)


# ── GET /api/v1/coupons/{coupon_id} ──────────────────────────────────────────
@router.get(
    "/{coupon_id}",
    response_model=CouponResponse,
    summary="Get coupon by ID",
)
async def get_coupon(
    coupon_id: int = Path(..., ge=1),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> CouponResponse:
    _require_admin(current_user)
    from app.repositories.coupon_repository import CouponRepository
    from app.exceptions.custom import NotFoundException
    repo = CouponRepository(db)
    coupon = await repo.get(coupon_id)
    if not coupon:
        raise NotFoundException("Coupon", coupon_id)
    return CouponResponse.model_validate(coupon)


# ── PATCH /api/v1/coupons/{coupon_id} ────────────────────────────────────────
@router.patch(
    "/{coupon_id}",
    response_model=CouponResponse,
    summary="Update a coupon",
)
async def update_coupon(
    coupon_id: int = Path(..., ge=1),
    body: CouponUpdate = ...,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> CouponResponse:
    _require_admin(current_user)
    service = CouponService(db)
    coupon = await service.update_coupon(coupon_id, body)
    return CouponResponse.model_validate(coupon)


# ── DELETE /api/v1/coupons/{coupon_id} ───────────────────────────────────────
@router.delete(
    "/{coupon_id}",
    response_model=MessageResponse,
    summary="Deactivate / delete a coupon",
)
async def delete_coupon(
    coupon_id: int = Path(..., ge=1),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    _require_admin(current_user)
    service = CouponService(db)
    await service.deactivate_coupon(coupon_id)
    return MessageResponse(message="Coupon deactivated successfully.")


# ── POST /api/v1/coupons/validate ────────────────────────────────────────────
@router.post(
    "/validate",
    summary="Validate a coupon code before checkout",
    description=(
        "Checks whether a coupon code is valid for the given restaurant and order subtotal. "
        "Returns the discount amount if valid."
    ),
)
async def validate_coupon(
    body: CouponValidateRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    **Request Body:**
    ```json
    {
        "code": "SAVE20",
        "order_subtotal": 70000.0,
        "restaurant_id": 3
    }
    ```

    **Response:**
    ```json
    {
        "valid": true,
        "coupon_code": "SAVE20",
        "discount_type": "percentage",
        "discount_value": 20.0,
        "discount_amount": 14000.0,
        "max_discount": 15000.0
    }
    ```
    """
    service = CouponService(db)
    coupon = await service.validate_coupon(
        code=body.code,
        user_id=current_user.id,
        restaurant_id=body.restaurant_id,
        order_subtotal=body.order_subtotal,
    )
    type_val = coupon.type.value if hasattr(coupon.type, "value") else str(coupon.type)
    if type_val == "percentage":
        discount_amount = body.order_subtotal * (coupon.value / 100)
        if coupon.max_discount:
            discount_amount = min(discount_amount, float(coupon.max_discount))
    else:
        discount_amount = min(float(coupon.value), body.order_subtotal)
    return {
        "valid": True,
        "coupon_code": coupon.code,
        "discount_type": type_val,
        "discount_value": float(coupon.value),
        "discount_amount": discount_amount,
        "max_discount": float(coupon.max_discount) if coupon.max_discount else None,
    }
