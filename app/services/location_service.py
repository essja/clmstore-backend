"""
CLMStore — Location and Geocoding Service
Uses OpenStreetMap Nominatim API for address resolution and coordinate lookup.
"""
from __future__ import annotations

import httpx
import structlog
from typing import List, Optional

from app.config.settings import settings
from app.exceptions.custom import ServiceUnavailableException
from app.utils.geo import haversine_distance, calculate_delivery_fee, calculate_eta_minutes
from app.schemas.location import Coordinates, GeocodingResult, DistanceCalculationResponse

logger = structlog.get_logger()


class LocationService:
    def __init__(self) -> None:
        self.headers = {"User-Agent": settings.NOMINATIM_USER_AGENT}
        self.client = httpx.AsyncClient(headers=self.headers, timeout=10.0)

    async def geocode(self, address: str, limit: int = 5) -> List[GeocodingResult]:
        """
        Geocode a text address into GPS coordinates using OpenStreetMap Nominatim.
        """
        query_address = f"{address}, {settings.DEFAULT_CITY}, {settings.DEFAULT_COUNTRY}"
        url = "https://nominatim.openstreetmap.org/search"
        params = {
            "q": query_address,
            "format": "json",
            "addressdetails": 1,
            "limit": min(limit, 10),
        }

        try:
            response = await self.client.get(url, params=params)
            if response.status_code != 200:
                logger.error("nominatim_error_response", status_code=response.status_code)
                raise ServiceUnavailableException("Nominatim Geocoding")

            data = response.json()
            return [
                GeocodingResult(
                    display_name=item["display_name"],
                    latitude=float(item["lat"]),
                    longitude=float(item["lon"]),
                    address_details=item.get("address", {}),
                )
                for item in data
            ]
        except httpx.HTTPError as e:
            logger.error("nominatim_connection_error", error=str(e))
            return [
                GeocodingResult(
                    display_name=f"{address}, Freetown, Sierra Leone",
                    latitude=8.484,
                    longitude=-13.234,
                )
            ]

    async def geocode_address(self, address: str) -> List[GeocodingResult]:
        """Alias kept for backward compatibility."""
        return await self.geocode(address)

    async def reverse_geocode(self, latitude: float, longitude: float) -> GeocodingResult:
        """Resolve coordinates into a GeocodingResult with display_name and coords."""
        url = "https://nominatim.openstreetmap.org/reverse"
        params = {
            "lat": latitude,
            "lon": longitude,
            "format": "json",
            "addressdetails": 1,
        }
        try:
            response = await self.client.get(url, params=params)
            if response.status_code == 200:
                data = response.json()
                return GeocodingResult(
                    display_name=data.get("display_name", f"{latitude}, {longitude}"),
                    latitude=latitude,
                    longitude=longitude,
                    address_details=data.get("address", {}),
                )
        except httpx.HTTPError as e:
            logger.error("nominatim_reverse_error", error=str(e))
        return GeocodingResult(
            display_name=f"{latitude}, {longitude}",
            latitude=latitude,
            longitude=longitude,
        )

    def calculate_trip_details(
        self, origin_lat: float, origin_lng: float, dest_lat: float, dest_lng: float
    ) -> DistanceCalculationResponse:
        """
        Calculate straight line distance, delivery fee, and estimated duration.
        """
        dist = haversine_distance(origin_lat, origin_lng, dest_lat, dest_lng)
        fee = calculate_delivery_fee(dist)
        duration = calculate_eta_minutes(dist)

        return DistanceCalculationResponse(
            distance_km=round(dist, 2),
            estimated_duration_min=duration,
            delivery_fee=fee,
        )

    async def close(self) -> None:
        await self.client.aclose()
