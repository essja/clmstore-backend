"""
CLMStore — Location / Geocoding Router
Handles geocoding, reverse geocoding, distance calculation, and nearby restaurants.
"""
from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies.auth import get_current_active_user
from app.models.user import User
from app.schemas.location import (
    Coordinates,
    DistanceCalculationRequest,
    DistanceCalculationResponse,
    GeocodingResult,
)
from app.schemas.restaurant import RestaurantResponse
from app.services.location_service import LocationService

router = APIRouter()


# ── GET /api/v1/location/geocode ─────────────────────────────────────────────
@router.get(
    "/geocode",
    response_model=List[GeocodingResult],
    summary="Geocode an address to coordinates",
    description="Converts a text address to GPS coordinates using Nominatim / Google Maps.",
)
async def geocode_address(
    address: str = Query(..., description="Address to geocode e.g. '15 Lumley Beach Road, Freetown'"),
    limit: int = Query(default=5, ge=1, le=10),
) -> List[GeocodingResult]:
    """
    **Example:** `GET /api/v1/location/geocode?address=Tower+Hill+Freetown`

    **Response:**
    ```json
    [
        {
            "display_name": "Tower Hill, Freetown, Sierra Leone",
            "latitude": 8.4901,
            "longitude": -13.2323,
            "address_details": {"city": "Freetown", "country": "Sierra Leone"}
        }
    ]
    ```
    """
    service = LocationService()
    results = await service.geocode(address, limit=limit)
    return results


# ── GET /api/v1/location/reverse-geocode ─────────────────────────────────────
@router.get(
    "/reverse-geocode",
    response_model=GeocodingResult,
    summary="Reverse geocode coordinates to address",
    description="Converts GPS coordinates to a human-readable address.",
)
async def reverse_geocode(
    lat: float = Query(..., ge=-90.0, le=90.0, description="Latitude"),
    lon: float = Query(..., ge=-180.0, le=180.0, description="Longitude"),
) -> GeocodingResult:
    """
    **Example:** `GET /api/v1/location/reverse-geocode?lat=8.4901&lon=-13.2323`
    """
    service = LocationService()
    result = await service.reverse_geocode(lat, lon)
    return result


# ── POST /api/v1/location/distance ───────────────────────────────────────────
@router.post(
    "/distance",
    response_model=DistanceCalculationResponse,
    summary="Calculate distance and delivery fee between two points",
)
async def calculate_distance(
    body: DistanceCalculationRequest,
) -> DistanceCalculationResponse:
    """
    Calculates the straight-line (Haversine) distance between two GPS points
    and returns the estimated delivery fee and duration.

    **Request Body:**
    ```json
    {
        "origin": {"latitude": 8.4901, "longitude": -13.2323},
        "destination": {"latitude": 8.4657, "longitude": -13.2317}
    }
    ```

    **Response:**
    ```json
    {
        "distance_km": 3.2,
        "estimated_duration_min": 18,
        "delivery_fee": 5000.0
    }
    ```
    """
    from app.utils.geo import haversine_distance, calculate_delivery_fee, calculate_eta_minutes
    dist = haversine_distance(
        body.origin.latitude, body.origin.longitude,
        body.destination.latitude, body.destination.longitude,
    )
    fee = calculate_delivery_fee(dist)
    eta = calculate_eta_minutes(dist)
    return DistanceCalculationResponse(
        distance_km=round(dist, 2),
        estimated_duration_min=eta,
        delivery_fee=fee,
    )


# ── GET /api/v1/location/nearby-restaurants ──────────────────────────────────
@router.get(
    "/nearby-restaurants",
    response_model=List[RestaurantResponse],
    summary="Find restaurants near a GPS location",
    description="Returns verified, open restaurants within a radius sorted by distance.",
)
async def nearby_restaurants(
    lat: float = Query(..., ge=-90.0, le=90.0, description="User latitude"),
    lon: float = Query(..., ge=-180.0, le=180.0, description="User longitude"),
    radius_km: float = Query(default=10.0, ge=0.5, le=30.0, description="Search radius in km"),
    limit: int = Query(default=20, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
) -> List[RestaurantResponse]:
    """
    **Example:** `GET /api/v1/location/nearby-restaurants?lat=8.4901&lon=-13.2323&radius_km=5`

    Returns restaurants sorted by distance (nearest first).
    """
    from app.services.restaurant_service import RestaurantService
    service = RestaurantService(db)
    restaurants, _ = await service.search_restaurants(
        lat=lat, lon=lon, radius_km=radius_km,
        sort_by="distance", limit=limit, skip=0,
        is_open=True,
    )
    return [RestaurantResponse.model_validate(r) for r in restaurants]


# ── GET /api/v1/location/delivery-zones ──────────────────────────────────────
@router.get(
    "/delivery-zones",
    summary="Get delivery coverage zones in Freetown",
    description="Returns the defined delivery zones and approximate fees for the platform.",
)
async def delivery_zones() -> dict:
    """
    **Response:**
    ```json
    {
        "zones": [
            {"name": "Zone 1 (0–3 km)", "fee": 5000, "currency": "SLL"},
            {"name": "Zone 2 (3–7 km)", "fee": 10000, "currency": "SLL"},
            {"name": "Zone 3 (7–15 km)", "fee": 18000, "currency": "SLL"},
            {"name": "Zone 4 (15–30 km)", "fee": 30000, "currency": "SLL"}
        ],
        "currency": "SLL",
        "max_radius_km": 30.0
    }
    ```
    """
    from app.utils.constants import DELIVERY_FEE_TIERS
    from app.config.settings import settings
    zones = []
    prev = 0.0
    for km, fee in sorted(DELIVERY_FEE_TIERS.items()):
        zones.append({
            "name": f"Zone ({prev}–{km} km)",
            "distance_km": {"min": prev, "max": km},
            "delivery_fee": fee,
            "currency": settings.DEFAULT_CURRENCY,
        })
        prev = km
    return {
        "zones": zones,
        "max_radius_km": settings.MAX_DELIVERY_RADIUS_KM,
        "currency": settings.DEFAULT_CURRENCY,
    }


# ── GET /api/v1/location/cuisine-types ───────────────────────────────────────
@router.get(
    "/cuisine-types",
    summary="List all available cuisine types",
)
async def cuisine_types() -> dict:
    """
    **Response:**
    ```json
    {
        "cuisine_types": ["Sierra Leonean", "Fast Food", "Chinese", ...]
    }
    ```
    """
    from app.utils.constants import CUISINE_TYPES
    return {"cuisine_types": CUISINE_TYPES}
