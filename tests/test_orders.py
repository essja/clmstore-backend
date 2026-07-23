"""
CLMStore — Order Tests
"""
from __future__ import annotations

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


async def _login(client: AsyncClient, email: str, password: str = "Test@1234") -> str:
    resp = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    return resp.json()["data"]["access_token"]


class TestCart:
    async def test_get_empty_cart(self, client: AsyncClient, customer_user) -> None:
        token = await _login(client, "customer@test.com")
        resp = await client.get(
            "/api/v1/cart",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200

    async def test_clear_cart(self, client: AsyncClient, customer_user) -> None:
        token = await _login(client, "customer@test.com")
        resp = await client.delete(
            "/api/v1/cart",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200

    async def test_validate_coupon_invalid(self, client: AsyncClient, customer_user) -> None:
        token = await _login(client, "customer@test.com")
        resp = await client.post(
            "/api/v1/coupons/validate",
            json={
                "code": "NONEXISTENT",
                "order_subtotal": 50000.0,
                "restaurant_id": 1,
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        # Either 404 or 400 for invalid coupon
        assert resp.status_code in (400, 404)


class TestOrderHistory:
    async def test_list_orders_empty(self, client: AsyncClient, customer_user) -> None:
        token = await _login(client, "customer@test.com")
        resp = await client.get(
            "/api/v1/orders",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "data" in data
        assert "pagination" in data
        assert data["pagination"]["total"] == 0

    async def test_get_nonexistent_order(self, client: AsyncClient, customer_user) -> None:
        token = await _login(client, "customer@test.com")
        resp = await client.get(
            "/api/v1/orders/99999",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code in (403, 404)

    async def test_orders_require_auth(self, client: AsyncClient) -> None:
        resp = await client.get("/api/v1/orders")
        assert resp.status_code == 401


class TestPayments:
    async def test_payment_history_empty(self, client: AsyncClient, customer_user) -> None:
        token = await _login(client, "customer@test.com")
        resp = await client.get(
            "/api/v1/payments",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["pagination"]["total"] == 0

    async def test_payment_nonexistent_order(self, client: AsyncClient, customer_user) -> None:
        token = await _login(client, "customer@test.com")
        resp = await client.post(
            "/api/v1/payments/initiate",
            json={"order_id": 99999, "provider": "cash"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code in (400, 404)
