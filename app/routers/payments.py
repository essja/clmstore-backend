"""
CLMStore — Payments Router
Handles payment initiation, verification, webhooks, invoices, and refunds.
Designed for pluggable payment provider integration.
"""
from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, Path, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies.auth import get_current_active_user
from app.dependencies.pagination import PaginationParams
from app.models.user import User
from app.schemas.common import MessageResponse, PaginatedResponse
from app.schemas.payment import (
    InvoiceResponse,
    PaymentInitiateRequest,
    PaymentResponse,
    PaymentVerifyResponse,
    ReceiptResponse,
    RefundRequest,
    TransactionResponse,
)
from app.services.payment_service import PaymentService

router = APIRouter()


# ── POST /api/v1/payments/initiate ───────────────────────────────────────────
@router.post(
    "/initiate",
    response_model=PaymentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Initiate a payment for an order",
    description=(
        "Starts the payment process for a placed order. Returns a payment record. "
        "For mobile money providers, use the returned `provider_ref` to complete payment on the provider's platform."
    ),
)
async def initiate_payment(
    body: PaymentInitiateRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> PaymentResponse:
    """
    **Request Body:**
    ```json
    {
        "order_id": 12,
        "provider": "orange_money",
        "payment_details": {
            "phone_number": "+23276123456"
        }
    }
    ```

    **Providers:** `cash` | `orange_money` | `afrimoney` | `stripe` | `paypal` | `visa` | `mastercard`

    **For cash:** Payment is immediately confirmed.
    **For mobile money:** An OTP / USSD prompt is sent to the phone number.
    **For Stripe:** Returns a `client_secret` for frontend to complete payment.
    """
    service = PaymentService(db)
    payment = await service.initiate_payment(body, current_user.id)
    return PaymentResponse.model_validate(payment)


# ── POST /api/v1/payments/{payment_id}/verify ────────────────────────────────
@router.post(
    "/{payment_id}/verify",
    response_model=PaymentVerifyResponse,
    summary="Verify payment status with provider",
    description="Polls the payment provider to confirm if payment has been completed.",
)
async def verify_payment(
    payment_id: int = Path(..., ge=1),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> PaymentVerifyResponse:
    service = PaymentService(db)
    result = await service.verify_payment(payment_id, current_user.id)
    return result


# ── GET /api/v1/payments ──────────────────────────────────────────────────────
@router.get(
    "",
    response_model=PaginatedResponse[PaymentResponse],
    summary="Get user payment history",
)
async def list_payments(
    pagination: PaginationParams = Depends(),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> PaginatedResponse[PaymentResponse]:
    from app.repositories.payment_repository import PaymentRepository
    repo = PaymentRepository(db)
    payments, total = await repo.get_by_user_id(current_user.id, pagination.skip, pagination.limit)
    return PaginatedResponse(
        data=[PaymentResponse.model_validate(p) for p in payments],
        pagination=pagination.meta(total),
    )


# ── GET /api/v1/payments/{payment_id} ────────────────────────────────────────
@router.get(
    "/{payment_id}",
    response_model=PaymentResponse,
    summary="Get payment details",
)
async def get_payment(
    payment_id: int = Path(..., ge=1),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> PaymentResponse:
    from app.repositories.payment_repository import PaymentRepository
    from app.exceptions.custom import NotFoundException, ForbiddenException
    repo = PaymentRepository(db)
    payment = await repo.get_with_details(payment_id)
    if not payment:
        raise NotFoundException("Payment", payment_id)
    from app.utils.constants import UserRole
    if payment.user_id != current_user.id and current_user.role not in (UserRole.ADMIN, UserRole.SUPER_ADMIN):
        raise ForbiddenException()
    return PaymentResponse.model_validate(payment)


# ── GET /api/v1/payments/{payment_id}/transactions ───────────────────────────
@router.get(
    "/{payment_id}/transactions",
    response_model=List[TransactionResponse],
    summary="Get transaction history for a payment",
)
async def get_transactions(
    payment_id: int = Path(..., ge=1),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> List[TransactionResponse]:
    from app.repositories.payment_repository import PaymentRepository
    from app.exceptions.custom import NotFoundException, ForbiddenException
    repo = PaymentRepository(db)
    payment = await repo.get_with_details(payment_id)
    if not payment:
        raise NotFoundException("Payment", payment_id)
    from app.utils.constants import UserRole
    if payment.user_id != current_user.id and current_user.role not in (UserRole.ADMIN, UserRole.SUPER_ADMIN):
        raise ForbiddenException()
    return [TransactionResponse.model_validate(t) for t in payment.transactions]


# ── GET /api/v1/payments/orders/{order_id}/invoice ───────────────────────────
@router.get(
    "/orders/{order_id}/invoice",
    response_model=InvoiceResponse,
    summary="Get invoice for an order",
)
async def get_invoice(
    order_id: int = Path(..., ge=1),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> InvoiceResponse:
    from app.repositories.payment_repository import InvoiceRepository
    from app.exceptions.custom import NotFoundException
    repo = InvoiceRepository(db)
    invoice = await repo.get_by_order_id(order_id)
    if not invoice:
        raise NotFoundException("Invoice")
    return InvoiceResponse.model_validate(invoice)


# ── GET /api/v1/payments/orders/{order_id}/receipt ───────────────────────────
@router.get(
    "/orders/{order_id}/receipt",
    response_model=ReceiptResponse,
    summary="Get receipt for an order",
)
async def get_receipt(
    order_id: int = Path(..., ge=1),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> ReceiptResponse:
    from app.repositories.payment_repository import ReceiptRepository
    from app.exceptions.custom import NotFoundException
    repo = ReceiptRepository(db)
    receipt = await repo.get_by_order_id(order_id)
    if not receipt:
        raise NotFoundException("Receipt")
    return ReceiptResponse.model_validate(receipt)


# ── POST /api/v1/payments/{payment_id}/refund ────────────────────────────────
@router.post(
    "/{payment_id}/refund",
    response_model=PaymentResponse,
    summary="Request a refund (admin or customer for cancelled orders)",
)
async def request_refund(
    payment_id: int = Path(..., ge=1),
    body: RefundRequest = ...,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> PaymentResponse:
    """
    **Request Body:**
    ```json
    {
        "reason": "Order was cancelled before pickup",
        "amount": null
    }
    ```
    Set `amount` to `null` to request a full refund.
    """
    service = PaymentService(db)
    payment = await service.process_refund(payment_id, body, current_user)
    return PaymentResponse.model_validate(payment)


# ── POST /api/v1/payments/webhooks/stripe ────────────────────────────────────
@router.post(
    "/webhooks/stripe",
    include_in_schema=False,
    summary="Stripe payment webhook",
)
async def stripe_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Handles Stripe payment confirmation webhooks."""
    service = PaymentService(db)
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")
    await service.handle_stripe_webhook(payload, sig_header)
    return {"received": True}


# ── POST /api/v1/payments/webhooks/orange-money ──────────────────────────────
@router.post(
    "/webhooks/orange-money",
    include_in_schema=False,
    summary="Orange Money payment webhook",
)
async def orange_money_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict:
    service = PaymentService(db)
    data = await request.json()
    await service.handle_orange_money_webhook(data)
    return {"received": True}


# ── POST /api/v1/payments/webhooks/afrimoney ─────────────────────────────────
@router.post(
    "/webhooks/afrimoney",
    include_in_schema=False,
    summary="Afrimoney payment webhook",
)
async def afrimoney_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict:
    service = PaymentService(db)
    data = await request.json()
    await service.handle_afrimoney_webhook(data)
    return {"received": True}
