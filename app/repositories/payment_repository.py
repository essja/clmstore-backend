"""
CLMStore — Payment Repository
"""
from __future__ import annotations

from typing import List, Optional

from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.payment import Payment, Transaction, Invoice, Receipt
from app.repositories.base import BaseRepository
from app.utils.constants import PaymentStatus


class PaymentRepository(BaseRepository[Payment]):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(Payment, db)

    async def get_by_order(self, order_id: int) -> Optional[Payment]:
        result = await self.db.execute(
            select(Payment)
            .filter(Payment.order_id == order_id)
            .options(
                selectinload(Payment.transactions),
                selectinload(Payment.invoice),
                selectinload(Payment.receipt),
            )
        )
        return result.scalars().first()

    async def get_by_reference(self, reference: str) -> Optional[Payment]:
        result = await self.db.execute(
            select(Payment)
            .filter(Payment.provider_ref == reference)
            .options(selectinload(Payment.transactions))
        )
        return result.scalars().first()

    async def get_with_details(self, payment_id: int) -> Optional[Payment]:
        result = await self.db.execute(
            select(Payment)
            .filter(Payment.id == payment_id)
            .options(
                selectinload(Payment.transactions),
                selectinload(Payment.invoice),
                selectinload(Payment.receipt),
            )
        )
        return result.scalars().first()

    async def get_by_user_id(
        self, user_id: int, skip: int = 0, limit: int = 20
    ) -> tuple[List[Payment], int]:
        count_res = await self.db.execute(
            select(func.count(Payment.id)).filter(Payment.user_id == user_id)
        )
        total = count_res.scalar() or 0
        stmt = (
            select(Payment)
            .filter(Payment.user_id == user_id)
            .options(
                selectinload(Payment.transactions),
                selectinload(Payment.invoice),
                selectinload(Payment.receipt),
            )
            .order_by(Payment.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all()), total

    async def get_history_by_user(
        self,
        user_id: int,
        status: Optional[PaymentStatus] = None,
        skip: int = 0,
        limit: int = 20,
    ) -> List[Payment]:
        stmt = select(Payment).filter(Payment.user_id == user_id)
        if status is not None:
            stmt = stmt.filter(Payment.status == status)
        stmt = stmt.order_by(Payment.created_at.desc()).offset(skip).limit(limit)

        result = await self.db.execute(stmt)
        return list(result.scalars().all())


class TransactionRepository(BaseRepository[Transaction]):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(Transaction, db)


class InvoiceRepository(BaseRepository[Invoice]):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(Invoice, db)

    async def get_by_order(self, order_id: int) -> Optional[Invoice]:
        result = await self.db.execute(select(Invoice).filter(Invoice.order_id == order_id))
        return result.scalars().first()

    async def get_by_order_id(self, order_id: int) -> Optional[Invoice]:
        return await self.get_by_order(order_id)


class ReceiptRepository(BaseRepository[Receipt]):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(Receipt, db)

    async def get_by_order(self, order_id: int) -> Optional[Receipt]:
        result = await self.db.execute(select(Receipt).filter(Receipt.order_id == order_id))
        return result.scalars().first()

    async def get_by_order_id(self, order_id: int) -> Optional[Receipt]:
        return await self.get_by_order(order_id)
