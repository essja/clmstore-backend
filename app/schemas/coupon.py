"""
CLMStore — Coupon Pydantic Schemas
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator

from app.utils.constants import CouponType
from app.utils.validators import validate_coupon_code


class CouponBase(BaseModel):
    code: str = Field(..., min_length=4, max_length=20)
    type: CouponType = Field(default=CouponType.PERCENTAGE)
    value: float = Field(..., ge=0.0, description="Percentage (e.g. 10 for 10%) or absolute fixed amount")
    min_order_value: float = Field(default=0.0, ge=0.0)
    max_discount: Optional[float] = Field(default=None, ge=0.0)
    restaurant_id: Optional[int] = Field(default=None, description="Set null for global coupons")
    expires_at: datetime
    usage_limit: Optional[int] = Field(default=None, ge=1)
    user_usage_limit: int = Field(default=1, ge=1)
    is_active: bool = Field(default=True)

    @field_validator("code")
    @classmethod
    def check_code(cls, v: str) -> str:
        return validate_coupon_code(v)


class CouponCreate(CouponBase):
    pass


class CouponUpdate(BaseModel):
    code: Optional[str] = None
    type: Optional[CouponType] = None
    value: Optional[float] = None
    min_order_value: Optional[float] = None
    max_discount: Optional[float] = None
    expires_at: Optional[datetime] = None
    usage_limit: Optional[int] = None
    user_usage_limit: Optional[int] = None
    is_active: Optional[bool] = None

    @field_validator("code")
    @classmethod
    def check_code(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        return validate_coupon_code(v)


class CouponResponse(CouponBase):
    id: int
    used_count: int
    created_at: datetime

    class Config:
        from_attributes = True


class CouponValidateRequest(BaseModel):
    code: str
    order_subtotal: float
    restaurant_id: int
