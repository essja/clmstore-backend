"""
CLMStore — Location API Tests
"""
from __future__ import annotations

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


class TestDistanceCalculation:
    async def test_distance_calculation(self, client: AsyncClient) -> None:
        resp = await client.post(
            "/api/v1/location/distance",
            json={
                "origin": {"latitude": 8.4901, "longitude": -13.2323},
                "destination": {"latitude": 8.4657, "longitude": -13.2317},
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "distance_km" in data
        assert "estimated_duration_min" in data
        assert "delivery_fee" in data
        assert data["distance_km"] > 0

    async def test_zero_distance(self, client: AsyncClient) -> None:
        resp = await client.post(
            "/api/v1/location/distance",
            json={
                "origin": {"latitude": 8.4901, "longitude": -13.2323},
                "destination": {"latitude": 8.4901, "longitude": -13.2323},
            },
        )
        assert resp.status_code == 200
        assert resp.json()["distance_km"] == 0.0


class TestDeliveryZones:
    async def test_delivery_zones(self, client: AsyncClient) -> None:
        resp = await client.get("/api/v1/location/delivery-zones")
        assert resp.status_code == 200
        data = resp.json()
        assert "zones" in data
        assert len(data["zones"]) > 0

    async def test_cuisine_types(self, client: AsyncClient) -> None:
        resp = await client.get("/api/v1/location/cuisine-types")
        assert resp.status_code == 200
        data = resp.json()
        assert "cuisine_types" in data
        assert "Sierra Leonean" in data["cuisine_types"]


class TestNearbyRestaurants:
    async def test_nearby_restaurants(self, client: AsyncClient) -> None:
        resp = await client.get(
            "/api/v1/location/nearby-restaurants?lat=8.4901&lon=-13.2323&radius_km=10"
        )
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    async def test_invalid_coordinates(self, client: AsyncClient) -> None:
        resp = await client.get(
            "/api/v1/location/nearby-restaurants?lat=200.0&lon=-13.2323"
        )
        assert resp.status_code == 422
