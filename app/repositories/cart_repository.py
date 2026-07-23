"""
CLMStore — Cart Repository
"""
from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.cart import Cart, CartItem
from app.repositories.base import BaseRepository


class CartRepository(BaseRepository[Cart]):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(Cart, db)

    async def get_by_user_id(self, user_id: int) -> Optional[Cart]:
        result = await self.db.execute(
            select(Cart)
            .filter(Cart.user_id == user_id, Cart.is_active == True)
            .options(
                selectinload(Cart.items).selectinload(CartItem.menu_item),
                selectinload(Cart.items).selectinload(CartItem.variant),
                selectinload(Cart.coupon),
            )
        )
        return result.scalars().first()

    async def get_by_session_id(self, session_id: str) -> Optional[Cart]:
        result = await self.db.execute(
            select(Cart)
            .filter(Cart.session_id == session_id, Cart.is_active == True)
            .options(
                selectinload(Cart.items).selectinload(CartItem.menu_item),
                selectinload(Cart.items).selectinload(CartItem.variant),
                selectinload(Cart.coupon),
            )
        )
        return result.scalars().first()


class CartItemRepository(BaseRepository[CartItem]):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(CartItem, db)

    async def get_item_in_cart(
        self,
        cart_id: int,
        menu_item_id: int,
        variant_id: Optional[int] = None,
    ) -> Optional[CartItem]:
        stmt = select(CartItem).filter(
            CartItem.cart_id == cart_id,
            CartItem.menu_item_id == menu_item_id,
        )
        if variant_id is not None:
            stmt = stmt.filter(CartItem.variant_id == variant_id)
        else:
            stmt = stmt.filter(CartItem.variant_id == None)

        result = await self.db.execute(stmt)
        return result.scalars().first()
