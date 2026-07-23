"""
CLMStore — Delivery Pydantic Schemas
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from app.utils.constants import DeliveryStatus


class DeliveryBase(BaseModel):
    pickup_latitude: float
    pickup_longitude: float
    dropoff_latitude: float
    dropoff_longitude: float
    distance_km: float
    estimated_duration_min: int


class DeliveryResponse(DeliveryBase):
    id: int
    order_id: int
    rider_id: Optional[int]
    status: DeliveryStatus
    assigned_at: Optional[datetime]
    accepted_at: Optional[datetime]
    picked_up_at: Optional[datetime]
    delivered_at: Optional[datetime]
    failed_at: Optional[datetime]
    failure_reason: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class DeliveryFailRequest(BaseModel):
    reason: str = Field(..., min_length=5, max_length=500)
