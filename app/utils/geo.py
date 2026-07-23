"""
CLMStore — Geospatial Utilities
Haversine distance, delivery fee calculation, bounding box queries
"""
from __future__ import annotations

import math
from typing import Tuple

from app.utils.constants import DELIVERY_FEE_TIERS


# ── Haversine Distance ────────────────────────────────────────────────────────
def haversine_distance(
    lat1: float, lon1: float, lat2: float, lon2: float
) -> float:
    """
    Calculate the great-circle distance between two GPS coordinates.
    Returns distance in kilometres.
    """
    R = 6371.0  # Earth radius in kilometres

    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)

    a = (
        math.sin(d_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


def calculate_delivery_fee(distance_km: float) -> float:
    """
    Return delivery fee in SLL based on distance tiers.
    Falls back to maximum tier for distances beyond 30 km.
    """
    for max_km, fee in sorted(DELIVERY_FEE_TIERS.items()):
        if distance_km <= max_km:
            return float(fee)
    # Beyond all tiers — charge the maximum + overage
    max_fee = max(DELIVERY_FEE_TIERS.values())
    return float(max_fee) + (distance_km - 30.0) * 1500  # 1,500 SLL per extra km


def calculate_eta_minutes(distance_km: float, avg_speed_kmh: float = 25.0) -> int:
    """
    Estimate delivery time in minutes.
    Default assumes 25 km/h average speed in city traffic.
    Adds a 5-minute preparation buffer.
    """
    travel_minutes = (distance_km / avg_speed_kmh) * 60
    buffer = 5
    return max(int(travel_minutes) + buffer, 10)  # Minimum 10 minutes


def bounding_box(
    lat: float, lon: float, radius_km: float
) -> Tuple[float, float, float, float]:
    """
    Calculate a lat/lon bounding box for a given radius.
    Returns (min_lat, max_lat, min_lon, max_lon).
    Useful for fast pre-filter before exact Haversine calculation.
    """
    R = 6371.0
    lat_delta = math.degrees(radius_km / R)
    lon_delta = math.degrees(radius_km / (R * math.cos(math.radians(lat))))

    return (
        lat - lat_delta,
        lat + lat_delta,
        lon - lon_delta,
        lon + lon_delta,
    )


def is_within_radius(
    origin_lat: float,
    origin_lon: float,
    target_lat: float,
    target_lon: float,
    radius_km: float,
) -> bool:
    """Return True if target point is within radius_km of origin."""
    return haversine_distance(origin_lat, origin_lon, target_lat, target_lon) <= radius_km


def bearing(
    lat1: float, lon1: float, lat2: float, lon2: float
) -> float:
    """
    Calculate the initial bearing (azimuth) from point 1 to point 2.
    Returns bearing in degrees (0–360).
    """
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    d_lambda = math.radians(lon2 - lon1)

    x = math.sin(d_lambda) * math.cos(phi2)
    y = math.cos(phi1) * math.sin(phi2) - math.sin(phi1) * math.cos(phi2) * math.cos(d_lambda)

    initial_bearing = math.atan2(x, y)
    return (math.degrees(initial_bearing) + 360) % 360
