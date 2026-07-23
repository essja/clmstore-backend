"""
CLMStore — Restaurant Pydantic Schemas
"""
from __future__ import annotations

from datetime import datetime, time
from typing import List, Optional

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.utils.constants import OperatingStatus, RestaurantStatus, DayOfWeek, DocumentType, StoreType
from app.utils.validators import validate_phone, validate_latitude, validate_longitude


# ── Opening Hours Schemas ─────────────────────────────────────────────────────
class OpeningHoursBase(BaseModel):
    day_of_week: DayOfWeek
    open_time: Optional[time] = Field(default=None, description="Format HH:MM:SS")
    close_time: Optional[time] = Field(default=None, description="Format HH:MM:SS")
    is_closed: bool = Field(default=False)


class OpeningHoursCreate(OpeningHoursBase):
    pass


class OpeningHoursResponse(OpeningHoursBase):
    id: int
    restaurant_id: int

    class Config:
        from_attributes = True


# ── Restaurant Documents Schemas ──────────────────────────────────────────────
class RestaurantDocumentBase(BaseModel):
    doc_type: DocumentType
    file_url: str


class RestaurantDocumentCreate(RestaurantDocumentBase):
    pass


class RestaurantDocumentResponse(RestaurantDocumentBase):
    id: int
    restaurant_id: int
    is_verified: bool
    created_at: datetime

    class Config:
        from_attributes = True


# ── Restaurant Employee Schemas ──────────────────────────────────────────────
class RestaurantEmployeeCreate(BaseModel):
    user_id: int
    role: str = Field(default="staff", examples=["manager", "cashier", "staff"])


class RestaurantEmployeeResponse(BaseModel):
    id: int
    restaurant_id: int
    user_id: int
    role: str
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


# ── Restaurant Profile Schemas ────────────────────────────────────────────────
class RestaurantBase(BaseModel):
    name: str = Field(..., min_length=2, max_length=200)
    description: Optional[str] = None
    store_type: StoreType = Field(default=StoreType.RESTAURANT, description="restaurant | grocery | pharmacy")
    cuisine_type: str = Field(..., description="e.g. Rice Dishes, Fast Food, Sierra Leonean")
    address: str
    city: str = Field(default="Freetown")
    latitude: float = Field(..., ge=-90.0, le=90.0)
    longitude: float = Field(..., ge=-180.0, le=180.0)
    phone: Optional[str] = None
    email: Optional[EmailStr] = None
    min_order: float = Field(default=0.0, ge=0.0)
    delivery_fee: float = Field(default=10000.0, ge=0.0)
    delivery_radius_km: float = Field(default=5.0, ge=0.0)
    min_delivery_time_min: int = Field(default=20, ge=5)
    avg_delivery_time_min: int = Field(default=35, ge=5)

    @field_validator("phone")
    @classmethod
    def check_phone(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        return validate_phone(v)

    @field_validator("latitude")
    @classmethod
    def check_lat(cls, v: float) -> float:
        return validate_latitude(v)

    @field_validator("longitude")
    @classmethod
    def check_lon(cls, v: float) -> float:
        return validate_longitude(v)


class RestaurantCreate(RestaurantBase):
    owner_id: Optional[int] = None  # Settable by admin, otherwise takes current user ID


class RestaurantUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    logo: Optional[str] = None
    cover_image: Optional[str] = None
    store_type: Optional[StoreType] = None
    cuisine_type: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    phone: Optional[str] = None
    email: Optional[EmailStr] = None
    min_order: Optional[float] = None
    delivery_fee: Optional[float] = None
    delivery_radius_km: Optional[float] = None
    min_delivery_time_min: Optional[int] = None
    avg_delivery_time_min: Optional[int] = None
    is_open: Optional[bool] = None

    @field_validator("phone")
    @classmethod
    def check_phone(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        return validate_phone(v)


class RestaurantResponse(RestaurantBase):
    id: int
    owner_id: int
    slug: str
    logo: Optional[str]
    cover_image: Optional[str]
    status: RestaurantStatus
    is_open: bool
    operating_status: str = "open"
    is_featured: bool
    commission_rate: float
    current_balance: float = 0.0
    total_earnings: float = 0.0
    avg_rating: float
    total_reviews: int
    total_orders: int
    created_at: datetime
    # Computed at query time
    distance_km: Optional[float] = None

    class Config:
        from_attributes = True


# ── Restaurant Earnings & Withdrawal Schemas ──────────────────────────────────

class RestaurantEarningResponse(BaseModel):
    id: int
    restaurant_id: int
    order_id: int
    gross_amount: float
    commission_rate: float
    commission_amount: float
    net_amount: float
    status: str
    created_at: datetime

    class Config:
        from_attributes = True


class RestaurantWithdrawalRequest(BaseModel):
    amount: float = Field(..., ge=50000.0, description="Minimum 50,000 SLL")
    payment_method: str = Field(..., examples=["orange_money", "afrimoney", "bank"])
    payment_details: str = Field(..., min_length=5, description="Mobile money number or bank account details")


class RestaurantWithdrawalResponse(BaseModel):
    id: int
    restaurant_id: int
    amount: float
    status: str
    payment_method: str
    payment_details: str
    transaction_reference: Optional[str]
    notes: Optional[str]
    processed_at: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True
