"""
CLMStore — Menu Pydantic Schemas
"""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator

from app.utils.validators import validate_price


# ── Variant Schemas ───────────────────────────────────────────────────────────
class MenuItemVariantBase(BaseModel):
    name: str = Field(..., examples=["Small", "Regular", "Large"])
    price_modifier: float = Field(default=0.0, description="Amount added to base item price")
    is_available: bool = Field(default=True)
    sort_order: int = Field(default=0)


class MenuItemVariantCreate(MenuItemVariantBase):
    pass


class MenuItemVariantResponse(MenuItemVariantBase):
    id: int
    menu_item_id: int

    class Config:
        from_attributes = True


# ── Addon Schemas ─────────────────────────────────────────────────────────────
class MenuItemAddonBase(BaseModel):
    name: str = Field(..., examples=["Extra Cheese", "Extra Ketchup"])
    price: float = Field(default=0.0, ge=0.0)
    is_required: bool = Field(default=False)
    max_selections: int = Field(default=1, ge=1)
    is_available: bool = Field(default=True)


class MenuItemAddonCreate(MenuItemAddonBase):
    pass


class MenuItemAddonResponse(MenuItemAddonBase):
    id: int
    menu_item_id: int

    class Config:
        from_attributes = True


# ── Food Category Schemas ─────────────────────────────────────────────────────
class FoodCategoryBase(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    description: Optional[str] = None
    sort_order: int = Field(default=0)
    is_active: bool = Field(default=True)


class FoodCategoryCreate(FoodCategoryBase):
    pass


class FoodCategoryResponse(FoodCategoryBase):
    id: int
    restaurant_id: int
    image: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


# ── Menu Item Schemas ─────────────────────────────────────────────────────────
class MenuItemBase(BaseModel):
    name: str = Field(..., min_length=2, max_length=200)
    description: Optional[str] = None
    price: float = Field(..., ge=0.0)
    is_available: bool = Field(default=True)
    is_popular: bool = Field(default=False)
    is_recommended: bool = Field(default=False)
    is_vegan: bool = Field(default=False)
    is_vegetarian: bool = Field(default=False)
    is_spicy: bool = Field(default=False)
    discount_percentage: float = Field(default=0.0, ge=0.0, le=100.0)
    stock_count: Optional[int] = Field(default=None, description="Null indicates unlimited")
    preparation_time_min: int = Field(default=15, ge=1)
    calories: Optional[int] = Field(default=None, ge=0)
    sort_order: int = Field(default=0)

    @field_validator("price")
    @classmethod
    def check_price(cls, v: float) -> float:
        return validate_price(v)


class MenuItemCreate(MenuItemBase):
    category_id: Optional[int] = None
    image: Optional[str] = None


class MenuItemUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    price: Optional[float] = None
    category_id: Optional[int] = None
    is_available: Optional[bool] = None
    is_popular: Optional[bool] = None
    is_recommended: Optional[bool] = None
    is_vegan: Optional[bool] = None
    is_vegetarian: Optional[bool] = None
    is_spicy: Optional[bool] = None
    discount_percentage: Optional[float] = None
    stock_count: Optional[int] = None
    preparation_time_min: Optional[int] = None
    calories: Optional[int] = None
    sort_order: Optional[int] = None

    @field_validator("price")
    @classmethod
    def check_price(cls, v: Optional[float]) -> Optional[float]:
        if v is None:
            return None
        return validate_price(v)


class MenuItemResponse(MenuItemBase):
    id: int
    restaurant_id: int
    category_id: Optional[int]
    image: Optional[str]
    effective_price: float
    total_orders: int
    avg_rating: float
    variants: List[MenuItemVariantResponse] = []
    addons: List[MenuItemAddonResponse] = []
    option_groups: List["MenuOptionGroupResponse"] = []
    created_at: datetime

    class Config:
        from_attributes = True


class MenuItemStockUpdate(BaseModel):
    stock_count: Optional[int] = Field(..., description="Set to null for unlimited stock, or a positive integer")


# ── Option Group & Option Schemas ─────────────────────────────────────────────

class MenuOptionBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    price_modifier: float = Field(default=0.0, description="Price change (negative for removals)")
    is_default: bool = Field(default=False)
    is_available: bool = Field(default=True)
    display_order: int = Field(default=0)


class MenuOptionCreate(MenuOptionBase):
    pass


class MenuOptionUpdate(BaseModel):
    name: Optional[str] = None
    price_modifier: Optional[float] = None
    is_default: Optional[bool] = None
    is_available: Optional[bool] = None
    display_order: Optional[int] = None


class MenuOptionResponse(MenuOptionBase):
    id: int
    option_group_id: int

    class Config:
        from_attributes = True


class MenuOptionGroupBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, examples=["Choose Protein", "Add-ons", "Remove Ingredients"])
    group_type: str = Field(default="multiple", pattern="^(single|multiple|removal)$")
    is_required: bool = Field(default=False)
    min_selections: int = Field(default=0, ge=0)
    max_selections: int = Field(default=1, ge=0, description="0 = unlimited")
    display_order: int = Field(default=0)


class MenuOptionGroupCreate(MenuOptionGroupBase):
    options: List[MenuOptionCreate] = []


class MenuOptionGroupUpdate(BaseModel):
    name: Optional[str] = None
    group_type: Optional[str] = Field(default=None, pattern="^(single|multiple|removal)$")
    is_required: Optional[bool] = None
    min_selections: Optional[int] = Field(default=None, ge=0)
    max_selections: Optional[int] = Field(default=None, ge=0)
    display_order: Optional[int] = None


class MenuOptionGroupResponse(MenuOptionGroupBase):
    id: int
    menu_item_id: int
    options: List[MenuOptionResponse] = []

    class Config:
        from_attributes = True


# Resolve forward reference
MenuItemResponse.model_rebuild()
