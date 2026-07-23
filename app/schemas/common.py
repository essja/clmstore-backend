"""
CLMStore — Common Schemas
"""
from __future__ import annotations

from typing import Any, Generic, List, Optional, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class MessageResponse(BaseModel):
    success: bool = True
    message: str


class PaginationMeta(BaseModel):
    page: int
    per_page: int
    total: int
    total_pages: int
    has_next: bool
    has_prev: bool


class PaginatedResponse(BaseModel, Generic[T]):
    success: bool = True
    data: List[T]
    pagination: PaginationMeta


class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    role: str
    email: str


class AuthTokenData(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "Bearer"
    user: Any


class AuthResponse(BaseModel):
    success: bool = True
    data: AuthTokenData


class TokenData(BaseModel):
    user_id: str
    role: str
    email: str
    exp: Optional[int] = None
