"""
CLMStore — Review Pydantic Schemas
"""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator

from app.utils.constants import ReviewTargetType
from app.utils.validators import validate_rating


class ReviewCreateRequest(BaseModel):
    order_id: int
    target_type: ReviewTargetType
    target_id: int  # references restaurant_id, rider_id, or menu_item_id
    rating: float = Field(..., ge=1.0, le=5.0)
    comment: Optional[str] = Field(default=None, max_length=1000)
    images: Optional[List[str]] = Field(default=None, description="List of uploaded image URLs")

    @field_validator("rating")
    @classmethod
    def check_rating(cls, v: float) -> float:
        return validate_rating(v)


class ReviewResponse(BaseModel):
    id: int
    user_id: int
    order_id: int
    target_type: ReviewTargetType
    target_id: int
    rating: float
    comment: Optional[str]
    images: Optional[List[str]]
    created_at: datetime

    class Config:
        from_attributes = True


class RatingSummary(BaseModel):
    average_rating: float
    total_reviews: int
