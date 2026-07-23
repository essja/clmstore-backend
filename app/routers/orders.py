"""
CLMStore — Orders Router
Handles order creation, status tracking, status transitions, and order history.
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
from app.schemas.order import (
    OrderAssignRiderRequest,
    OrderCancelRequest,
    OrderCreateRequest,
    OrderRejectRequest,
    OrderResponse,
)
from app.services.order_service import OrderService
from app.utils.constants import OrderStatus, UserRole

router = APIRouter()


# ── POST /api/v1/orders ───────────────────────────────────────────────────────
@router.post(
    "",
    response_model=OrderResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Place an order from the active cart",
    description=(
        "Converts the authenticated user's active cart into a pending order. "
        "Calculates totals, applies coupons, and notifies the restaurant."
    ),
)
async def place_order(
    body: OrderCreateRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> OrderResponse:
    """
    **Request Body:**
    ```json
    {
        "delivery_address_id": 3,
        "payment_method": "orange_money",
        "notes": "Extra spicy please"
    }
    ```

    **Payment Methods:** `cash` | `orange_money` | `afrimoney` | `stripe` | `paypal` | `visa` | `mastercard`

    **Response:** Full order details with calculated totals and order number.
    """
    service = OrderService(db)
    order = await service.checkout_cart(current_user.id, body)
    return OrderResponse.model_validate(order)


# ── GET /api/v1/orders ────────────────────────────────────────────────────────
@router.get(
    "",
    response_model=PaginatedResponse[OrderResponse],
    summary="List user's order history",
    description="Returns a paginated list of orders for the current user, sorted by date.",
)
async def list_orders(
    status_filter: Optional[OrderStatus] = Query(default=None, alias="status"),
    pagination: PaginationParams = Depends(),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> PaginatedResponse[OrderResponse]:
    """
    **Query Params:**
    - `status`: Filter by order status (pending | accepted | preparing | ready | picked_up | on_the_way | delivered | cancelled | refunded)
    - `page`, `per_page`: Pagination
    """
    from app.repositories.order_repository import OrderRepository
    repo = OrderRepository(db)
    orders, total = await repo.get_user_orders(
        user_id=current_user.id,
        status_filter=status_filter,
        skip=pagination.skip,
        limit=pagination.limit,
    )
    return PaginatedResponse(
        data=[OrderResponse.model_validate(o) for o in orders],
        pagination=pagination.meta(total),
    )


# ── GET /api/v1/orders/{order_id} ────────────────────────────────────────────
@router.get(
    "/{order_id}",
    response_model=OrderResponse,
    summary="Get order details",
)
async def get_order(
    order_id: int = Path(..., ge=1),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> OrderResponse:
    """Returns full order details including items, status history, and restaurant info."""
    from app.repositories.order_repository import OrderRepository
    from app.exceptions.custom import NotFoundException, ForbiddenException
    repo = OrderRepository(db)
    order = await repo.get_with_details(order_id)
    if not order:
        raise NotFoundException("Order", order_id)
    if current_user.role not in (UserRole.ADMIN, UserRole.SUPER_ADMIN):
        if order.user_id != current_user.id and order.restaurant.owner_id != current_user.id:
            raise ForbiddenException("You do not have access to this order.")
    return OrderResponse.model_validate(order)


# ── GET /api/v1/orders/{order_id}/track ───────────────────────────────────────
@router.get(
    "/{order_id}/track",
    summary="Track order in real time",
    description="Returns current status, rider location (if assigned), and ETA.",
)
async def track_order(
    order_id: int = Path(..., ge=1),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    **Response:**
    ```json
    {
        "order_number": "CLM-20240615-123456",
        "status": "on_the_way",
        "rider": {
            "name": "Ibrahim Kamara",
            "phone": "+23276999888",
            "latitude": 8.4701,
            "longitude": -13.2345,
            "eta_minutes": 12
        },
        "estimated_delivery_at": "2024-06-15T14:35:00Z"
    }
    ```
    """
    from app.repositories.order_repository import OrderRepository
    from app.models.delivery import RiderLocation
    from app.exceptions.custom import NotFoundException, ForbiddenException
    repo = OrderRepository(db)
    order = await repo.get_with_details(order_id)
    if not order:
        raise NotFoundException("Order", order_id)
    if current_user.id != order.user_id and current_user.role not in (UserRole.ADMIN, UserRole.SUPER_ADMIN):
        raise ForbiddenException()

    response: dict = {
        "order_id": order.id,
        "order_number": order.order_number,
        "status": order.status.value,
        "estimated_delivery_min": order.estimated_delivery_min,
    }

    if order.rider_id:
        from sqlalchemy import select
        result = await db.execute(
            select(RiderLocation).filter(RiderLocation.rider_id == order.rider_id)
        )
        rider_loc = result.scalars().first()
        if rider_loc:
            response["rider_location"] = {
                "latitude": rider_loc.latitude,
                "longitude": rider_loc.longitude,
                "updated_at": rider_loc.updated_at.isoformat(),
            }

    return response


# ── POST /api/v1/orders/{order_id}/cancel ─────────────────────────────────────
@router.post(
    "/{order_id}/cancel",
    response_model=OrderResponse,
    summary="Cancel an order",
    description="Customers can cancel before restaurant accepts. Admins can cancel at any stage.",
)
async def cancel_order(
    order_id: int = Path(..., ge=1),
    body: OrderCancelRequest = ...,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> OrderResponse:
    """
    **Request Body:**
    ```json
    {"reason": "Changed my mind"}
    ```
    """
    service = OrderService(db)
    order = await service.cancel_order(order_id, current_user.id, body.reason)
    return OrderResponse.model_validate(order)


# ══════════════════════════════════════════════════════════════════════
# RESTAURANT OWNER ORDER MANAGEMENT
# ══════════════════════════════════════════════════════════════════════

# ── GET /api/v1/orders/restaurant/{restaurant_id} ────────────────────
@router.get(
    "/restaurant/{restaurant_id}",
    response_model=PaginatedResponse[OrderResponse],
    summary="List orders for a restaurant (restaurant owner / admin)",
)
async def list_restaurant_orders(
    restaurant_id: int = Path(..., ge=1),
    status_filter: Optional[OrderStatus] = Query(default=None, alias="status"),
    pagination: PaginationParams = Depends(),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> PaginatedResponse[OrderResponse]:
    from app.repositories.order_repository import OrderRepository
    from app.repositories.restaurant_repository import RestaurantRepository
    from app.exceptions.custom import ForbiddenException, NotFoundException
    r_repo = RestaurantRepository(db)
    restaurant = await r_repo.get(restaurant_id)
    if not restaurant:
        raise NotFoundException("Restaurant", restaurant_id)
    if current_user.role not in (UserRole.ADMIN, UserRole.SUPER_ADMIN):
        if restaurant.owner_id != current_user.id:
            raise ForbiddenException("You do not own this restaurant.")
    repo = OrderRepository(db)
    orders, total = await repo.get_restaurant_orders(
        restaurant_id=restaurant_id,
        status_filter=status_filter,
        skip=pagination.skip,
        limit=pagination.limit,
    )
    return PaginatedResponse(
        data=[OrderResponse.model_validate(o) for o in orders],
        pagination=pagination.meta(total),
    )


# ── POST /api/v1/orders/{order_id}/accept ────────────────────────────
@router.post(
    "/{order_id}/accept",
    response_model=OrderResponse,
    summary="Accept order (restaurant owner)",
)
async def accept_order(
    order_id: int = Path(..., ge=1),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> OrderResponse:
    service = OrderService(db)
    order = await service.transition_order_status(
        order_id, OrderStatus.ACCEPTED, current_user.id, "Order accepted by restaurant"
    )
    return OrderResponse.model_validate(order)


# ── POST /api/v1/orders/{order_id}/reject ────────────────────────────
@router.post(
    "/{order_id}/reject",
    response_model=OrderResponse,
    summary="Reject order (restaurant owner)",
)
async def reject_order(
    order_id: int = Path(..., ge=1),
    body: OrderRejectRequest = ...,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> OrderResponse:
    """
    **Request Body:**
    ```json
    {"reason": "Out of key ingredients"}
    ```
    """
    from app.repositories.order_repository import OrderRepository
    repo = OrderRepository(db)
    order_obj = await repo.get(order_id)
    if order_obj:
        order_obj.rejection_reason = body.reason
        db.add(order_obj)
    service = OrderService(db)
    order = await service.transition_order_status(
        order_id, OrderStatus.CANCELLED, current_user.id, f"Rejected: {body.reason}"
    )
    return OrderResponse.model_validate(order)


# ── POST /api/v1/orders/{order_id}/mark-preparing ────────────────────
@router.post(
    "/{order_id}/mark-preparing",
    response_model=OrderResponse,
    summary="Mark order as preparing (restaurant owner)",
)
async def mark_preparing(
    order_id: int = Path(..., ge=1),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> OrderResponse:
    service = OrderService(db)
    order = await service.transition_order_status(order_id, OrderStatus.PREPARING, current_user.id)
    return OrderResponse.model_validate(order)


# ── POST /api/v1/orders/{order_id}/mark-ready ────────────────────────
@router.post(
    "/{order_id}/mark-ready",
    response_model=OrderResponse,
    summary="Mark order as ready for pickup (restaurant owner)",
)
async def mark_ready(
    order_id: int = Path(..., ge=1),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> OrderResponse:
    service = OrderService(db)
    order = await service.transition_order_status(order_id, OrderStatus.READY, current_user.id)
    return OrderResponse.model_validate(order)


# ── POST /api/v1/orders/{order_id}/assign-rider ──────────────────────
@router.post(
    "/{order_id}/assign-rider",
    response_model=OrderResponse,
    summary="Manually assign rider to order",
)
async def assign_rider(
    order_id: int = Path(..., ge=1),
    body: OrderAssignRiderRequest = ...,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> OrderResponse:
    """
    **Request Body:**
    ```json
    {"rider_id": 7}
    ```
    """
    from app.services.delivery_service import DeliveryService
    service = DeliveryService(db)
    order = await service.assign_rider(order_id, body.rider_id, current_user)
    return OrderResponse.model_validate(order)


# ── POST /api/v1/orders/{order_id}/auto-assign-rider ─────────────────
@router.post(
    "/{order_id}/auto-assign-rider",
    response_model=OrderResponse,
    summary="Auto-assign nearest available rider",
)
async def auto_assign_rider(
    order_id: int = Path(..., ge=1),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> OrderResponse:
    from app.services.delivery_service import DeliveryService
    service = DeliveryService(db)
    order = await service.auto_assign_rider(order_id, current_user)
    return OrderResponse.model_validate(order)
