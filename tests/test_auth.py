"""
CLMStore — Authentication Tests
"""
from __future__ import annotations

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


async def _login(client: AsyncClient, email: str, password: str = "Test@1234") -> dict:
    """Login and return the full data dict: {access_token, refresh_token, ...}"""
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    return resp.json()["data"]


class TestRegister:
    async def test_register_customer_success(self, client: AsyncClient) -> None:
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "newuser@example.com",
                "phone": "+23276900001",
                "password": "SecurePass@1",
                "first_name": "John",
                "last_name": "Doe",
                "role": "customer",
            },
        )
        assert response.status_code == 201
        body = response.json()
        # AuthResponse shape: {"success": true, "data": {"access_token": ..., "user": {...}}}
        assert body["success"] is True
        assert "access_token" in body["data"]
        user = body["data"]["user"]
        assert user["email"] == "newuser@example.com"
        assert user["role"] == "customer"
        assert "password_hash" not in user

    async def test_register_duplicate_email(self, client: AsyncClient) -> None:
        payload = {
            "email": "dupe@example.com",
            "phone": "+23276900002",
            "password": "SecurePass@1",
            "first_name": "Jane",
            "last_name": "Doe",
            "role": "customer",
        }
        await client.post("/api/v1/auth/register", json=payload)
        response = await client.post("/api/v1/auth/register", json=payload)
        assert response.status_code == 409

    async def test_register_invalid_email(self, client: AsyncClient) -> None:
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "not-an-email",
                "phone": "+23276900003",
                "password": "SecurePass@1",
                "first_name": "A",
                "last_name": "B",
                "role": "customer",
            },
        )
        assert response.status_code == 422

    async def test_register_weak_password(self, client: AsyncClient) -> None:
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "weakpass@example.com",
                "phone": "+23276900004",
                "password": "123",
                "first_name": "A",
                "last_name": "B",
                "role": "customer",
            },
        )
        assert response.status_code == 422


class TestLogin:
    async def test_login_success(self, client: AsyncClient, customer_user) -> None:
        data = await _login(client, "customer@test.com")
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"].lower() == "bearer"
        user = data["user"]
        assert user["role"] == "customer"

    async def test_login_wrong_password(self, client: AsyncClient, customer_user) -> None:
        response = await client.post(
            "/api/v1/auth/login",
            json={"email": "customer@test.com", "password": "WrongPassword"},
        )
        assert response.status_code == 401

    async def test_login_nonexistent_user(self, client: AsyncClient) -> None:
        response = await client.post(
            "/api/v1/auth/login",
            json={"email": "nobody@example.com", "password": "Password@1"},
        )
        assert response.status_code == 401


class TestGetMe:
    async def test_get_me_authenticated(self, client: AsyncClient, customer_user) -> None:
        data = await _login(client, "customer@test.com")
        token = data["access_token"]

        response = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["email"] == "customer@test.com"

    async def test_get_me_unauthenticated(self, client: AsyncClient) -> None:
        response = await client.get("/api/v1/auth/me")
        assert response.status_code == 401


class TestTokenRefresh:
    async def test_refresh_token_success(self, client: AsyncClient) -> None:
        # Register a fresh user unique to this test to avoid cross-test conflicts
        reg = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "refresh_test@example.com",
                "phone": "+23276800001",
                "password": "RefreshPass@1",
                "first_name": "Refresh",
                "last_name": "Tester",
                "role": "customer",
            },
        )
        assert reg.status_code == 201, f"Register failed: {reg.json()}"
        refresh_token = reg.json()["data"]["refresh_token"]

        response = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": refresh_token},
        )
        assert response.status_code == 200
        body = response.json()
        assert "access_token" in body
        assert "refresh_token" in body


class TestForgotPassword:
    async def test_forgot_password_existing_user(self, client: AsyncClient, customer_user) -> None:
        response = await client.post(
            "/api/v1/auth/forgot-password",
            json={"email": "customer@test.com"},
        )
        # Always 200 regardless of whether email exists (anti-enumeration)
        assert response.status_code == 200

    async def test_forgot_password_nonexistent_email(self, client: AsyncClient) -> None:
        response = await client.post(
            "/api/v1/auth/forgot-password",
            json={"email": "nobody@example.com"},
        )
        assert response.status_code == 200
