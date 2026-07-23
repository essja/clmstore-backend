"""
CLMStore — Cart Router
Manages guest and user carts, item operations, coupon application, and cart merging.
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Header, Path, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies.auth import get_current_active_user
from app.exceptions.custom import UnauthorizedException
from app.models.user import User
from app.schemas.cart import (
    ApplyCouponRequest,
    CartItemAddRequest,
    CartItemResponse,
    CartItemUpdateRequest,
    CartResponse,
    CartSyncRequest,
    MergeCartRequest,
)
from app.schemas.common import MessageResponse
from app.services.cart_service import CartService

router = APIRouter()


def _get_session_id(x_session_id: Optional[str] = Header(default=None)) -> Optional[str]:
    """Extract guest session ID from request header."""
    return x_session_id


# ── GET /api/v1/cart ──────────────────────────────────────────────────────────
@router.get(
    "",
    response_model=CartResponse,
    summary="Get current cart",
    description=(
        "Returns the active cart for authenticated users. "
        "For guest users, pass the `X-Session-ID` header."
    ),
)
async def get_cart(
    session_id: Optional[str] = Depends(_get_session_id),
    current_user: Optional[User] = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> CartResponse:
    service = CartService(db)
    cart = await service.get_or_create_cart(
        user_id=current_user.id if current_user else None,
        session_id=session_id,
    )
    return CartResponse.model_validate(cart)


# ── POST /api/v1/cart/items ───────────────────────────────────────────────────
@router.post(
    "/items",
    response_model=CartResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add item to cart",
    description=(
        "Adds a menu item to the cart. If the cart contains items from a different "
        "restaurant, it is automatically cleared first."
    ),
)
async def add_to_cart(
    body: CartItemAddRequest,
    session_id: Optional[str] = Depends(_get_session_id),
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_active_user),
) -> CartResponse:
    """
    **Request Body:**
    ```json
    {
        "menu_item_id": 42,
        "variant_id": 3,
        "quantity": 2,
        "addons": [{"id": 1, "name": "Extra Sauce", "price": 2000.0}],
        "special_instructions": "No onions please"
    }
    ```

    **Headers:**
    - `X-Session-ID: guest-session-uuid` (for guest carts)
    - `Authorization: Bearer <token>` (for authenticated users)
    """
    service = CartService(db)
    cart = await service.add_item(
        body,
        user_id=current_user.id if current_user else None,
        session_id=session_id,
    )
    return CartResponse.model_validate(cart)


# ── PATCH /api/v1/cart/items/{item_id} ───────────────────────────────────────
@router.patch(
    "/items/{item_id}",
    response_model=CartResponse,
    summary="Update cart item quantity",
)
async def update_cart_item(
    item_id: int = Path(..., ge=1),
    body: CartItemUpdateRequest = ...,
    session_id: Optional[str] = Depends(_get_session_id),
    current_user: Optional[User] = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> CartResponse:
    """
    **Request Body:**
    ```json
    {"quantity": 3}
    ```
    """
    service = CartService(db)
    cart = await service.update_item_quantity(
        item_id,
        body.quantity,
        user_id=current_user.id if current_user else None,
        session_id=session_id,
    )
    return CartResponse.model_validate(cart)


# ── DELETE /api/v1/cart/items/{item_id} ──────────────────────────────────────
@router.delete(
    "/items/{item_id}",
    response_model=CartResponse,
    summary="Remove item from cart",
)
async def remove_from_cart(
    item_id: int = Path(..., ge=1),
    session_id: Optional[str] = Depends(_get_session_id),
    current_user: Optional[User] = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> CartResponse:
    service = CartService(db)
    cart = await service.remove_item(
        item_id,
        user_id=current_user.id if current_user else None,
        session_id=session_id,
    )
    return CartResponse.model_validate(cart)


# ── DELETE /api/v1/cart ───────────────────────────────────────────────────────
@router.delete(
    "",
    response_model=MessageResponse,
    summary="Clear entire cart",
)
async def clear_cart(
    session_id: Optional[str] = Depends(_get_session_id),
    current_user: Optional[User] = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    service = CartService(db)
    await service.clear_cart(
        user_id=current_user.id if current_user else None,
        session_id=session_id,
    )
    return MessageResponse(message="Cart cleared successfully.")


# ── POST /api/v1/cart/coupon ─────────────────────────────────────────────────
@router.post(
    "/coupon",
    response_model=CartResponse,
    summary="Apply coupon code to cart",
    description="Validates and applies a coupon code to the active cart.",
)
async def apply_coupon(
    body: ApplyCouponRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> CartResponse:
    """
    **Request Body:**
    ```json
    {"code": "SAVE20"}
    ```
    """
    service = CartService(db)
    cart = await service.apply_coupon(current_user.id, body.code)
    return CartResponse.model_validate(cart)


# ── DELETE /api/v1/cart/coupon ────────────────────────────────────────────────
@router.delete(
    "/coupon",
    response_model=CartResponse,
    summary="Remove coupon from cart",
)
async def remove_coupon(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> CartResponse:
    service = CartService(db)
    cart = await service.remove_coupon(current_user.id)
    return CartResponse.model_validate(cart)


# ── POST /api/v1/cart/merge ───────────────────────────────────────────────────
@router.post(
    "/merge",
    response_model=CartResponse,
    summary="Merge guest cart into user cart after login",
    description=(
        "Merges a guest cart (identified by session ID) into the authenticated "
        "user's cart. Should be called immediately after login."
    ),
)
async def merge_guest_cart(
    body: MergeCartRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> CartResponse:
    """
    **Request Body:**
    ```json
    {"guest_session_id": "uuid-of-guest-session"}
    ```
    """
    service = CartService(db)
    cart = await service.merge_guest_cart(current_user.id, body.guest_session_id)
    return CartResponse.model_validate(cart)


# ── GET /api/v1/cart/summary ──────────────────────────────────────────────────
@router.get(
    "/summary",
    summary="Get cart totals (subtotal, delivery fee, taxes, discount, total)",
    description="Calculates the full financial breakdown for checkout preview.",
)
async def get_cart_summary(
    delivery_address_id: int,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    **Response:**
    ```json
    {
        "subtotal": 70000.0,
        "delivery_fee": 10000.0,
        "service_fee": 3500.0,
        "tax_amount": 10500.0,
        "discount_amount": 7000.0,
        "total_amount": 87000.0,
        "distance_km": 4.2,
        "eta_min": 35
    }
    ```
    """
    from app.services.order_service import OrderService
    service = OrderService(db)
    from app.repositories.cart_repository import CartRepository
    cart_repo = CartRepository(db)
    cart = await cart_repo.get_by_user_id(current_user.id)
    if not cart:
        from app.exceptions.custom import BusinessRuleException
        raise BusinessRuleException("Your cart is empty.")
    return await service.calculate_order_totals(cart.id, delivery_address_id)


# ── POST /api/v1/cart/sync ────────────────────────────────────────────────────
@router.post(
    "/sync",
    response_model=CartResponse,
    summary="Replace server cart with local cart items (called before checkout)",
    description=(
        "Clears the authenticated user's server cart and replaces it entirely "
        "with the items from the local (frontend) cart. Called once before placing an order."
    ),
)
async def sync_cart(
    body: CartSyncRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> CartResponse:
    service = CartService(db)

    # Clear any existing server cart
    await service.clear_cart(user_id=current_user.id, session_id=None)

    # Add each item from the local cart
    for item in body.items:
        add_req = CartItemAddRequest(
            menu_item_id=item.menu_item_id,
            quantity=item.quantity,
            customizations=item.customizations,
            special_instructions=item.special_instructions,
        )
        await service.add_item(
            schema=add_req,
            user_id=current_user.id,
            session_id=None,
        )

    # Apply coupon if provided
    if body.coupon_code:
        try:
            await service.apply_coupon(current_user.id, body.coupon_code)
        except Exception:
            pass  # non-fatal — coupon may be expired or invalid

    cart = await service.get_or_create_cart(user_id=current_user.id, session_id=None)
    return CartResponse.model_validate(cart)
