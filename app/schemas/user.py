"""
CLMStore — User Pydantic Schemas
"""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.utils.constants import UserRole
from app.utils.validators import validate_phone, validate_password


# ── User Address Schemas ──────────────────────────────────────────────────────
class UserAddressBase(BaseModel):
    label: str = Field(..., examples=["Home", "Work", "My Office"])
    address_line: str = Field(..., examples=["12 Wilkinson Road", "5 Signal Hill Road"])
    city: str = Field(default="Freetown")
    country: str = Field(default="Sierra Leone")
    latitude: Optional[float] = Field(default=None, ge=-90.0, le=90.0)
    longitude: Optional[float] = Field(default=None, ge=-180.0, le=180.0)
    is_default: bool = Field(default=False)
    notes: Optional[str] = Field(default=None, examples=["Call when you reach the gate"])


class UserAddressCreate(UserAddressBase):
    pass


class UserAddressUpdate(BaseModel):
    label: Optional[str] = None
    address_line: Optional[str] = None
    city: Optional[str] = None
    country: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    is_default: Optional[bool] = None
    notes: Optional[str] = None


class UserAddressResponse(UserAddressBase):
    id: int
    user_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ── User Auth Schemas ─────────────────────────────────────────────────────────
class UserRegisterRequest(BaseModel):
    email: EmailStr
    phone: Optional[str] = None
    phone_number: Optional[str] = None  # frontend alias
    password: str
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    role: UserRole = Field(default=UserRole.CUSTOMER)

    @field_validator("phone", "phone_number", mode="before")
    @classmethod
    def check_phone(cls, v: Optional[str]) -> Optional[str]:
        if not v:
            return None
        return validate_phone(v)

    @field_validator("password")
    @classmethod
    def check_password(cls, v: str) -> str:
        return validate_password(v)


class UserLoginRequest(BaseModel):
    email: EmailStr
    password: str
    onesignal_player_id: Optional[str] = None


class TokenRefreshRequest(BaseModel):
    refresh_token: str


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def check_password(cls, v: str) -> str:
        return validate_password(v)


class PhoneVerifyRequest(BaseModel):
    phone: str
    otp_code: str

    @field_validator("phone")
    @classmethod
    def check_phone(cls, v: str) -> str:
        return validate_phone(v)


class EmailVerifyRequest(BaseModel):
    token: str


# ── User Profile Schemas ──────────────────────────────────────────────────────
class UserProfileResponse(BaseModel):
    id: int
    email: EmailStr
    phone: Optional[str]
    first_name: str
    last_name: str
    role: UserRole
    profile_picture: Optional[str]
    is_active: bool
    is_email_verified: bool
    is_phone_verified: bool
    created_at: datetime

    class Config:
        from_attributes = True


class UserProfileUpdateRequest(BaseModel):
    first_name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    last_name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    phone: Optional[str] = None

    @field_validator("phone")
    @classmethod
    def check_phone(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        return validate_phone(v)


class UserFavoriteResponse(BaseModel):
    id: int
    user_id: int
    restaurant_id: int
    created_at: datetime

    class Config:
        from_attributes = True
