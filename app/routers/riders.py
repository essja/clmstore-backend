"""
CLMStore — Riders Router
Handles rider registration, profile, documents, availability, earnings, and withdrawals.
"""
from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, File, Path, Query, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies.auth import get_current_active_user
from app.dependencies.pagination import PaginationParams
from app.exceptions.custom import ForbiddenException
from app.models.user import User
from app.schemas.common import MessageResponse, PaginatedResponse
from app.schemas.rider import (
    RiderDocumentCreate,
    RiderDocumentResponse,
    RiderEarningResponse,
    RiderProfileRegisterRequest,
    RiderProfileResponse,
    RiderProfileUpdateRequest,
    RiderWithdrawalRequest,
    RiderWithdrawalResponse,
)
from app.services.rider_service import RiderService
from app.services.file_service import FileService
from app.utils.constants import UserRole

router = APIRouter()


def _require_rider(user: User) -> None:
    if user.role not in (UserRole.RIDER, UserRole.ADMIN, UserRole.SUPER_ADMIN):
        raise ForbiddenException("Rider access required.")


# ── POST /api/v1/riders/register ─────────────────────────────────────────────
@router.post(
    "/register",
    response_model=RiderProfileResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new rider profile",
    description=(
        "Creates a rider profile for a user with the `rider` role. "
        "The rider starts as unverified and must upload documents."
    ),
)
async def register_rider(
    body: RiderProfileRegisterRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> RiderProfileResponse:
    """
    **Request Body:**
    ```json
    {
        "vehicle_type": "motorcycle",
        "vehicle_plate": "SL-1234",
        "vehicle_model": "Honda CG 125",
        "vehicle_color": "Red"
    }
    ```
    """
    _require_rider(current_user)
    service = RiderService(db)
    profile = await service.create_profile(current_user.id, body)
    return RiderProfileResponse.model_validate(profile)


# ── GET /api/v1/riders/me/current-delivery ───────────────────────────────────
@router.get(
    "/me/current-delivery",
    summary="Get rider's current active delivery",
    description=(
        "Returns the rider's active delivery job — the one shown on the rider app home screen. "
        "Returns null if no active delivery."
    ),
)
async def get_current_delivery(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    **Response (active delivery):**
    ```json
    {
        "delivery_id": 14,
        "order_id": 42,
        "order_number": "CLM-784562",
        "restaurant_name": "Mama Salone Kitchen",
        "restaurant_address": "15 Lumley Beach Road",
        "restaurant_lat": 8.4512,
        "restaurant_lon": -13.2789,
        "customer_address": "21 Peytermu Road, Freetown",
        "customer_lat": 8.4657,
        "customer_lon": -13.2317,
        "order_total": 81500.0,
        "distance_km": 3.5,
        "status": "accepted"
    }
    ```
    Returns `{"delivery": null}` when no active delivery.
    """
    _require_rider(current_user)
    from sqlalchemy import select
    from app.models.delivery import Delivery
    from app.models.order import Order
    from app.models.restaurant import Restaurant
    from app.utils.constants import DeliveryStatus

    active_statuses = [
        DeliveryStatus.ASSIGNED,
        DeliveryStatus.ACCEPTED,
        DeliveryStatus.PICKING_UP,
        DeliveryStatus.PICKED_UP,
        DeliveryStatus.ON_THE_WAY,
    ]
    result = await db.execute(
        select(Delivery)
        .where(
            Delivery.rider_id == current_user.id,
            Delivery.status.in_(active_statuses),
        )
        .order_by(Delivery.created_at.desc())
        .limit(1)
    )
    delivery = result.scalars().first()
    if not delivery:
        return {"delivery": None}

    order = await db.get(Order, delivery.order_id)
    restaurant = await db.get(Restaurant, order.restaurant_id) if order else None

    return {
        "delivery": {
            "delivery_id": delivery.id,
            "order_id": delivery.order_id,
            "order_number": order.order_number if order else None,
            "restaurant_name": restaurant.name if restaurant else None,
            "restaurant_address": restaurant.address if restaurant else None,
            "restaurant_lat": restaurant.latitude if restaurant else None,
            "restaurant_lon": restaurant.longitude if restaurant else None,
            "customer_address": order.delivery_address_snapshot.get("address_line") if order and order.delivery_address_snapshot else None,
            "customer_lat": order.delivery_address_snapshot.get("latitude") if order and order.delivery_address_snapshot else None,
            "customer_lon": order.delivery_address_snapshot.get("longitude") if order and order.delivery_address_snapshot else None,
            "order_total": order.total_amount if order else None,
            "distance_km": delivery.distance_km,
            "status": delivery.status.value,
        }
    }


# ── GET /api/v1/riders/profile ───────────────────────────────────────────────
@router.get(
    "/profile",
    response_model=RiderProfileResponse,
    summary="Get rider's own profile",
)
async def get_rider_profile(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> RiderProfileResponse:
    _require_rider(current_user)
    service = RiderService(db)
    profile = await service.get_profile_by_user_id(current_user.id)
    return RiderProfileResponse.model_validate(profile)


# ── PATCH /api/v1/riders/profile ─────────────────────────────────────────────
@router.patch(
    "/profile",
    response_model=RiderProfileResponse,
    summary="Update rider profile",
)
async def update_rider_profile(
    body: RiderProfileUpdateRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> RiderProfileResponse:
    _require_rider(current_user)
    service = RiderService(db)
    profile = await service.update_profile(current_user.id, body)
    return RiderProfileResponse.model_validate(profile)


# ── PATCH /api/v1/riders/availability ────────────────────────────────────────
@router.patch(
    "/availability",
    response_model=MessageResponse,
    summary="Toggle rider availability (online/offline)",
)
async def toggle_availability(
    is_available: bool = Query(..., description="true = online, false = offline"),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    """Sets the rider as available or unavailable for deliveries."""
    _require_rider(current_user)
    service = RiderService(db)
    await service.set_availability(current_user.id, is_available)
    state = "online" if is_available else "offline"
    return MessageResponse(message=f"You are now {state}.")


# ── POST /api/v1/riders/documents ────────────────────────────────────────────
@router.post(
    "/documents",
    response_model=RiderDocumentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload rider verification document",
)
async def upload_document(
    doc_type: str = Query(..., description="drivers_license | national_id | vehicle_insurance | police_clearance | vehicle_image"),
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> RiderDocumentResponse:
    """
    Upload required documents for rider verification:
    - Driver's License
    - National ID
    - Vehicle Insurance
    - Police Clearance (optional)
    - Vehicle Image
    """
    _require_rider(current_user)
    file_service = FileService()
    url = await file_service.upload_document(file, folder="rider_documents")
    service = RiderService(db)
    doc = await service.upload_document(current_user.id, doc_type, url, file.filename)
    return RiderDocumentResponse.model_validate(doc)


# ── GET /api/v1/riders/documents ─────────────────────────────────────────────
@router.get(
    "/documents",
    response_model=List[RiderDocumentResponse],
    summary="List rider uploaded documents",
)
async def list_documents(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> List[RiderDocumentResponse]:
    _require_rider(current_user)
    service = RiderService(db)
    docs = await service.list_documents(current_user.id)
    return [RiderDocumentResponse.model_validate(d) for d in docs]


# ── GET /api/v1/riders/earnings ──────────────────────────────────────────────
@router.get(
    "/earnings",
    response_model=PaginatedResponse[RiderEarningResponse],
    summary="Get rider earnings history",
)
async def list_earnings(
    pagination: PaginationParams = Depends(),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> PaginatedResponse[RiderEarningResponse]:
    _require_rider(current_user)
    service = RiderService(db)
    earnings, total = await service.get_earnings(current_user.id, pagination.skip, pagination.limit)
    return PaginatedResponse(
        data=[RiderEarningResponse.model_validate(e) for e in earnings],
        pagination=pagination.meta(total),
    )


# ── GET /api/v1/riders/earnings/summary ──────────────────────────────────────
@router.get(
    "/earnings/summary",
    summary="Get rider earnings summary (balance, total, pending)",
)
async def earnings_summary(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    **Response:**
    ```json
    {
        "total_earnings": 1250000.0,
        "current_balance": 850000.0,
        "pending_earnings": 120000.0,
        "total_deliveries": 87,
        "average_per_delivery": 14367.0
    }
    ```
    """
    _require_rider(current_user)
    service = RiderService(db)
    return await service.get_earnings_summary(current_user.id)


# ── POST /api/v1/riders/withdrawals ──────────────────────────────────────────
@router.post(
    "/withdrawals",
    response_model=RiderWithdrawalResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Request earnings withdrawal",
)
async def request_withdrawal(
    body: RiderWithdrawalRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> RiderWithdrawalResponse:
    """
    **Request Body:**
    ```json
    {
        "amount": 500000.0,
        "payment_method": "orange_money",
        "payment_details": "+23276123456"
    }
    ```
    **Minimum withdrawal:** 50,000 SLL

    **Methods:** `orange_money` | `afrimoney` | `bank`
    """
    _require_rider(current_user)
    service = RiderService(db)
    withdrawal = await service.request_withdrawal(current_user.id, body)
    return RiderWithdrawalResponse.model_validate(withdrawal)


# ── GET /api/v1/riders/withdrawals ───────────────────────────────────────────
@router.get(
    "/withdrawals",
    response_model=PaginatedResponse[RiderWithdrawalResponse],
    summary="Get rider withdrawal history",
)
async def list_withdrawals(
    pagination: PaginationParams = Depends(),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> PaginatedResponse[RiderWithdrawalResponse]:
    _require_rider(current_user)
    service = RiderService(db)
    withdrawals, total = await service.get_withdrawals(current_user.id, pagination.skip, pagination.limit)
    return PaginatedResponse(
        data=[RiderWithdrawalResponse.model_validate(w) for w in withdrawals],
        pagination=pagination.meta(total),
    )


# ── GET /api/v1/riders/{rider_id} ────────────────────────────────────────────
@router.get(
    "/{rider_id}",
    response_model=RiderProfileResponse,
    summary="Get rider profile by ID (admin)",
)
async def get_rider_by_id(
    rider_id: int = Path(..., ge=1),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> RiderProfileResponse:
    if current_user.role not in (UserRole.ADMIN, UserRole.SUPER_ADMIN):
        raise ForbiddenException("Admin access required.")
    service = RiderService(db)
    from app.repositories.rider_repository import RiderRepository
    repo = RiderRepository(db)
    profile = await repo.get_by_user_id(rider_id)
    from app.exceptions.custom import NotFoundException
    if not profile:
        raise NotFoundException("Rider", rider_id)
    return RiderProfileResponse.model_validate(profile)
