"""
CLMStore — Location and GPS Pydantic Schemas
"""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class Coordinates(BaseModel):
    latitude: float = Field(..., ge=-90.0, le=90.0)
    longitude: float = Field(..., ge=-180.0, le=180.0)


class LocationUpdateRequest(Coordinates):
    bearing: Optional[float] = Field(default=None, ge=0.0, le=360.0)


class RiderLocationResponse(LocationUpdateRequest):
    rider_id: int
    updated_at: datetime

    class Config:
        from_attributes = True


class GeocodingResult(BaseModel):
    display_name: str
    latitude: float
    longitude: float
    address_details: Optional[dict] = None


class DistanceCalculationRequest(BaseModel):
    origin: Coordinates
    destination: Coordinates


class DistanceCalculationResponse(BaseModel):
    distance_km: float
    estimated_duration_min: int
    delivery_fee: float
