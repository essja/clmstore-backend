"""
CLMStore — Test Configuration and Fixtures
"""
from __future__ import annotations

from typing import AsyncGenerator

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.auth.password import hash_password
from app.models.user import User
from app.utils.constants import UserRole

# ── Test Database (in-memory SQLite for speed) ────────────────────────────────
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

test_engine = create_async_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

TestingSessionLocal = async_sessionmaker(
    bind=test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


@pytest_asyncio.fixture(scope="session", autouse=True)
async def create_tables() -> AsyncGenerator:
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def db() -> AsyncGenerator[AsyncSession, None]:
    async with TestingSessionLocal() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def client(db: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    async def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac

    app.dependency_overrides.clear()


# ── Seed Fixtures ─────────────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def customer_user(db: AsyncSession) -> User:
    user = User(
        email="customer@test.com",
        phone="+23276111111",
        password_hash=hash_password("Test@1234"),
        first_name="Test",
        last_name="Customer",
        role=UserRole.CUSTOMER,
        is_active=True,
        is_email_verified=True,
        is_phone_verified=True,
    )
    db.add(user)
    await db.flush()
    return user


@pytest_asyncio.fixture
async def restaurant_owner_user(db: AsyncSession) -> User:
    user = User(
        email="owner@test.com",
        phone="+23276222222",
        password_hash=hash_password("Test@1234"),
        first_name="Test",
        last_name="Owner",
        role=UserRole.RESTAURANT_OWNER,
        is_active=True,
        is_email_verified=True,
        is_phone_verified=True,
    )
    db.add(user)
    await db.flush()
    return user


@pytest_asyncio.fixture
async def rider_user(db: AsyncSession) -> User:
    user = User(
        email="rider@test.com",
        phone="+23276333333",
        password_hash=hash_password("Test@1234"),
        first_name="Test",
        last_name="Rider",
        role=UserRole.RIDER,
        is_active=True,
        is_email_verified=True,
        is_phone_verified=True,
    )
    db.add(user)
    await db.flush()
    return user


@pytest_asyncio.fixture
async def admin_user(db: AsyncSession) -> User:
    user = User(
        email="admin@test.com",
        phone="+23276444444",
        password_hash=hash_password("Admin@1234"),
        first_name="Platform",
        last_name="Admin",
        role=UserRole.ADMIN,
        is_active=True,
        is_email_verified=True,
        is_phone_verified=True,
    )
    db.add(user)
    await db.flush()
    return user


async def get_auth_token(client: AsyncClient, email: str, password: str) -> str:
    """Helper to get auth token for a test user.
    The API wraps the response: {"success": true, "data": {"access_token": "...", ...}}
    """
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    return resp.json()["data"]["access_token"]
