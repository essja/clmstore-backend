"""
CLMStore — Rider Service
Handles rider registration, profile management, document uploads, earnings, and withdrawals.
"""
from __future__ import annotations

from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions.custom import NotFoundException, BusinessRuleException, ConflictException, ForbiddenException
from app.models.rider import RiderProfile, RiderDocument, RiderEarning, RiderWithdrawal
from app.repositories.rider_repository import (
    RiderProfileRepository,
    RiderDocumentRepository,
    RiderEarningRepository,
    RiderWithdrawalRepository,
)
from app.repositories.user_repository import UserRepository
from app.schemas.rider import RiderProfileRegisterRequest, RiderProfileUpdateRequest, RiderWithdrawalRequest


class RiderService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.rider_repo = RiderProfileRepository(db)
        self.doc_repo = RiderDocumentRepository(db)
        self.earning_repo = RiderEarningRepository(db)
        self.withdrawal_repo = RiderWithdrawalRepository(db)
        self.user_repo = UserRepository(db)

    # ── Core profile ──────────────────────────────────────────────────────────

    async def register_rider(self, user_id: int, schema: RiderProfileRegisterRequest) -> RiderProfile:
        existing = await self.rider_repo.get_by_user(user_id)
        if existing:
            raise ConflictException("Rider profile already exists for this user")
        profile = RiderProfile(
            user_id=user_id,
            vehicle_type=schema.vehicle_type,
            vehicle_plate=schema.vehicle_plate,
            vehicle_model=schema.vehicle_model,
            vehicle_color=schema.vehicle_color,
            is_available=False,
            is_verified=False,
        )
        return await self.rider_repo.create(profile)

    # Router-facing aliases
    async def create_profile(self, user_id: int, schema: RiderProfileRegisterRequest) -> RiderProfile:
        return await self.register_rider(user_id, schema)

    async def get_rider_profile(self, user_id: int) -> RiderProfile:
        profile = await self.rider_repo.get_by_user(user_id)
        if not profile:
            raise NotFoundException("Rider profile")
        return profile

    async def get_profile_by_user_id(self, user_id: int) -> RiderProfile:
        return await self.get_rider_profile(user_id)

    async def update_rider_profile(self, user_id: int, schema: RiderProfileUpdateRequest) -> RiderProfile:
        profile = await self.get_rider_profile(user_id)
        return await self.rider_repo.update(profile, schema)

    async def update_profile(self, user_id: int, schema: RiderProfileUpdateRequest) -> RiderProfile:
        return await self.update_rider_profile(user_id, schema)

    # ── Availability ──────────────────────────────────────────────────────────

    async def toggle_availability(self, user_id: int, is_available: bool) -> RiderProfile:
        profile = await self.get_rider_profile(user_id)
        if not profile.is_verified and is_available:
            raise BusinessRuleException("Your rider account is not verified by admin yet.")
        profile.is_available = is_available
        self.db.add(profile)
        return profile

    async def set_availability(self, user_id: int, is_available: bool) -> RiderProfile:
        return await self.toggle_availability(user_id, is_available)

    # ── Documents ─────────────────────────────────────────────────────────────

    async def upload_document(
        self, user_id: int, doc_type: str, file_url: str, filename: Optional[str] = None
    ) -> RiderDocument:
        profile = await self.get_rider_profile(user_id)
        doc = RiderDocument(
            rider_id=profile.id,
            doc_type=doc_type,
            file_url=file_url,
            file_name=filename,
            is_verified=False,
        )
        return await self.doc_repo.create(doc)

    async def list_documents(self, user_id: int) -> List[RiderDocument]:
        profile = await self.get_rider_profile(user_id)
        return await self.doc_repo.get_by_rider(profile.id)

    # ── Earnings ──────────────────────────────────────────────────────────────

    async def get_earnings(
        self, user_id: int, skip: int = 0, limit: int = 20
    ) -> tuple[List[RiderEarning], int]:
        profile = await self.get_rider_profile(user_id)
        all_earnings = await self.earning_repo.get_by_rider(profile.id)
        total = len(all_earnings)
        return all_earnings[skip : skip + limit], total

    async def get_earnings_summary(self, user_id: int) -> dict:
        profile = await self.get_rider_profile(user_id)
        from sqlalchemy import select, func
        from app.utils.constants import EarningsStatus
        pending_res = await self.db.execute(
            select(func.sum(RiderEarning.net_earning)).filter(
                RiderEarning.rider_id == profile.id,
                RiderEarning.status == EarningsStatus.PENDING,
            )
        )
        pending = float(pending_res.scalar() or 0)
        avg = (
            round(profile.total_earnings / profile.total_deliveries, 2)
            if profile.total_deliveries > 0
            else 0.0
        )
        return {
            "total_earnings": profile.total_earnings,
            "current_balance": profile.current_balance,
            "pending_earnings": pending,
            "total_deliveries": profile.total_deliveries,
            "average_per_delivery": avg,
        }

    # ── Withdrawals ───────────────────────────────────────────────────────────

    async def request_withdrawal(self, user_id: int, schema: RiderWithdrawalRequest) -> RiderWithdrawal:
        profile = await self.get_rider_profile(user_id)
        if not profile.is_verified:
            raise BusinessRuleException("Account must be verified to withdraw earnings")
        if profile.current_balance < schema.amount:
            raise BusinessRuleException("Insufficient balance for withdrawal request")
        profile.current_balance -= schema.amount
        self.db.add(profile)
        withdrawal = RiderWithdrawal(
            rider_id=profile.id,
            amount=schema.amount,
            status="pending",
            payment_method=schema.payment_method,
            payment_details=schema.payment_details,
        )
        await self.withdrawal_repo.create(withdrawal)
        await self.db.flush()
        return withdrawal

    async def get_withdrawals(
        self, user_id: int, skip: int = 0, limit: int = 20
    ) -> tuple[List[RiderWithdrawal], int]:
        profile = await self.get_rider_profile(user_id)
        all_w = await self.withdrawal_repo.get_by_rider(profile.id)
        total = len(all_w)
        return all_w[skip : skip + limit], total

    # ── Admin actions ─────────────────────────────────────────────────────────

    async def verify_rider(self, rider_profile_id: int, admin_id: int) -> RiderProfile:
        profile = await self.rider_repo.get(rider_profile_id)
        if not profile:
            raise NotFoundException("Rider profile", rider_profile_id)
        profile.is_verified = True
        self.db.add(profile)
        return profile

    async def approve_withdrawal(
        self, withdrawal_id: int, admin_id: int, transaction_reference: Optional[str] = None
    ) -> RiderWithdrawal:
        from datetime import datetime, timezone
        withdrawal = await self.withdrawal_repo.get(withdrawal_id)
        if not withdrawal:
            raise NotFoundException("Withdrawal", withdrawal_id)
        if withdrawal.status != "pending":
            raise BusinessRuleException("Only pending withdrawals can be approved")
        withdrawal.status = "approved"
        withdrawal.processed_by = admin_id
        withdrawal.processed_at = datetime.now(timezone.utc).isoformat()
        if transaction_reference:
            withdrawal.transaction_reference = transaction_reference
        self.db.add(withdrawal)
        return withdrawal

    async def reject_withdrawal(
        self, withdrawal_id: int, admin_id: int, reason: str
    ) -> RiderWithdrawal:
        from datetime import datetime, timezone
        withdrawal = await self.withdrawal_repo.get(withdrawal_id)
        if not withdrawal:
            raise NotFoundException("Withdrawal", withdrawal_id)
        if withdrawal.status != "pending":
            raise BusinessRuleException("Only pending withdrawals can be rejected")
        # Refund balance to rider
        profile = await self.rider_repo.get(withdrawal.rider_id)
        if profile:
            profile.current_balance += withdrawal.amount
            self.db.add(profile)
        withdrawal.status = "rejected"
        withdrawal.notes = reason
        withdrawal.processed_by = admin_id
        withdrawal.processed_at = datetime.now(timezone.utc).isoformat()
        self.db.add(withdrawal)
        return withdrawal
