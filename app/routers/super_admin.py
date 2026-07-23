"""
CLMStore — Super Admin Router
Platform-level control: system settings, commissions, taxes, banners, promotions.
"""
from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, Path, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.auth.permissions import require_roles
from app.dependencies.pagination import PaginationParams
from app.models.user import User
from app.schemas.admin import (
    FeaturedRestaurantsUpdateRequest,
    HomepageBannerCreate,
    HomepageBannerResponse,
    SystemSettingsResponse,
    SystemSettingsUpdateRequest,
)
from app.schemas.common import MessageResponse, PaginatedResponse
from app.schemas.user import UserProfileResponse
from app.utils.constants import UserRole

router = APIRouter()

_super_admin_dep = Depends(require_roles(UserRole.SUPER_ADMIN))


# ══════════════════════════════════════════════════════════════
# SYSTEM SETTINGS
# ══════════════════════════════════════════════════════════════

@router.get(
    "/settings",
    response_model=SystemSettingsResponse,
    summary="Get platform system settings",
    dependencies=[_super_admin_dep],
)
async def get_settings(db: AsyncSession = Depends(get_db)) -> SystemSettingsResponse:
    """Returns the current platform-wide rates. Loaded from the database."""
    from app.models.system_settings import SystemSettings
    s = await SystemSettings.load(db)
    return SystemSettingsResponse.model_validate(s)


@router.patch(
    "/settings",
    response_model=SystemSettingsResponse,
    summary="Update platform system settings",
    description=(
        "Super admin adjusts platform-wide rates. "
        "Persisted to the database — takes effect immediately for all new orders without a restart."
    ),
    dependencies=[_super_admin_dep],
)
async def update_settings(
    body: SystemSettingsUpdateRequest,
    db: AsyncSession = Depends(get_db),
) -> SystemSettingsResponse:
    """
    **Request Body (all fields optional):**
    ```json
    {
        "commission_rate": 0.15,
        "service_fee": 5000.0,
        "tax_rate": 0.08,
        "default_delivery_fee": 10000.0,
        "currency_symbol": "Le",
        "currency_code": "SLL",
        "min_withdrawal_amount": 50000.0,
        "max_delivery_radius_km": 30.0
    }
    ```
    """
    from app.models.system_settings import SystemSettings
    s = await SystemSettings.load(db)
    updates = body.model_dump(exclude_unset=True)
    for field, value in updates.items():
        if hasattr(s, field):
            setattr(s, field, value)
    db.add(s)
    await db.flush()
    return SystemSettingsResponse.model_validate(s)


# ══════════════════════════════════════════════════════════════
# USER ROLES & PERMISSIONS
# ══════════════════════════════════════════════════════════════

@router.patch(
    "/users/{user_id}/role",
    response_model=UserProfileResponse,
    summary="Change user role",
    dependencies=[_super_admin_dep],
)
async def change_user_role(
    user_id: int = Path(..., ge=1),
    new_role: UserRole = Query(...),
    db: AsyncSession = Depends(get_db),
) -> UserProfileResponse:
    """
    Super admin can promote or demote any user to any role.

    **Example:** `PATCH /api/v1/super-admin/users/5/role?new_role=admin`
    """
    from app.repositories.user_repository import UserRepository
    from app.exceptions.custom import NotFoundException
    repo = UserRepository(db)
    user = await repo.get(user_id)
    if not user:
        raise NotFoundException("User", user_id)
    user.role = new_role
    db.add(user)
    return UserProfileResponse.model_validate(user)


@router.delete(
    "/users/{user_id}",
    response_model=MessageResponse,
    summary="Hard-delete a user account",
    dependencies=[_super_admin_dep],
)
async def delete_user(
    user_id: int = Path(..., ge=1),
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    """Permanently deletes a user account and all associated data. Irreversible."""
    from app.repositories.user_repository import UserRepository
    from app.exceptions.custom import NotFoundException
    repo = UserRepository(db)
    user = await repo.get(user_id)
    if not user:
        raise NotFoundException("User", user_id)
    user.soft_delete()
    db.add(user)
    return MessageResponse(message=f"User {user_id} permanently deleted.")


# ══════════════════════════════════════════════════════════════
# HOMEPAGE BANNERS
# ══════════════════════════════════════════════════════════════

@router.get(
    "/banners",
    response_model=List[HomepageBannerResponse],
    summary="List homepage banners",
    dependencies=[_super_admin_dep],
)
async def list_banners(db: AsyncSession = Depends(get_db)) -> List[HomepageBannerResponse]:
    from app.models.audit import HomepageBanner
    from sqlalchemy import select
    result = await db.execute(select(HomepageBanner).order_by(HomepageBanner.sort_order))
    banners = list(result.scalars().all())
    return [HomepageBannerResponse.model_validate(b) for b in banners]


@router.post(
    "/banners",
    response_model=HomepageBannerResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a homepage banner",
    dependencies=[_super_admin_dep],
)
async def create_banner(
    body: HomepageBannerCreate,
    db: AsyncSession = Depends(get_db),
) -> HomepageBannerResponse:
    """
    **Request Body:**
    ```json
    {
        "title": "Ramadan Special — 20% off all orders",
        "image_url": "https://cdn.clmstore.sl/banners/ramadan.jpg",
        "link_url": "/restaurants?promo=ramadan",
        "sort_order": 1
    }
    ```
    """
    from app.models.audit import HomepageBanner
    banner = HomepageBanner(**body.model_dump())
    db.add(banner)
    await db.flush()
    return HomepageBannerResponse.model_validate(banner)


@router.delete(
    "/banners/{banner_id}",
    response_model=MessageResponse,
    summary="Delete a homepage banner",
    dependencies=[_super_admin_dep],
)
async def delete_banner(
    banner_id: int = Path(..., ge=1),
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    from app.models.audit import HomepageBanner
    from app.exceptions.custom import NotFoundException
    banner = await db.get(HomepageBanner, banner_id)
    if not banner:
        raise NotFoundException("Banner", banner_id)
    await db.delete(banner)
    return MessageResponse(message="Banner deleted.")


# ══════════════════════════════════════════════════════════════
# FEATURED RESTAURANTS
# ══════════════════════════════════════════════════════════════

@router.put(
    "/featured-restaurants",
    response_model=MessageResponse,
    summary="Set featured restaurants (shown on homepage)",
    dependencies=[_super_admin_dep],
)
async def set_featured_restaurants(
    body: FeaturedRestaurantsUpdateRequest,
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    """
    **Request Body:**
    ```json
    {"restaurant_ids": [1, 4, 7, 12]}
    ```
    Replaces the current featured restaurant list.
    """
    from app.repositories.restaurant_repository import RestaurantRepository
    repo = RestaurantRepository(db)
    await repo.set_featured_restaurants(body.restaurant_ids)
    return MessageResponse(message=f"Featured restaurants updated ({len(body.restaurant_ids)} restaurants).")


# ══════════════════════════════════════════════════════════════
# PLATFORM ANALYTICS
# ══════════════════════════════════════════════════════════════

@router.get(
    "/analytics/revenue",
    summary="Platform revenue analytics",
    dependencies=[_super_admin_dep],
)
async def revenue_analytics(
    period: str = Query(default="month", description="today | week | month | year"),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    **Response:**
    ```json
    {
        "gross_revenue": 284350000.0,
        "platform_commission": 28435000.0,
        "service_fees_collected": 14217500.0,
        "tax_collected": 42652500.0,
        "net_payable_to_restaurants": 199045000.0,
        "period": "month",
        "currency": "SLL"
    }
    ```
    """
    from app.services.analytics_service import AnalyticsService
    service = AnalyticsService(db)
    return await service.get_revenue_analytics(period)


@router.get(
    "/analytics/orders",
    summary="Platform order analytics",
    dependencies=[_super_admin_dep],
)
async def order_analytics(
    period: str = Query(default="month"),
    db: AsyncSession = Depends(get_db),
) -> dict:
    from app.services.analytics_service import AnalyticsService
    service = AnalyticsService(db)
    return await service.get_order_analytics(period)


@router.get(
    "/analytics/top-restaurants",
    summary="Top performing restaurants",
    dependencies=[_super_admin_dep],
)
async def top_restaurants(
    limit: int = Query(default=10, ge=1, le=50),
    period: str = Query(default="month"),
    db: AsyncSession = Depends(get_db),
) -> dict:
    from app.services.analytics_service import AnalyticsService
    service = AnalyticsService(db)
    return await service.get_top_restaurants(limit=limit, period=period)


@router.get(
    "/analytics/top-riders",
    summary="Top performing riders",
    dependencies=[_super_admin_dep],
)
async def top_riders(
    limit: int = Query(default=10, ge=1, le=50),
    period: str = Query(default="month"),
    db: AsyncSession = Depends(get_db),
) -> dict:
    from app.services.analytics_service import AnalyticsService
    service = AnalyticsService(db)
    return await service.get_top_riders(limit=limit, period=period)


# ══════════════════════════════════════════════════════════════
# AUDIT LOGS
# ══════════════════════════════════════════════════════════════

@router.get(
    "/audit-logs",
    summary="View platform audit logs",
    dependencies=[_super_admin_dep],
)
async def audit_logs(
    user_id: Optional[int] = Query(default=None),
    action: Optional[str] = Query(default=None),
    pagination: PaginationParams = Depends(),
    db: AsyncSession = Depends(get_db),
) -> dict:
    from app.models.audit import AuditLog
    from sqlalchemy import select, func
    query = select(AuditLog)
    if user_id:
        query = query.filter(AuditLog.user_id == user_id)
    if action:
        query = query.filter(AuditLog.action.ilike(f"%{action}%"))
    count_q = select(func.count()).select_from(query.subquery())
    total_res = await db.execute(count_q)
    total = total_res.scalar() or 0
    result = await db.execute(query.order_by(AuditLog.created_at.desc()).offset(pagination.skip).limit(pagination.limit))
    logs = list(result.scalars().all())
    return {
        "data": [
            {
                "id": log.id,
                "user_id": log.user_id,
                "action": log.action,
                "resource_type": log.resource_type,
                "resource_id": log.resource_id,
                "details": log.new_value or log.old_value,
                "ip_address": log.ip_address,
                "created_at": log.created_at.isoformat(),
            }
            for log in logs
        ],
        "total": total,
    }
