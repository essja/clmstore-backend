"""
CLMStore — Admin Router
Dashboard management for customers, restaurants, riders, orders, payments, disputes, and support.
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
    DashboardStatsResponse,
    DisputeCreate,
    DisputeResolveRequest,
    DisputeResponse,
    SupportTicketCreate,
    SupportTicketResponse,
    SupportTicketUpdate,
)
from app.schemas.common import MessageResponse, PaginatedResponse
from app.schemas.order import OrderResponse
from app.schemas.payment import PaymentResponse
from app.schemas.restaurant import RestaurantResponse
from app.schemas.rider import RiderProfileResponse, RiderWithdrawalResponse
from app.schemas.restaurant import RestaurantWithdrawalResponse
from app.schemas.user import UserProfileResponse
from app.services.analytics_service import AnalyticsService
from app.utils.constants import UserRole

router = APIRouter()

# All admin routes require at minimum ADMIN role
_admin_dep = Depends(require_roles(UserRole.ADMIN, UserRole.SUPER_ADMIN))


# ══════════════════════════════════════════════════════════════
# DASHBOARD
# ══════════════════════════════════════════════════════════════

@router.get(
    "/dashboard",
    response_model=DashboardStatsResponse,
    summary="Admin dashboard statistics",
    description="Returns real-time platform stats: total users, revenue, order counts, etc.",
    dependencies=[_admin_dep],
)
async def dashboard(
    period: str = Query(default="today", description="today | week | month | year"),
    db: AsyncSession = Depends(get_db),
) -> DashboardStatsResponse:
    """
    **Response:**
    ```json
    {
        "total_customers": 1250,
        "total_restaurants": 48,
        "total_riders": 120,
        "total_orders": 5642,
        "total_revenue": 284350000.0,
        "total_commission": 28435000.0,
        "order_status_counts": {"pending": 12, "delivered": 5430},
        "daily_revenue": [{"date": "2024-06-01", "revenue": 8500000.0}]
    }
    ```
    """
    service = AnalyticsService(db)
    return await service.get_dashboard_stats(period)


# ══════════════════════════════════════════════════════════════
# USER MANAGEMENT
# ══════════════════════════════════════════════════════════════

@router.get(
    "/users",
    response_model=PaginatedResponse[UserProfileResponse],
    summary="List all platform users",
    dependencies=[_admin_dep],
)
async def list_users(
    role: Optional[UserRole] = Query(default=None),
    is_active: Optional[bool] = Query(default=None),
    q: Optional[str] = Query(default=None, description="Search by name or email"),
    pagination: PaginationParams = Depends(),
    db: AsyncSession = Depends(get_db),
) -> PaginatedResponse[UserProfileResponse]:
    from app.repositories.user_repository import UserRepository
    repo = UserRepository(db)
    users, total = await repo.search_users(role=role, is_active=is_active, query=q, skip=pagination.skip, limit=pagination.limit)
    return PaginatedResponse(
        data=[UserProfileResponse.model_validate(u) for u in users],
        pagination=pagination.meta(total),
    )


@router.post(
    "/users/{user_id}/suspend",
    response_model=MessageResponse,
    summary="Suspend a user account",
    dependencies=[_admin_dep],
)
async def suspend_user(
    user_id: int = Path(..., ge=1),
    reason: str = Query(..., min_length=5),
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    from app.repositories.user_repository import UserRepository
    from app.exceptions.custom import NotFoundException
    repo = UserRepository(db)
    user = await repo.get(user_id)
    if not user:
        raise NotFoundException("User", user_id)
    user.is_active = False
    db.add(user)
    return MessageResponse(message=f"User {user_id} suspended. Reason: {reason}")


@router.post(
    "/users/{user_id}/activate",
    response_model=MessageResponse,
    summary="Reactivate a suspended user",
    dependencies=[_admin_dep],
)
async def activate_user(
    user_id: int = Path(..., ge=1),
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    from app.repositories.user_repository import UserRepository
    from app.exceptions.custom import NotFoundException
    repo = UserRepository(db)
    user = await repo.get(user_id)
    if not user:
        raise NotFoundException("User", user_id)
    user.is_active = True
    db.add(user)
    return MessageResponse(message=f"User {user_id} reactivated.")


# ══════════════════════════════════════════════════════════════
# RESTAURANT MANAGEMENT
# ══════════════════════════════════════════════════════════════

@router.get(
    "/restaurants",
    response_model=PaginatedResponse[RestaurantResponse],
    summary="List all restaurants (admin view)",
    dependencies=[_admin_dep],
)
async def list_restaurants(
    status_filter: Optional[str] = Query(default=None, alias="status"),
    pagination: PaginationParams = Depends(),
    db: AsyncSession = Depends(get_db),
) -> PaginatedResponse[RestaurantResponse]:
    from app.repositories.restaurant_repository import RestaurantRepository
    repo = RestaurantRepository(db)
    restaurants, total = await repo.get_all_with_status(status_filter=status_filter, skip=pagination.skip, limit=pagination.limit)
    return PaginatedResponse(
        data=[RestaurantResponse.model_validate(r) for r in restaurants],
        pagination=pagination.meta(total),
    )


@router.post(
    "/restaurants/{restaurant_id}/approve",
    response_model=RestaurantResponse,
    summary="Approve a restaurant",
    dependencies=[_admin_dep],
)
async def approve_restaurant(
    restaurant_id: int = Path(..., ge=1),
    current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.SUPER_ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> RestaurantResponse:
    from app.services.restaurant_service import RestaurantService
    service = RestaurantService(db)
    restaurant = await service.approve_restaurant(restaurant_id, current_user.id)
    return RestaurantResponse.model_validate(restaurant)


@router.post(
    "/restaurants/{restaurant_id}/reject",
    response_model=RestaurantResponse,
    summary="Reject a restaurant application",
    dependencies=[_admin_dep],
)
async def reject_restaurant(
    restaurant_id: int = Path(..., ge=1),
    reason: str = Query(..., min_length=10),
    current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.SUPER_ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> RestaurantResponse:
    from app.services.restaurant_service import RestaurantService
    service = RestaurantService(db)
    restaurant = await service.reject_restaurant(restaurant_id, reason, current_user.id)
    return RestaurantResponse.model_validate(restaurant)


@router.post(
    "/restaurants/{restaurant_id}/suspend",
    response_model=RestaurantResponse,
    summary="Suspend a restaurant",
    dependencies=[_admin_dep],
)
async def suspend_restaurant(
    restaurant_id: int = Path(..., ge=1),
    reason: str = Query(..., min_length=10),
    current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.SUPER_ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> RestaurantResponse:
    from app.services.restaurant_service import RestaurantService
    service = RestaurantService(db)
    restaurant = await service.suspend_restaurant(restaurant_id, reason, current_user.id)
    return RestaurantResponse.model_validate(restaurant)


@router.post(
    "/restaurants/{restaurant_id}/verify-document/{document_id}",
    response_model=MessageResponse,
    summary="Verify a restaurant document",
    dependencies=[_admin_dep],
)
async def verify_document(
    restaurant_id: int = Path(..., ge=1),
    document_id: int = Path(..., ge=1),
    current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.SUPER_ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    from app.repositories.restaurant_repository import RestaurantDocumentRepository
    from app.exceptions.custom import NotFoundException
    repo = RestaurantDocumentRepository(db)
    doc = await repo.get(document_id)
    if not doc or doc.restaurant_id != restaurant_id:
        raise NotFoundException("Document")
    doc.is_verified = True
    doc.verified_by = current_user.id
    db.add(doc)
    return MessageResponse(message="Document verified successfully.")


# ══════════════════════════════════════════════════════════════
# RIDER MANAGEMENT
# ══════════════════════════════════════════════════════════════

@router.get(
    "/riders",
    response_model=PaginatedResponse[RiderProfileResponse],
    summary="List all riders",
    dependencies=[_admin_dep],
)
async def list_riders(
    is_verified: Optional[bool] = Query(default=None),
    is_available: Optional[bool] = Query(default=None),
    pagination: PaginationParams = Depends(),
    db: AsyncSession = Depends(get_db),
) -> PaginatedResponse[RiderProfileResponse]:
    from app.repositories.rider_repository import RiderRepository
    repo = RiderRepository(db)
    riders, total = await repo.search_riders(
        is_verified=is_verified, is_available=is_available,
        skip=pagination.skip, limit=pagination.limit,
    )
    return PaginatedResponse(
        data=[RiderProfileResponse.model_validate(r) for r in riders],
        pagination=pagination.meta(total),
    )


@router.post(
    "/riders/{rider_id}/verify",
    response_model=MessageResponse,
    summary="Verify and approve a rider",
    dependencies=[_admin_dep],
)
async def verify_rider(
    rider_id: int = Path(..., ge=1),
    current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.SUPER_ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    from app.services.rider_service import RiderService
    service = RiderService(db)
    await service.verify_rider(rider_id, current_user.id)
    return MessageResponse(message="Rider verified and approved.")


@router.get(
    "/riders/withdrawals",
    response_model=PaginatedResponse[RiderWithdrawalResponse],
    summary="List all pending rider withdrawals",
    dependencies=[_admin_dep],
)
async def list_withdrawals(
    status_filter: Optional[str] = Query(default="pending"),
    pagination: PaginationParams = Depends(),
    db: AsyncSession = Depends(get_db),
) -> PaginatedResponse[RiderWithdrawalResponse]:
    from app.repositories.rider_repository import RiderWithdrawalRepository
    repo = RiderWithdrawalRepository(db)
    withdrawals, total = await repo.list_all(status=status_filter, skip=pagination.skip, limit=pagination.limit)
    return PaginatedResponse(
        data=[RiderWithdrawalResponse.model_validate(w) for w in withdrawals],
        pagination=pagination.meta(total),
    )


@router.post(
    "/riders/withdrawals/{withdrawal_id}/approve",
    response_model=MessageResponse,
    summary="Approve a rider withdrawal",
    dependencies=[_admin_dep],
)
async def approve_withdrawal(
    withdrawal_id: int = Path(..., ge=1),
    transaction_reference: Optional[str] = Query(default=None),
    current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.SUPER_ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    from app.services.rider_service import RiderService
    service = RiderService(db)
    await service.approve_withdrawal(withdrawal_id, current_user.id, transaction_reference)
    return MessageResponse(message="Withdrawal approved and processed.")


@router.post(
    "/riders/withdrawals/{withdrawal_id}/reject",
    response_model=MessageResponse,
    summary="Reject a rider withdrawal",
    dependencies=[_admin_dep],
)
async def reject_withdrawal(
    withdrawal_id: int = Path(..., ge=1),
    reason: str = Query(...),
    current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.SUPER_ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    from app.services.rider_service import RiderService
    service = RiderService(db)
    await service.reject_withdrawal(withdrawal_id, current_user.id, reason)
    return MessageResponse(message="Withdrawal rejected.")


# ══════════════════════════════════════════════════════════════
# RESTAURANT WITHDRAWAL MANAGEMENT
# ══════════════════════════════════════════════════════════════

@router.get(
    "/restaurants/withdrawals",
    response_model=PaginatedResponse[RestaurantWithdrawalResponse],
    summary="List all restaurant withdrawals",
    dependencies=[_admin_dep],
)
async def list_restaurant_withdrawals(
    status_filter: Optional[str] = Query(default="pending"),
    pagination: PaginationParams = Depends(),
    db: AsyncSession = Depends(get_db),
) -> PaginatedResponse[RestaurantWithdrawalResponse]:
    from sqlalchemy import select, func
    from app.models.restaurant import RestaurantWithdrawal
    query = select(RestaurantWithdrawal)
    if status_filter:
        query = query.where(RestaurantWithdrawal.status == status_filter)
    count_q = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_q)).scalar() or 0
    result = await db.execute(
        query.order_by(RestaurantWithdrawal.created_at.desc())
        .offset(pagination.skip).limit(pagination.limit)
    )
    withdrawals = list(result.scalars().all())
    return PaginatedResponse(
        data=[RestaurantWithdrawalResponse.model_validate(w) for w in withdrawals],
        pagination=pagination.meta(total),
    )


@router.post(
    "/restaurants/withdrawals/{withdrawal_id}/approve",
    response_model=MessageResponse,
    summary="Approve a restaurant withdrawal and mark as paid",
    dependencies=[_admin_dep],
)
async def approve_restaurant_withdrawal(
    withdrawal_id: int = Path(..., ge=1),
    transaction_reference: Optional[str] = Query(default=None, description="Mobile money or bank transaction reference"),
    current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.SUPER_ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    from app.models.restaurant import RestaurantWithdrawal
    from app.exceptions.custom import NotFoundException, BusinessRuleException
    from datetime import datetime, timezone

    withdrawal = await db.get(RestaurantWithdrawal, withdrawal_id)
    if not withdrawal:
        raise NotFoundException("Withdrawal", withdrawal_id)
    if withdrawal.status != "pending":
        raise BusinessRuleException(f"Withdrawal is already {withdrawal.status}.")

    withdrawal.status = "completed"
    withdrawal.transaction_reference = transaction_reference
    withdrawal.processed_at = datetime.now(timezone.utc).isoformat()
    withdrawal.processed_by = current_user.id
    db.add(withdrawal)
    return MessageResponse(message=f"Restaurant withdrawal #{withdrawal_id} approved and marked as paid.")


@router.post(
    "/restaurants/withdrawals/{withdrawal_id}/reject",
    response_model=MessageResponse,
    summary="Reject a restaurant withdrawal and refund balance",
    dependencies=[_admin_dep],
)
async def reject_restaurant_withdrawal(
    withdrawal_id: int = Path(..., ge=1),
    reason: str = Query(..., description="Reason for rejection"),
    current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.SUPER_ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    from sqlalchemy import select
    from app.models.restaurant import Restaurant, RestaurantWithdrawal
    from app.exceptions.custom import NotFoundException, BusinessRuleException
    from datetime import datetime, timezone

    withdrawal = await db.get(RestaurantWithdrawal, withdrawal_id)
    if not withdrawal:
        raise NotFoundException("Withdrawal", withdrawal_id)
    if withdrawal.status != "pending":
        raise BusinessRuleException(f"Withdrawal is already {withdrawal.status}.")

    # Refund balance back to restaurant
    restaurant = await db.get(Restaurant, withdrawal.restaurant_id)
    if restaurant:
        restaurant.current_balance = round(restaurant.current_balance + withdrawal.amount, 2)
        db.add(restaurant)

    withdrawal.status = "rejected"
    withdrawal.notes = reason
    withdrawal.processed_at = datetime.now(timezone.utc).isoformat()
    withdrawal.processed_by = current_user.id
    db.add(withdrawal)
    return MessageResponse(message=f"Restaurant withdrawal #{withdrawal_id} rejected. Balance refunded.")


# ══════════════════════════════════════════════════════════════
# ORDER MANAGEMENT
# ══════════════════════════════════════════════════════════════

@router.get(
    "/orders",
    response_model=PaginatedResponse[OrderResponse],
    summary="List all orders (admin view)",
    dependencies=[_admin_dep],
)
async def list_all_orders(
    status_filter: Optional[str] = Query(default=None, alias="status"),
    restaurant_id: Optional[int] = Query(default=None),
    user_id: Optional[int] = Query(default=None),
    pagination: PaginationParams = Depends(),
    db: AsyncSession = Depends(get_db),
) -> PaginatedResponse[OrderResponse]:
    from app.repositories.order_repository import OrderRepository
    repo = OrderRepository(db)
    orders, total = await repo.admin_list_orders(
        status_filter=status_filter,
        restaurant_id=restaurant_id,
        user_id=user_id,
        skip=pagination.skip,
        limit=pagination.limit,
    )
    return PaginatedResponse(
        data=[OrderResponse.model_validate(o) for o in orders],
        pagination=pagination.meta(total),
    )


# ══════════════════════════════════════════════════════════════
# SUPPORT TICKETS
# ══════════════════════════════════════════════════════════════

@router.post(
    "/support/tickets",
    response_model=SupportTicketResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a support ticket",
)
async def create_ticket(
    body: SupportTicketCreate,
    current_user: User = Depends(require_roles(
        UserRole.CUSTOMER, UserRole.RESTAURANT_OWNER, UserRole.RIDER, UserRole.ADMIN, UserRole.SUPER_ADMIN
    )),
    db: AsyncSession = Depends(get_db),
) -> SupportTicketResponse:
    from app.models.support import SupportTicket
    from app.utils.constants import TicketStatus
    ticket = SupportTicket(
        user_id=current_user.id,
        subject=body.subject,
        description=body.description,
        priority=body.priority,
        status=TicketStatus.OPEN,
    )
    db.add(ticket)
    await db.flush()
    return SupportTicketResponse.model_validate(ticket)


@router.get(
    "/support/tickets",
    response_model=PaginatedResponse[SupportTicketResponse],
    summary="List support tickets (admin)",
    dependencies=[_admin_dep],
)
async def list_tickets(
    status_filter: Optional[str] = Query(default=None, alias="status"),
    priority: Optional[str] = Query(default=None),
    pagination: PaginationParams = Depends(),
    db: AsyncSession = Depends(get_db),
) -> PaginatedResponse[SupportTicketResponse]:
    from app.models.support import SupportTicket
    from sqlalchemy import select, func
    query = select(SupportTicket)
    if status_filter:
        query = query.filter(SupportTicket.status == status_filter)
    if priority:
        query = query.filter(SupportTicket.priority == priority)
    count_q = select(func.count()).select_from(query.subquery())
    total_res = await db.execute(count_q)
    total = total_res.scalar() or 0
    result = await db.execute(query.offset(pagination.skip).limit(pagination.limit))
    tickets = list(result.scalars().all())
    return PaginatedResponse(
        data=[SupportTicketResponse.model_validate(t) for t in tickets],
        pagination=pagination.meta(total),
    )


@router.patch(
    "/support/tickets/{ticket_id}",
    response_model=SupportTicketResponse,
    summary="Update support ticket status",
    dependencies=[_admin_dep],
)
async def update_ticket(
    ticket_id: int = Path(..., ge=1),
    body: SupportTicketUpdate = ...,
    db: AsyncSession = Depends(get_db),
) -> SupportTicketResponse:
    from app.models.support import SupportTicket
    from app.exceptions.custom import NotFoundException
    ticket = await db.get(SupportTicket, ticket_id)
    if not ticket:
        raise NotFoundException("Support ticket", ticket_id)
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(ticket, field, value)
    db.add(ticket)
    return SupportTicketResponse.model_validate(ticket)


# ══════════════════════════════════════════════════════════════
# DISPUTES
# ══════════════════════════════════════════════════════════════

@router.post(
    "/disputes",
    response_model=DisputeResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Open a dispute for an order",
)
async def create_dispute(
    body: DisputeCreate,
    current_user: User = Depends(require_roles(
        UserRole.CUSTOMER, UserRole.RESTAURANT_OWNER, UserRole.ADMIN, UserRole.SUPER_ADMIN
    )),
    db: AsyncSession = Depends(get_db),
) -> DisputeResponse:
    from app.models.support import Dispute
    from app.utils.constants import DisputeStatus
    dispute = Dispute(
        order_id=body.order_id,
        user_id=current_user.id,
        reason=body.reason,
        status=DisputeStatus.OPEN,
    )
    db.add(dispute)
    await db.flush()
    return DisputeResponse.model_validate(dispute)


@router.get(
    "/disputes",
    response_model=PaginatedResponse[DisputeResponse],
    summary="List disputes (admin)",
    dependencies=[_admin_dep],
)
async def list_disputes(
    status_filter: Optional[str] = Query(default=None, alias="status"),
    pagination: PaginationParams = Depends(),
    db: AsyncSession = Depends(get_db),
) -> PaginatedResponse[DisputeResponse]:
    from app.models.support import Dispute
    from sqlalchemy import select, func
    query = select(Dispute)
    if status_filter:
        query = query.filter(Dispute.status == status_filter)
    count_q = select(func.count()).select_from(query.subquery())
    total_res = await db.execute(count_q)
    total = total_res.scalar() or 0
    result = await db.execute(query.offset(pagination.skip).limit(pagination.limit))
    disputes = list(result.scalars().all())
    return PaginatedResponse(
        data=[DisputeResponse.model_validate(d) for d in disputes],
        pagination=pagination.meta(total),
    )


@router.post(
    "/disputes/{dispute_id}/resolve",
    response_model=DisputeResponse,
    summary="Resolve a dispute",
    dependencies=[_admin_dep],
)
async def resolve_dispute(
    dispute_id: int = Path(..., ge=1),
    body: DisputeResolveRequest = ...,
    current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.SUPER_ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> DisputeResponse:
    from app.models.support import Dispute
    from app.exceptions.custom import NotFoundException, BusinessRuleException
    dispute = await db.get(Dispute, dispute_id)
    if not dispute:
        raise NotFoundException("Dispute", dispute_id)

    resolution_text = body.resolution

    if body.refund_payment:
        from app.repositories.payment_repository import PaymentRepository
        from app.services.payment_service import PaymentService
        from app.schemas.payment import RefundRequest
        from app.utils.constants import PaymentStatus
        pay_repo = PaymentRepository(db)
        payment = await pay_repo.get_by_order(dispute.order_id)
        if not payment:
            raise BusinessRuleException("No payment found for this order — cannot refund.")
        if payment.status != PaymentStatus.COMPLETED:
            raise BusinessRuleException("Payment is not completed — cannot refund.")
        svc = PaymentService(db)
        refund_req = RefundRequest(
            reason=f"Dispute #{dispute_id} resolved: {body.resolution}",
            amount=None,  # full refund
        )
        try:
            await svc.process_refund(payment.id, refund_req, current_user)
            resolution_text = f"[REFUNDED] {body.resolution}"
        except Exception:
            resolution_text = f"[REFUND FAILED — manual action required] {body.resolution}"

    dispute.status = body.status
    dispute.resolution = resolution_text
    dispute.resolved_by = current_user.id
    db.add(dispute)
    return DisputeResponse.model_validate(dispute)
