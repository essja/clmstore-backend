"""
CLMStore — Rider Pydantic Schemas
"""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field

from app.utils.constants import VehicleType, DocumentType, EarningsStatus


class RiderProfileRegisterRequest(BaseModel):
    vehicle_type: VehicleType = Field(default=VehicleType.MOTORCYCLE)
    vehicle_plate: Optional[str] = Field(default=None, max_length=50)
    vehicle_model: Optional[str] = Field(default=None, max_length=100)
    vehicle_color: Optional[str] = Field(default=None, max_length=50)


class RiderProfileUpdateRequest(BaseModel):
    vehicle_type: Optional[VehicleType] = None
    vehicle_plate: Optional[str] = None
    vehicle_model: Optional[str] = None
    vehicle_color: Optional[str] = None


class RiderDocumentCreate(BaseModel):
    doc_type: DocumentType
    file_url: str


class RiderDocumentResponse(BaseModel):
    id: int
    rider_id: int
    doc_type: DocumentType
    file_url: str
    is_verified: bool
    created_at: datetime

    class Config:
        from_attributes = True


class RiderProfileResponse(BaseModel):
    id: int
    user_id: int
    vehicle_type: VehicleType
    vehicle_plate: Optional[str]
    vehicle_model: Optional[str]
    vehicle_color: Optional[str]
    is_available: bool
    is_verified: bool
    rating: float
    total_deliveries: int
    total_earnings: float
    current_balance: float
    created_at: datetime

    class Config:
        from_attributes = True


class RiderEarningResponse(BaseModel):
    id: int
    rider_id: int
    order_id: int
    amount: float
    commission_deducted: float
    net_earning: float
    status: EarningsStatus
    created_at: datetime

    class Config:
        from_attributes = True


class RiderWithdrawalRequest(BaseModel):
    amount: float = Field(..., ge=50000.0)  # Min 50,000 SLL
    payment_method: str = Field(..., examples=["orange_money", "afrimoney", "bank"])
    payment_details: str = Field(..., description="Phone number or bank details")


class RiderWithdrawalResponse(BaseModel):
    id: int
    rider_id: int
    amount: float
    status: str
    payment_method: str
    payment_details: str
    transaction_reference: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True
