"""
CLMStore — Payment Service
Implements Strategy Pattern for payment providers (COD, Stripe, PayPal, Orange Money, Afrimoney).
"""
from __future__ import annotations

import abc
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Type

import httpx
import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions.custom import PaymentException, NotFoundException, BusinessRuleException, ForbiddenException
from app.models.payment import Payment, Transaction, Invoice, Receipt
from app.schemas.payment import PaymentInitiateRequest, PaymentVerifyResponse, RefundRequest
from app.repositories.payment_repository import (
    PaymentRepository,
    TransactionRepository,
    InvoiceRepository,
    ReceiptRepository,
)
from app.repositories.order_repository import OrderRepository
from app.utils.constants import PaymentProvider, PaymentStatus, TransactionType

logger = structlog.get_logger()


# ── Provider Strategy Interface ──────────────────────────────────────────────
class PaymentProviderStrategy(abc.ABC):
    @abc.abstractmethod
    async def initiate_payment(
        self, order_id: int, amount: float, currency: str, details: Optional[dict] = None
    ) -> Dict[str, Any]:
        """Initiate payment and return provider-specific transaction reference details."""
        pass

    @abc.abstractmethod
    async def verify_payment(self, reference: str) -> bool:
        """Query provider API to verify if payment succeeded."""
        pass

    @abc.abstractmethod
    async def process_refund(self, reference: str, amount: float) -> bool:
        """Refund a previous charge."""
        pass


# ── Cash On Delivery Strategy ────────────────────────────────────────────────
class CashOnDeliveryStrategy(PaymentProviderStrategy):
    async def initiate_payment(
        self, order_id: int, amount: float, currency: str, details: Optional[dict] = None
    ) -> Dict[str, Any]:
        return {
            "status": "pending",
            "provider_ref": f"COD-{uuid.uuid4().hex[:12].upper()}",
            "message": "Payment will be collected on delivery",
            "redirect_url": None,
        }

    async def verify_payment(self, reference: str) -> bool:
        # Cash on Delivery starts pending and completes upon delivery completion
        return True

    async def process_refund(self, reference: str, amount: float) -> bool:
        return True


# ── Orange Money Strategy (Sierra Leone Webpay) ───────────────────────────────
class OrangeMoneyStrategy(PaymentProviderStrategy):
    """
    Orange Money Sierra Leone Webpay integration.
    Docs: https://developer.orange.com/apis/orange-money-webpay-sl
    Credentials: ORANGE_MONEY_API_KEY, ORANGE_MONEY_MERCHANT_ID in .env
    """

    async def initiate_payment(
        self, order_id: int, amount: float, currency: str, details: Optional[dict] = None
    ) -> Dict[str, Any]:
        from app.config.settings import settings
        ref = f"CLM-OM-{order_id}-{uuid.uuid4().hex[:8].upper()}"

        if not settings.ORANGE_MONEY_API_KEY or not settings.ORANGE_MONEY_MERCHANT_ID:
            logger.warning("orange_money_credentials_missing")
            return {
                "status": "processing",
                "provider_ref": ref,
                "redirect_url": None,
                "message": "Orange Money not configured — set ORANGE_MONEY_API_KEY and ORANGE_MONEY_MERCHANT_ID",
            }

        payload = {
            "merchant_key": settings.ORANGE_MONEY_API_KEY,
            "currency": currency,
            "order_id": ref,
            "amount": int(amount),
            "return_url": f"{settings.FRONTEND_URL}/payment/success",
            "cancel_url": f"{settings.FRONTEND_URL}/payment/cancelled",
            "notif_url": f"https://api.clmstore.sl/api/v1/payments/webhooks/orange-money",
        }
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(
                    f"{settings.ORANGE_MONEY_BASE_URL}/webpayment",
                    json=payload,
                    headers={
                        "Authorization": f"Bearer {settings.ORANGE_MONEY_API_KEY}",
                        "Content-Type": "application/json",
                    },
                )
            data = response.json()
            if response.status_code == 200 and data.get("status") == "SUCCESS":
                return {
                    "status": "processing",
                    "provider_ref": data.get("pay_token", ref),
                    "redirect_url": data.get("payment_url"),
                    "message": "Redirecting to Orange Money payment page",
                }
            else:
                raise PaymentException(f"Orange Money error: {data.get('message', response.text)}")
        except httpx.RequestError as e:
            raise PaymentException(f"Orange Money API unreachable: {e}")

    async def verify_payment(self, reference: str) -> bool:
        from app.config.settings import settings
        if not settings.ORANGE_MONEY_API_KEY:
            return False
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"{settings.ORANGE_MONEY_BASE_URL}/paymentstatus",
                    params={"pay_token": reference},
                    headers={"Authorization": f"Bearer {settings.ORANGE_MONEY_API_KEY}"},
                )
            data = response.json()
            return data.get("status") in ("SUCCESS", "SUCCESSFUL", "COMPLETED")
        except Exception as e:
            logger.error("orange_money_verify_failed", error=str(e), reference=reference)
            return False

    async def process_refund(self, reference: str, amount: float) -> bool:
        # Orange Money SL does not yet expose a programmatic refund API.
        # Refunds are processed manually through the merchant portal.
        logger.info("orange_money_refund_manual", reference=reference, amount=amount)
        return True


# ── Afrimoney Strategy (Sierra Leone USSD Push) ───────────────────────────────
class AfrimoneyStrategy(PaymentProviderStrategy):
    """
    Afrimoney Sierra Leone merchant API — sends a USSD push to the customer's phone.
    Docs/onboarding: contact Afrimoney merchant support.
    Credentials: AFRIMONEY_API_KEY in .env
    """

    async def initiate_payment(
        self, order_id: int, amount: float, currency: str, details: Optional[dict] = None
    ) -> Dict[str, Any]:
        from app.config.settings import settings
        ref = f"CLM-AM-{order_id}-{uuid.uuid4().hex[:8].upper()}"
        phone = (details or {}).get("phone_number", "")

        if not settings.AFRIMONEY_API_KEY:
            logger.warning("afrimoney_credentials_missing")
            return {
                "status": "processing",
                "provider_ref": ref,
                "redirect_url": None,
                "message": "Afrimoney not configured — set AFRIMONEY_API_KEY in .env",
            }

        if not phone:
            raise PaymentException("phone_number is required for Afrimoney payments")

        payload = {
            "amount": str(int(amount)),
            "currency": currency,
            "externalId": ref,
            "payer": {"partyIdType": "MSISDN", "partyId": phone.lstrip("+")},
            "payerMessage": f"CLMStore order #{order_id}",
            "payeeNote": f"CLMStore order #{order_id}",
        }
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(
                    f"{settings.AFRIMONEY_BASE_URL}/requesttopay",
                    json=payload,
                    headers={
                        "Authorization": f"Bearer {settings.AFRIMONEY_API_KEY}",
                        "X-Reference-Id": ref,
                        "Content-Type": "application/json",
                    },
                )
            if response.status_code in (200, 202):
                return {
                    "status": "processing",
                    "provider_ref": ref,
                    "redirect_url": None,
                    "message": "USSD push sent to customer's Afrimoney wallet — awaiting approval",
                }
            else:
                raise PaymentException(f"Afrimoney error: {response.text}")
        except httpx.RequestError as e:
            raise PaymentException(f"Afrimoney API unreachable: {e}")

    async def verify_payment(self, reference: str) -> bool:
        from app.config.settings import settings
        if not settings.AFRIMONEY_API_KEY:
            return False
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"{settings.AFRIMONEY_BASE_URL}/requesttopay/{reference}",
                    headers={"Authorization": f"Bearer {settings.AFRIMONEY_API_KEY}"},
                )
            data = response.json()
            return data.get("status") in ("SUCCESSFUL", "SUCCESS", "COMPLETED")
        except Exception as e:
            logger.error("afrimoney_verify_failed", error=str(e), reference=reference)
            return False

    async def process_refund(self, reference: str, amount: float) -> bool:
        # Afrimoney refunds processed via merchant portal or their support API.
        logger.info("afrimoney_refund_manual", reference=reference, amount=amount)
        return True


# ── Stripe Card Strategy ─────────────────────────────────────────────────────
class StripeStrategy(PaymentProviderStrategy):
    """
    Real Stripe integration using PaymentIntents.
    The frontend receives client_secret and calls stripe.confirmPayment().
    Credentials: STRIPE_SECRET_KEY, STRIPE_WEBHOOK_SECRET in .env
    Note: SLL is a zero-decimal currency in Stripe — amount is passed as-is (no *100).
    """

    def _get_stripe(self):
        import stripe as _stripe
        from app.config.settings import settings
        if not settings.STRIPE_SECRET_KEY:
            raise PaymentException("STRIPE_SECRET_KEY is not configured")
        _stripe.api_key = settings.STRIPE_SECRET_KEY
        return _stripe

    async def initiate_payment(
        self, order_id: int, amount: float, currency: str, details: Optional[dict] = None
    ) -> Dict[str, Any]:
        import asyncio
        stripe = self._get_stripe()
        payment_method_id = (details or {}).get("payment_method_id")

        def _create():
            params: Dict[str, Any] = {
                "amount": int(amount),  # SLL is zero-decimal in Stripe
                "currency": currency.lower(),
                "metadata": {"order_id": str(order_id), "platform": "CLMStore"},
                "automatic_payment_methods": {"enabled": True},
            }
            if payment_method_id:
                params["payment_method"] = payment_method_id
                params["confirm"] = True
            return stripe.PaymentIntent.create(**params)

        try:
            intent = await asyncio.to_thread(_create)
            return {
                "status": "processing",
                "provider_ref": intent.id,
                "client_secret": intent.client_secret,
                "redirect_url": None,
                "message": "Complete payment on the frontend using the client_secret",
            }
        except stripe.error.CardError as e:
            raise PaymentException(f"Card declined: {e.user_message}")
        except stripe.error.StripeError as e:
            raise PaymentException(f"Stripe error: {e.user_message}")

    async def verify_payment(self, reference: str) -> bool:
        import asyncio
        stripe = self._get_stripe()

        def _retrieve():
            return stripe.PaymentIntent.retrieve(reference)

        try:
            intent = await asyncio.to_thread(_retrieve)
            return intent.status == "succeeded"
        except Exception as e:
            logger.error("stripe_verify_failed", error=str(e), reference=reference)
            return False

    async def process_refund(self, reference: str, amount: float) -> bool:
        import asyncio
        stripe = self._get_stripe()

        def _refund():
            return stripe.Refund.create(
                payment_intent=reference,
                amount=int(amount),  # SLL zero-decimal
            )

        try:
            refund = await asyncio.to_thread(_refund)
            return refund.status in ("succeeded", "pending")
        except Exception as e:
            logger.error("stripe_refund_failed", error=str(e), reference=reference)
            return False


# ── Strategy Registry ────────────────────────────────────────────────────────
PROVIDERS: Dict[PaymentProvider, Type[PaymentProviderStrategy]] = {
    PaymentProvider.CASH: CashOnDeliveryStrategy,
    PaymentProvider.ORANGE_MONEY: OrangeMoneyStrategy,
    PaymentProvider.AFRIMONEY: AfrimoneyStrategy,
    PaymentProvider.STRIPE: StripeStrategy,
    PaymentProvider.PAYPAL: CashOnDeliveryStrategy,  # PayPal not yet integrated; treated as COD
    PaymentProvider.VISA: StripeStrategy,            # card providers map to Stripe
    PaymentProvider.MASTERCARD: StripeStrategy,
}


# ── Payment Service Interface ────────────────────────────────────────────────
class PaymentService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.payment_repo = PaymentRepository(db)
        self.trans_repo = TransactionRepository(db)
        self.invoice_repo = InvoiceRepository(db)
        self.receipt_repo = ReceiptRepository(db)
        self.order_repo = OrderRepository(db)

    def _get_provider(self, provider_name: PaymentProvider) -> PaymentProviderStrategy:
        strategy_class = PROVIDERS.get(provider_name)
        if not strategy_class:
            raise PaymentException(f"Unsupported payment provider: {provider_name}")
        return strategy_class()

    async def initiate_order_payment(
        self, order_id: int, provider_name: PaymentProvider, details: Optional[dict] = None
    ) -> Dict[str, Any]:
        """Initiate payment and save Payment entity in DB."""
        order = await self.order_repo.get(order_id)
        if not order:
            raise NotFoundException("Order")

        provider = self._get_provider(provider_name)
        result = await provider.initiate_payment(
            order_id=order.id,
            amount=order.total_amount,
            currency=order.currency,
            details=details,
        )

        # Create or update Payment entry
        payment = await self.payment_repo.get_by_order(order_id)
        if not payment:
            payment = Payment(
                order_id=order.id,
                user_id=order.user_id,
                provider=provider_name,
                provider_ref=result["provider_ref"],
                amount=order.total_amount,
                currency=order.currency,
                status=PaymentStatus.PENDING,
            )
            await self.payment_repo.create(payment)
        else:
            payment.provider = provider_name
            payment.provider_ref = result["provider_ref"]
            payment.status = PaymentStatus.PENDING
            self.db.add(payment)

        await self.db.flush()
        result["payment_id"] = payment.id
        return result

    # ── Public API methods called by the router ──────────────────────────────

    async def initiate_payment(self, body: PaymentInitiateRequest, user_id: int) -> Payment:
        """Router-facing: initiate payment and return the Payment ORM object."""
        result = await self.initiate_order_payment(
            order_id=body.order_id,
            provider_name=body.provider,
            details=body.payment_details,
        )
        payment_id = result["payment_id"]
        payment = await self.payment_repo.get_with_details(payment_id)
        if not payment:
            raise NotFoundException("Payment")
        # Verify ownership
        if payment.user_id != user_id:
            raise ForbiddenException("Order does not belong to you")
        return payment

    async def verify_payment(self, payment_id: int, user_id: int) -> PaymentVerifyResponse:
        """Router-facing: look up payment by ID, verify with provider, return structured response."""
        payment = await self.payment_repo.get_with_details(payment_id)
        if not payment:
            raise NotFoundException("Payment", payment_id)
        if payment.user_id != user_id:
            raise ForbiddenException("Payment does not belong to you")

        if payment.status == PaymentStatus.COMPLETED:
            return PaymentVerifyResponse(
                success=True,
                status=PaymentStatus.COMPLETED,
                transaction_id=payment.provider_ref,
                message="Payment already completed.",
            )

        reference = payment.provider_ref or ""
        success = await self.verify_and_complete_payment(reference)

        return PaymentVerifyResponse(
            success=success,
            status=PaymentStatus.COMPLETED if success else PaymentStatus.FAILED,
            transaction_id=reference or None,
            message="Payment verified successfully." if success else "Payment verification failed.",
        )

    async def process_refund(self, payment_id: int, body: RefundRequest, current_user: "User") -> Payment:
        """Router-facing: process a full or partial refund."""
        from app.utils.constants import UserRole
        from app.models.user import User

        payment = await self.payment_repo.get_with_details(payment_id)
        if not payment:
            raise NotFoundException("Payment", payment_id)
        if payment.user_id != current_user.id and current_user.role not in (UserRole.ADMIN, UserRole.SUPER_ADMIN):
            raise ForbiddenException("You cannot refund this payment")
        if payment.status != PaymentStatus.COMPLETED:
            raise BusinessRuleException("Only completed payments can be refunded")

        refund_amount = body.amount if body.amount is not None else (payment.amount - payment.refunded_amount)
        remaining = payment.amount - payment.refunded_amount
        if refund_amount > remaining:
            raise BusinessRuleException(f"Refund amount exceeds refundable balance of {remaining}")

        provider = self._get_provider(payment.provider)
        success = await provider.process_refund(payment.provider_ref or "", refund_amount)

        if success:
            payment.refunded_amount += refund_amount
            if payment.refunded_amount >= payment.amount:
                payment.status = PaymentStatus.REFUNDED
            trans = Transaction(
                payment_id=payment.id,
                type=TransactionType.REFUND,
                amount=refund_amount,
                currency=payment.currency,
                status="completed",
                reference=payment.provider_ref,
                notes=body.reason,
            )
            await self.trans_repo.create(trans)
            self.db.add(payment)
            await self.db.flush()
        else:
            raise PaymentException("Refund was rejected by the payment provider")

        return payment

    async def handle_stripe_webhook(self, payload: bytes, sig_header: str) -> None:
        """Process Stripe webhook — verify signature and update payment status."""
        import json
        import stripe
        from app.config.settings import settings

        # Verify webhook signature to prevent spoofed events
        if settings.STRIPE_WEBHOOK_SECRET and sig_header:
            try:
                event = stripe.Webhook.construct_event(
                    payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
                )
                data = event
            except stripe.error.SignatureVerificationError:
                logger.warning("stripe_webhook_invalid_signature")
                return
            except Exception:
                logger.warning("stripe_webhook_construct_failed")
                return
        else:
            try:
                data = json.loads(payload)
            except Exception:
                logger.warning("stripe_webhook_invalid_payload")
                return

        event_type = data.get("type", "")
        if event_type == "payment_intent.succeeded":
            provider_ref = data.get("data", {}).get("object", {}).get("id")
            if provider_ref:
                await self.verify_and_complete_payment(provider_ref)
        elif event_type in ("payment_intent.payment_failed", "charge.failed"):
            provider_ref = data.get("data", {}).get("object", {}).get("id")
            if provider_ref:
                payment = await self.payment_repo.get_by_reference(provider_ref)
                if payment:
                    payment.status = PaymentStatus.FAILED
                    payment.failure_reason = data.get("data", {}).get("object", {}).get("last_payment_error", {}).get("message")
                    self.db.add(payment)
                    await self.db.flush()

    async def handle_orange_money_webhook(self, data: dict) -> None:
        """Process Orange Money callback — update payment on success/failure."""
        status_str = str(data.get("status", "")).lower()
        provider_ref = data.get("reference") or data.get("txnid") or data.get("transactionId")
        if not provider_ref:
            logger.warning("orange_money_webhook_missing_reference", data=data)
            return

        if status_str in ("success", "successful", "completed"):
            await self.verify_and_complete_payment(provider_ref)
        elif status_str in ("failed", "cancelled", "rejected"):
            payment = await self.payment_repo.get_by_reference(provider_ref)
            if payment:
                payment.status = PaymentStatus.FAILED
                payment.failure_reason = data.get("message", "Orange Money payment failed")
                self.db.add(payment)
                await self.db.flush()

    async def handle_afrimoney_webhook(self, data: dict) -> None:
        """Process Afrimoney callback — update payment on success/failure."""
        status_str = str(data.get("status", "")).lower()
        provider_ref = data.get("reference") or data.get("transId") or data.get("transaction_id")
        if not provider_ref:
            logger.warning("afrimoney_webhook_missing_reference", data=data)
            return

        if status_str in ("success", "successful", "approved"):
            await self.verify_and_complete_payment(provider_ref)
        elif status_str in ("failed", "declined", "cancelled"):
            payment = await self.payment_repo.get_by_reference(provider_ref)
            if payment:
                payment.status = PaymentStatus.FAILED
                payment.failure_reason = data.get("message", "Afrimoney payment failed")
                self.db.add(payment)
                await self.db.flush()

    # ── Internal implementation ───────────────────────────────────────────────

    async def verify_and_complete_payment(self, reference: str) -> bool:
        """Verify dynamic status of payment and generate receipts/invoices if succeeded."""
        payment = await self.payment_repo.get_by_reference(reference)
        if not payment:
            raise NotFoundException("Payment record")

        if payment.status == PaymentStatus.COMPLETED:
            return True

        provider = self._get_provider(payment.provider)
        success = await provider.verify_payment(reference)

        if success:
            payment.status = PaymentStatus.COMPLETED
            self.db.add(payment)

            # Generate Transaction record
            trans = Transaction(
                payment_id=payment.id,
                type=TransactionType.CHARGE,
                amount=payment.amount,
                currency=payment.currency,
                status="completed",
                reference=reference,
            )
            await self.trans_repo.create(trans)

            # Update Order payment state
            order = await self.order_repo.get_with_details(payment.order_id)
            if order:
                order.payment_status = "paid"
                self.db.add(order)

            # Generate Invoice PDF
            inv_num = f"INV-{datetime.now().strftime('%Y%m%d')}-{payment.id:04d}"
            inv_url = f"/static/uploads/invoices/{inv_num}.pdf"
            if order:
                try:
                    from app.services.pdf_service import generate_invoice_pdf, save_pdf
                    pdf_bytes = generate_invoice_pdf(order, inv_num)
                    inv_url = await save_pdf(pdf_bytes, f"{inv_num}.pdf", subfolder="invoices")
                except Exception as e:
                    logger.error("invoice_pdf_generation_failed", error=str(e), inv_num=inv_num)

            invoice = Invoice(
                order_id=payment.order_id,
                payment_id=payment.id,
                invoice_number=inv_num,
                pdf_url=inv_url,
            )
            await self.invoice_repo.create(invoice)

            # Generate Receipt PDF
            rec_num = f"REC-{datetime.now().strftime('%Y%m%d')}-{payment.id:04d}"
            rec_url = f"/static/uploads/receipts/{rec_num}.pdf"
            if order:
                try:
                    from app.services.pdf_service import generate_receipt_pdf, save_pdf
                    pdf_bytes = generate_receipt_pdf(order, rec_num, payment)
                    rec_url = await save_pdf(pdf_bytes, f"{rec_num}.pdf", subfolder="receipts")
                except Exception as e:
                    logger.error("receipt_pdf_generation_failed", error=str(e), rec_num=rec_num)

            receipt = Receipt(
                order_id=payment.order_id,
                payment_id=payment.id,
                receipt_number=rec_num,
                pdf_url=rec_url,
            )
            await self.receipt_repo.create(receipt)

            await self.db.flush()
            return True
        else:
            payment.status = PaymentStatus.FAILED
            self.db.add(payment)
            await self.db.flush()
            return False
