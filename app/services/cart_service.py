"""
CLMStore — Cart Service
"""
from __future__ import annotations

from typing import List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions.custom import NotFoundException, BusinessRuleException
from app.models.cart import Cart, CartItem
from app.repositories.cart_repository import CartRepository, CartItemRepository
from app.repositories.menu_repository import MenuItemRepository, MenuItemVariantRepository
from app.repositories.coupon_repository import CouponRepository
from app.schemas.cart import CartItemAddRequest


class CartService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.cart_repo = CartRepository(db)
        self.item_repo = CartItemRepository(db)
        self.menu_repo = MenuItemRepository(db)
        self.variant_repo = MenuItemVariantRepository(db)
        self.coupon_repo = CouponRepository(db)

    async def get_or_create_cart(
        self, user_id: Optional[int] = None, session_id: Optional[str] = None
    ) -> Cart:
        """Fetch active cart or create one if not exists."""
        if not user_id and not session_id:
            raise BusinessRuleException("Either user_id or session_id must be provided")

        if user_id:
            cart = await self.cart_repo.get_by_user_id(user_id)
            if not cart:
                new_cart = Cart(user_id=user_id, is_active=True)
                await self.cart_repo.create(new_cart)
                await self.db.flush()
                # Re-fetch with selectinload so relationships are populated
                cart = await self.cart_repo.get_by_user_id(user_id)
            return cart
        else:
            cart = await self.cart_repo.get_by_session_id(session_id)
            if not cart:
                new_cart = Cart(session_id=session_id, is_active=True)
                await self.cart_repo.create(new_cart)
                await self.db.flush()
                # Re-fetch with selectinload so relationships are populated
                cart = await self.cart_repo.get_by_session_id(session_id)
            return cart

    async def add_item_to_cart(
        self,
        schema: CartItemAddRequest,
        user_id: Optional[int] = None,
        session_id: Optional[str] = None,
    ) -> Cart:
        cart = await self.get_or_create_cart(user_id, session_id)

        # Get menu item details
        menu_item = await self.menu_repo.get(schema.menu_item_id)
        if not menu_item or not menu_item.is_available:
            raise NotFoundException("Menu Item")

        # Handle restaurant restrictions (cannot mix items from different restaurants in one cart)
        if cart.restaurant_id is not None and cart.restaurant_id != menu_item.restaurant_id:
            # If cart has items, reject mixing. Otherwise overwrite restaurant_id
            if len(cart.items) > 0:
                raise BusinessRuleException(
                    "Cannot add items from a different restaurant. Clear your cart first."
                )

        cart.restaurant_id = menu_item.restaurant_id
        self.db.add(cart)

        # Fetch unit price
        unit_price = menu_item.effective_price
        if schema.variant_id:
            variant = await self.variant_repo.get(schema.variant_id)
            if not variant or variant.menu_item_id != menu_item.id or not variant.is_available:
                raise NotFoundException("MenuItemVariant")
            # Apply variant modifier directly to unit price snapshot
            unit_price += variant.price_modifier

        # Check stock limits if applicable
        if menu_item.stock_count is not None:
            if schema.quantity > menu_item.stock_count:
                raise BusinessRuleException("Insufficient stock available")

        # Serialise selected addons
        addons_list = []
        if schema.addons:
            addons_list = [a.model_dump() for a in schema.addons]

        # Check if identical item (same ID, same variant) already exists
        existing_item = await self.item_repo.get_item_in_cart(
            cart.id, schema.menu_item_id, schema.variant_id
        )

        if existing_item:
            # If addons are different, treat as a new item in some systems.
            # But for simplicity, we will merge quantity and update instructions/addons
            new_qty = existing_item.quantity + schema.quantity
            if menu_item.stock_count is not None and new_qty > menu_item.stock_count:
                raise BusinessRuleException("Insufficient stock available")
            existing_item.quantity = new_qty
            existing_item.addons = addons_list
            existing_item.special_instructions = schema.special_instructions
            self.db.add(existing_item)
        else:
            new_item = CartItem(
                cart_id=cart.id,
                menu_item_id=schema.menu_item_id,
                variant_id=schema.variant_id,
                quantity=schema.quantity,
                unit_price=unit_price,
                addons=addons_list,
                special_instructions=schema.special_instructions,
            )
            await self.item_repo.create(new_item)

        await self.db.flush()
        # Reload cart with latest relationships
        return await self.get_or_create_cart(user_id, session_id)

    async def update_cart_item_quantity(
        self,
        cart_item_id: int,
        quantity: int,
        user_id: Optional[int] = None,
        session_id: Optional[str] = None,
    ) -> Cart:
        cart = await self.get_or_create_cart(user_id, session_id)

        item = await self.item_repo.get(cart_item_id)
        if not item or item.cart_id != cart.id:
            raise NotFoundException("Cart Item")

        # Check stock count
        menu_item = await self.menu_repo.get(item.menu_item_id)
        if menu_item and menu_item.stock_count is not None and quantity > menu_item.stock_count:
            raise BusinessRuleException("Insufficient stock available")

        item.quantity = quantity
        self.db.add(item)
        await self.db.flush()

        return await self.get_or_create_cart(user_id, session_id)

    async def remove_cart_item(
        self,
        cart_item_id: int,
        user_id: Optional[int] = None,
        session_id: Optional[str] = None,
    ) -> Cart:
        cart = await self.get_or_create_cart(user_id, session_id)

        item = await self.item_repo.get(cart_item_id)
        if not item or item.cart_id != cart.id:
            raise NotFoundException("Cart Item")

        await self.item_repo.delete(cart_item_id)
        await self.db.flush()

        # If cart is now empty, clear restaurant_id and coupon_id
        # We must reload cart items first
        updated_cart = await self.get_or_create_cart(user_id, session_id)
        if len(updated_cart.items) == 0:
            updated_cart.restaurant_id = None
            updated_cart.coupon_id = None
            self.db.add(updated_cart)
            await self.db.flush()

        return updated_cart

    async def clear_cart(
        self, user_id: Optional[int] = None, session_id: Optional[str] = None
    ) -> None:
        cart = await self.get_or_create_cart(user_id, session_id)
        for item in cart.items:
            await self.item_repo.delete(item.id)
        cart.restaurant_id = None
        cart.coupon_id = None
        self.db.add(cart)
        await self.db.flush()

    async def apply_coupon(
        self,
        user_id: Optional[int] = None,
        code: str = "",
        session_id: Optional[str] = None,
    ) -> Cart:
        cart = await self.get_or_create_cart(user_id, session_id)
        if len(cart.items) == 0:
            raise BusinessRuleException("Cannot apply coupon to an empty cart")

        coupon = await self.coupon_repo.get_by_code(code)
        if not coupon:
            raise NotFoundException("Coupon")

        # Expiration check
        from datetime import datetime, timezone
        if coupon.expires_at < datetime.now(timezone.utc):
            raise BusinessRuleException("Coupon has expired")

        # Restaurant restriction check
        if coupon.restaurant_id is not None and coupon.restaurant_id != cart.restaurant_id:
            raise BusinessRuleException("Coupon is not valid for this restaurant's items")

        # Minimum order value check
        if cart.subtotal < coupon.min_order_value:
            raise BusinessRuleException(
                f"Minimum order subtotal of Le {coupon.min_order_value:,.0f} required"
            )

        cart.coupon_id = coupon.id
        self.db.add(cart)
        await self.db.flush()

        return await self.get_or_create_cart(user_id, session_id)

    async def remove_coupon(
        self, user_id: Optional[int] = None, session_id: Optional[str] = None
    ) -> Cart:
        cart = await self.get_or_create_cart(user_id, session_id)
        cart.coupon_id = None
        self.db.add(cart)
        await self.db.flush()
        return await self.get_or_create_cart(user_id, session_id)

    # Router-facing aliases
    async def add_item(
        self,
        schema: CartItemAddRequest,
        user_id: Optional[int] = None,
        session_id: Optional[str] = None,
    ) -> Cart:
        return await self.add_item_to_cart(schema, user_id, session_id)

    async def update_item_quantity(
        self,
        cart_item_id: int,
        quantity: int,
        user_id: Optional[int] = None,
        session_id: Optional[str] = None,
    ) -> Cart:
        return await self.update_cart_item_quantity(cart_item_id, quantity, user_id, session_id)

    async def remove_item(
        self,
        cart_item_id: int,
        user_id: Optional[int] = None,
        session_id: Optional[str] = None,
    ) -> Cart:
        return await self.remove_cart_item(cart_item_id, user_id, session_id)

    async def merge_guest_cart(self, user_id: int, guest_session_id: str) -> Cart:
        return await self._merge_guest_cart(guest_session_id, user_id)

    async def _merge_guest_cart(self, guest_session_id: str, logged_user_id: int) -> Cart:
        """Merge items from a guest cart into the user's active cart after logging in."""
        guest_cart = await self.cart_repo.get_by_session_id(guest_session_id)
        if not guest_cart or len(guest_cart.items) == 0:
            # Nothing to merge
            return await self.get_or_create_cart(user_id=logged_user_id)

        user_cart = await self.get_or_create_cart(user_id=logged_user_id)

        # If user's cart has items and they are from a different restaurant, guest cart wins or we clear user's cart.
        # Standard behaviour: if user cart has different restaurant, clear it first
        if (
            user_cart.restaurant_id is not None
            and user_cart.restaurant_id != guest_cart.restaurant_id
            and len(user_cart.items) > 0
        ):
            # Clear user cart first
            await self.clear_cart(user_id=logged_user_id)
            # Re-fetch
            user_cart = await self.get_or_create_cart(user_id=logged_user_id)

        user_cart.restaurant_id = guest_cart.restaurant_id
        if guest_cart.coupon_id:
            user_cart.coupon_id = guest_cart.coupon_id
        self.db.add(user_cart)

        for g_item in guest_cart.items:
            # Transfer item
            existing = await self.item_repo.get_item_in_cart(
                user_cart.id, g_item.menu_item_id, g_item.variant_id
            )
            if existing:
                existing.quantity += g_item.quantity
                self.db.add(existing)
            else:
                new_item = CartItem(
                    cart_id=user_cart.id,
                    menu_item_id=g_item.menu_item_id,
                    variant_id=g_item.variant_id,
                    quantity=g_item.quantity,
                    unit_price=g_item.unit_price,
                    addons=g_item.addons,
                    special_instructions=g_item.special_instructions,
                )
                await self.item_repo.create(new_item)

        # Deactivate guest cart
        guest_cart.is_active = False
        self.db.add(guest_cart)

        await self.db.flush()
        return await self.get_or_create_cart(user_id=logged_user_id)
