"""
CLMStore — Pagination Dependencies
"""
from __future__ import annotations

from fastapi import Query

from app.config.settings import settings
from app.utils.pagination import PaginationParams


def get_pagination_params(
    page: int = Query(default=1, ge=1, description="Page number"),
    per_page: int = Query(
        default=20, ge=1, le=100, description="Items per page (max 100)"
    ),
) -> PaginationParams:
    """Extract page and per_page limits query parameters."""
    return PaginationParams(page=page, per_page=per_page)
