"""
CLMStore — Order Pydantic Schemas
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from app.utils.constants import OrderStatus, PaymentProvider
from app.schemas.user import UserProfileResponse, UserAddressResponse
from app.schemas.restaurant import RestaurantResponse


class OrderItemResponse(BaseModel):
    id: int
    menu_item_id: Optional[int]
    name: str
    description: Optional[str]
    unit_price: float
    quantity: int
    variants: Optional[List[dict]]
    addons: Optional[List[dict]]
    customizations: Optional[List[dict]]
    special_instructions: Optional[str]
    subtotal: float

    class Config:
        from_attributes = True


class OrderStatusHistoryResponse(BaseModel):
    id: int
    status: OrderStatus
    note: Optional[str]
    changed_by: Optional[int]
    created_at: datetime

    class Config:
        from_attributes = True


class OrderCreateRequest(BaseModel):
    delivery_address_id: int
    payment_method: PaymentProvider
    notes: Optional[str] = Field(default=None, max_length=500)


class OrderResponse(BaseModel):
    id: int
    order_number: str
    user_id: int
    restaurant_id: int
    rider_id: Optional[int]
    delivery_address_id: Optional[int]
    coupon_id: Optional[int]
    status: OrderStatus
    payment_method: Optional[PaymentProvider]
    payment_status: str
    subtotal: float
    delivery_fee: float
    service_fee: float
    tax_amount: float
    discount_amount: float
    total_amount: float
    currency: str
    delivery_address_snapshot: Optional[Dict[str, Any]]
    delivery_distance_km: Optional[float]
    estimated_delivery_min: Optional[int]
    notes: Optional[str]
    rejection_reason: Optional[str]
    cancellation_reason: Optional[str]
    created_at: datetime
    updated_at: datetime

    items: List[OrderItemResponse] = []
    status_history: List[OrderStatusHistoryResponse] = []
    customer: Optional[UserProfileResponse] = None
    restaurant: Optional[RestaurantResponse] = None

    class Config:
        from_attributes = True


class OrderCancelRequest(BaseModel):
    reason: str = Field(..., min_length=5, max_length=500)


class OrderRejectRequest(BaseModel):
    reason: str = Field(..., min_length=5, max_length=500)


class OrderAssignRiderRequest(BaseModel):
    rider_id: int
