"""
CLMStore — Delivery Router
Handles delivery lifecycle, rider updates, and live location tracking.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Path, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies.auth import get_current_active_user
from app.models.user import User
from app.schemas.common import MessageResponse
from app.schemas.delivery import DeliveryFailRequest, DeliveryResponse
from app.schemas.location import LocationUpdateRequest, RiderLocationResponse
from app.services.delivery_service import DeliveryService
from app.utils.constants import UserRole

router = APIRouter()


# ── GET /api/v1/deliveries/{order_id} ────────────────────────────────────────
@router.get(
    "/{order_id}",
    response_model=DeliveryResponse,
    summary="Get delivery details for an order",
)
async def get_delivery(
    order_id: int = Path(..., ge=1),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> DeliveryResponse:
    from app.repositories.delivery_repository import DeliveryRepository
    from app.exceptions.custom import NotFoundException
    repo = DeliveryRepository(db)
    delivery = await repo.get_by_order_id(order_id)
    if not delivery:
        raise NotFoundException("Delivery")
    return DeliveryResponse.model_validate(delivery)


# ── POST /api/v1/deliveries/{order_id}/accept ────────────────────────────────
@router.post(
    "/{order_id}/accept",
    response_model=DeliveryResponse,
    summary="Rider accepts delivery assignment",
)
async def accept_delivery(
    order_id: int = Path(..., ge=1),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> DeliveryResponse:
    """Called by the assigned rider to accept the delivery."""
    service = DeliveryService(db)
    delivery = await service.accept_delivery(order_id, current_user)
    return DeliveryResponse.model_validate(delivery)


# ── POST /api/v1/deliveries/{order_id}/reject ────────────────────────────────
@router.post(
    "/{order_id}/reject",
    response_model=MessageResponse,
    summary="Rider rejects delivery assignment",
)
async def reject_delivery(
    order_id: int = Path(..., ge=1),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    """Rider rejects the assigned delivery. A new rider will be auto-assigned."""
    service = DeliveryService(db)
    await service.reject_delivery(order_id, current_user)
    return MessageResponse(message="Delivery rejected. Reassigning to another rider.")


# ── POST /api/v1/deliveries/{order_id}/pickup ────────────────────────────────
@router.post(
    "/{order_id}/pickup",
    response_model=DeliveryResponse,
    summary="Rider picked up the order",
)
async def pickup_order(
    order_id: int = Path(..., ge=1),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> DeliveryResponse:
    """Marks the order as picked up by the rider from the restaurant."""
    service = DeliveryService(db)
    delivery = await service.mark_picked_up(order_id, current_user)
    return DeliveryResponse.model_validate(delivery)


# ── POST /api/v1/deliveries/{order_id}/complete ──────────────────────────────
@router.post(
    "/{order_id}/complete",
    response_model=DeliveryResponse,
    summary="Rider marks delivery as completed",
)
async def complete_delivery(
    order_id: int = Path(..., ge=1),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> DeliveryResponse:
    """
    Marks the delivery as completed (delivered to customer).
    Triggers earnings recording and customer notification.
    """
    service = DeliveryService(db)
    delivery = await service.complete_delivery(order_id, current_user)
    return DeliveryResponse.model_validate(delivery)


# ── POST /api/v1/deliveries/{order_id}/fail ──────────────────────────────────
@router.post(
    "/{order_id}/fail",
    response_model=DeliveryResponse,
    summary="Rider reports delivery failure",
)
async def fail_delivery(
    order_id: int = Path(..., ge=1),
    body: DeliveryFailRequest = ...,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> DeliveryResponse:
    """
    **Request Body:**
    ```json
    {"reason": "Customer not at address after 3 attempts"}
    ```
    """
    service = DeliveryService(db)
    delivery = await service.fail_delivery(order_id, body.reason, current_user)
    return DeliveryResponse.model_validate(delivery)


# ── PUT /api/v1/deliveries/location ──────────────────────────────────────────
@router.put(
    "/location",
    response_model=RiderLocationResponse,
    summary="Rider updates live GPS location",
    description=(
        "Called periodically by the rider's app to broadcast current GPS coordinates. "
        "Location is stored in Redis for real-time access and pushed via WebSocket."
    ),
)
async def update_rider_location(
    body: LocationUpdateRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> RiderLocationResponse:
    """
    **Request Body:**
    ```json
    {
        "latitude": 8.4701,
        "longitude": -13.2345,
        "bearing": 180.0
    }
    ```
    **Headers:** `Authorization: Bearer <rider-token>`
    """
    from app.exceptions.custom import ForbiddenException
    if current_user.role != UserRole.RIDER:
        raise ForbiddenException("Only riders can update location.")
    service = DeliveryService(db)
    location = await service.update_rider_location(current_user.id, body)
    return location


# ── GET /api/v1/deliveries/location/{rider_id} ───────────────────────────────
@router.get(
    "/location/{rider_id}",
    response_model=RiderLocationResponse,
    summary="Get current rider location",
)
async def get_rider_location(
    rider_id: int = Path(..., ge=1),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> RiderLocationResponse:
    """Returns the most recent GPS location of a rider."""
    service = DeliveryService(db)
    location = await service.get_rider_location(rider_id)
    return location
