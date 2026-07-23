"""
CLMStore — Admin and Super Admin Pydantic Schemas
"""
from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional

from pydantic import BaseModel, Field

from app.utils.constants import TicketStatus, DisputeStatus


# ── Dashboard Analytics Schemas ───────────────────────────────────────────────
class DashboardStatsResponse(BaseModel):
    total_customers: int
    total_restaurants: int
    total_riders: int
    total_orders: int
    total_revenue: float
    total_commission: float
    order_status_counts: Dict[str, int]
    daily_revenue: List[dict]  # [{"date": "2024-01-01", "revenue": 10000.0}]


# ── Support Ticket Schemas ────────────────────────────────────────────────────
class SupportTicketBase(BaseModel):
    subject: str = Field(..., min_length=5, max_length=255)
    description: str = Field(..., min_length=10)
    priority: str = Field(default="medium", description="low, medium, high")


class SupportTicketCreate(SupportTicketBase):
    pass


class SupportTicketResponse(SupportTicketBase):
    id: int
    user_id: int
    status: TicketStatus
    assigned_to: Optional[int]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class SupportTicketUpdate(BaseModel):
    status: Optional[TicketStatus] = None
    priority: Optional[str] = None
    assigned_to: Optional[int] = None


# ── Dispute Schemas ───────────────────────────────────────────────────────────
class DisputeCreate(BaseModel):
    order_id: int
    reason: str = Field(..., min_length=10)


class DisputeResponse(BaseModel):
    id: int
    order_id: int
    user_id: int
    reason: str
    status: DisputeStatus
    resolution: Optional[str]
    resolved_by: Optional[int]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class DisputeResolveRequest(BaseModel):
    resolution: str = Field(..., min_length=5)
    status: DisputeStatus = Field(default=DisputeStatus.RESOLVED)
    refund_payment: bool = Field(
        default=False,
        description="If True, automatically process a full refund for the order's payment.",
    )


# ── Super Admin System Settings Schemas ────────────────────────────────────────
class SystemSettingsResponse(BaseModel):
    commission_rate: float = Field(description="e.g. 0.15 = 15%")
    service_fee: float = Field(description="Flat service fee in SLL, e.g. 5000.0")
    tax_rate: float = Field(description="e.g. 0.08 = 8% (internal accounting)")
    default_delivery_fee: float = Field(description="Default flat delivery fee in SLL")
    max_delivery_radius_km: float
    currency_symbol: str = Field(description="e.g. Le")
    currency_code: str = Field(description="e.g. SLL")
    min_withdrawal_amount: float
    platform_name: str

    class Config:
        from_attributes = True


class SystemSettingsUpdateRequest(BaseModel):
    commission_rate: Optional[float] = Field(default=None, ge=0.0, le=1.0, description="0.15 = 15%")
    service_fee: Optional[float] = Field(default=None, ge=0.0, description="Flat fee in SLL")
    tax_rate: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    default_delivery_fee: Optional[float] = Field(default=None, ge=0.0)
    max_delivery_radius_km: Optional[float] = Field(default=None, ge=0.0)
    currency_symbol: Optional[str] = None
    currency_code: Optional[str] = None
    min_withdrawal_amount: Optional[float] = Field(default=None, ge=0.0)
    platform_name: Optional[str] = None


# ── Home Banners and Featured Restaurants ─────────────────────────────────────
class HomepageBannerCreate(BaseModel):
    title: str
    image_url: str
    link_url: Optional[str] = None
    sort_order: int = 0


class HomepageBannerResponse(HomepageBannerCreate):
    id: int
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class FeaturedRestaurantsUpdateRequest(BaseModel):
    restaurant_ids: List[int]
