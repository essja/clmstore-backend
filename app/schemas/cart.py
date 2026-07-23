"""
CLMStore — Cart Pydantic Schemas
"""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field

from app.schemas.menu import MenuItemResponse, MenuItemVariantResponse


# ── Addon Selection Schema ───────────────────────────────────────────────────
class AddonSelection(BaseModel):
    id: int
    name: str
    price: float


# ── Cart Item Schemas ─────────────────────────────────────────────────────────
class CartItemAddRequest(BaseModel):
    menu_item_id: int
    variant_id: Optional[int] = None
    quantity: int = Field(default=1, ge=1)
    addons: Optional[List[AddonSelection]] = Field(default=None, description="Selected addons list")
    customizations: Optional[List[dict]] = Field(default=None, description="Option group selections")
    special_instructions: Optional[str] = Field(default=None, max_length=500)


class CartSyncRequest(BaseModel):
    restaurant_id: int
    items: List[CartItemAddRequest]
    coupon_code: Optional[str] = None


class CartItemUpdateRequest(BaseModel):
    quantity: int = Field(..., ge=1)


class CartItemResponse(BaseModel):
    id: int
    cart_id: int
    menu_item_id: int
    variant_id: Optional[int]
    quantity: int
    unit_price: float
    addons: Optional[List[AddonSelection]]
    special_instructions: Optional[str]
    addons_total: float
    item_price: float
    subtotal: float
    menu_item: MenuItemResponse
    variant: Optional[MenuItemVariantResponse]

    class Config:
        from_attributes = True


# ── Cart Schemas ──────────────────────────────────────────────────────────────
class CartResponse(BaseModel):
    id: int
    user_id: Optional[int]
    session_id: Optional[str]
    restaurant_id: Optional[int]
    coupon_id: Optional[int]
    subtotal: float
    item_count: int
    items: List[CartItemResponse] = []

    class Config:
        from_attributes = True


class ApplyCouponRequest(BaseModel):
    code: str = Field(..., min_length=4, max_length=20)


class MergeCartRequest(BaseModel):
    guest_session_id: str
