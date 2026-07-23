"""
CLMStore — User Profile Tests
"""
from __future__ import annotations

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


async def _login(client: AsyncClient, email: str, password: str = "Test@1234") -> str:
    resp = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    return resp.json()["data"]["access_token"]


class TestUserProfile:
    async def test_get_profile(self, client: AsyncClient, customer_user) -> None:
        token = await _login(client, "customer@test.com")
        resp = await client.get("/api/v1/users/profile", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        assert resp.json()["email"] == "customer@test.com"

    async def test_update_profile(self, client: AsyncClient, customer_user) -> None:
        token = await _login(client, "customer@test.com")
        resp = await client.patch(
            "/api/v1/users/profile",
            json={"first_name": "Updated", "last_name": "Name"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["first_name"] == "Updated"

    async def test_get_profile_unauthorized(self, client: AsyncClient) -> None:
        resp = await client.get("/api/v1/users/profile")
        assert resp.status_code == 401


class TestUserAddresses:
    async def test_add_address(self, client: AsyncClient, customer_user) -> None:
        token = await _login(client, "customer@test.com")
        resp = await client.post(
            "/api/v1/users/addresses",
            json={
                "label": "Home",
                "address_line": "12 Wilkinson Road",
                "city": "Freetown",
                "country": "Sierra Leone",
                "latitude": 8.4657,
                "longitude": -13.2317,
                "is_default": True,
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["label"] == "Home"
        assert data["city"] == "Freetown"

    async def test_list_addresses(self, client: AsyncClient, customer_user) -> None:
        token = await _login(client, "customer@test.com")
        resp = await client.get(
            "/api/v1/users/addresses",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    async def test_invalid_coordinates(self, client: AsyncClient, customer_user) -> None:
        token = await _login(client, "customer@test.com")
        resp = await client.post(
            "/api/v1/users/addresses",
            json={
                "label": "Bad",
                "address_line": "Test",
                "latitude": 200.0,  # Invalid
                "longitude": -13.0,
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 422
