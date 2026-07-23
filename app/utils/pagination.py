"""
CLMStore — Pagination Utilities
"""
from __future__ import annotations

import math
from typing import Any, Generic, List, Optional, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class PaginationParams(BaseModel):
    page: int = 1
    per_page: int = 20

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.per_page

    @property
    def skip(self) -> int:
        return (self.page - 1) * self.per_page

    @property
    def limit(self) -> int:
        return self.per_page

    def meta(self, total: int) -> dict:
        total_pages = math.ceil(total / self.per_page) if self.per_page > 0 else 0
        return {
            "page": self.page,
            "per_page": self.per_page,
            "total": total,
            "total_pages": total_pages,
            "has_next": self.page < total_pages,
            "has_prev": self.page > 1,
        }


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


def paginate(
    items: List[Any],
    total: int,
    page: int,
    per_page: int,
) -> dict:
    """Build a paginated response dictionary."""
    total_pages = math.ceil(total / per_page) if per_page > 0 else 0
    return {
        "success": True,
        "data": items,
        "pagination": {
            "page": page,
            "per_page": per_page,
            "total": total,
            "total_pages": total_pages,
            "has_next": page < total_pages,
            "has_prev": page > 1,
        },
    }


class SearchParams(BaseModel):
    q: Optional[str] = None
    page: int = 1
    per_page: int = 20
    sort_by: Optional[str] = None
    sort_order: str = "asc"  # "asc" | "desc"

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.per_page
