"""
CLMStore — Restaurant Tests
"""
from __future__ import annotations

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio

RESTAURANT_PAYLOAD = {
    "name": "Mama's Kitchen",
    "description": "Authentic Sierra Leonean cuisine",
    "cuisine_type": "Sierra Leonean",
    "address": "15 Lumley Beach Road, Freetown",
    "city": "Freetown",
    "latitude": 8.4657,
    "longitude": -13.2317,
    "phone": "+23276123456",
    "min_order": 20000.0,
    "delivery_fee": 10000.0,
    "delivery_radius_km": 8.0,
}


async def _login(client: AsyncClient, email: str, password: str = "Test@1234") -> str:
    resp = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    return resp.json()["data"]["access_token"]


class TestRestaurantBrowsing:
    async def test_list_restaurants_public(self, client: AsyncClient) -> None:
        resp = await client.get("/api/v1/restaurants")
        assert resp.status_code == 200
        data = resp.json()
        assert "data" in data
        assert "pagination" in data

    async def test_search_restaurants(self, client: AsyncClient) -> None:
        resp = await client.get("/api/v1/restaurants?q=rice&cuisine=Sierra+Leonean")
        assert resp.status_code == 200

    async def test_filter_by_open(self, client: AsyncClient) -> None:
        resp = await client.get("/api/v1/restaurants?is_open=true")
        assert resp.status_code == 200

    async def test_nearby_restaurants(self, client: AsyncClient) -> None:
        resp = await client.get(
            "/api/v1/restaurants?lat=8.4901&lon=-13.2323&radius_km=5"
        )
        assert resp.status_code == 200

    async def test_get_nonexistent_restaurant(self, client: AsyncClient) -> None:
        resp = await client.get("/api/v1/restaurants/99999")
        assert resp.status_code == 404


class TestRestaurantCRUD:
    async def test_create_restaurant(self, client: AsyncClient, restaurant_owner_user) -> None:
        token = await _login(client, "owner@test.com")
        resp = await client.post(
            "/api/v1/restaurants",
            json=RESTAURANT_PAYLOAD,
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Mama's Kitchen"
        assert data["status"] == "pending"  # Requires admin approval

    async def test_create_restaurant_as_customer_forbidden(
        self, client: AsyncClient, customer_user
    ) -> None:
        token = await _login(client, "customer@test.com")
        resp = await client.post(
            "/api/v1/restaurants",
            json=RESTAURANT_PAYLOAD,
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403

    async def test_update_restaurant(self, client: AsyncClient, restaurant_owner_user) -> None:
        token = await _login(client, "owner@test.com")
        # Create first
        create_resp = await client.post(
            "/api/v1/restaurants",
            json=RESTAURANT_PAYLOAD,
            headers={"Authorization": f"Bearer {token}"},
        )
        restaurant_id = create_resp.json()["id"]

        # Update
        resp = await client.patch(
            f"/api/v1/restaurants/{restaurant_id}",
            json={"name": "Updated Kitchen", "min_order": 25000.0},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "Updated Kitchen"


class TestMenu:
    async def test_get_menu_public(self, client: AsyncClient, restaurant_owner_user) -> None:
        token = await _login(client, "owner@test.com")
        create_resp = await client.post(
            "/api/v1/restaurants",
            json=RESTAURANT_PAYLOAD,
            headers={"Authorization": f"Bearer {token}"},
        )
        restaurant_id = create_resp.json()["id"]

        resp = await client.get(f"/api/v1/restaurants/{restaurant_id}/menu")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    async def test_create_menu_item(self, client: AsyncClient, restaurant_owner_user) -> None:
        token = await _login(client, "owner@test.com")
        create_resp = await client.post(
            "/api/v1/restaurants",
            json=RESTAURANT_PAYLOAD,
            headers={"Authorization": f"Bearer {token}"},
        )
        restaurant_id = create_resp.json()["id"]

        resp = await client.post(
            f"/api/v1/restaurants/{restaurant_id}/menu",
            json={
                "name": "Jollof Rice",
                "description": "Classic Sierra Leonean jollof rice",
                "price": 35000.0,
                "is_available": True,
                "preparation_time_min": 20,
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Jollof Rice"
        assert data["price"] == 35000.0
