"""
CLMStore — Production Database Initializer

This script bootstraps the system with the minimum required data:
  - Super Admin and Admin accounts (credentials supplied via environment or CLI)
  - No fake restaurants, riders, or customers

Usage:
    python seed.py
    python seed.py --reset          # drops ALL tables first (destructive!)
    python seed.py --skip-if-seeded # exits safely if super admin already exists

Credentials are loaded from environment variables:
    SEED_SUPER_ADMIN_EMAIL         (required)
    SEED_SUPER_ADMIN_PASSWORD      (required, min 12 chars)
    SEED_SUPER_ADMIN_FIRST_NAME    (optional, default: "Super")
    SEED_SUPER_ADMIN_LAST_NAME     (optional, default: "Admin")
    SEED_SUPER_ADMIN_PHONE         (optional)
    SEED_ADMIN_EMAIL               (optional)
    SEED_ADMIN_PASSWORD            (optional, min 12 chars)
    SEED_ADMIN_FIRST_NAME          (optional, default: "Platform")
    SEED_ADMIN_LAST_NAME           (optional, default: "Admin")
    SEED_ADMIN_PHONE               (optional)
"""
from __future__ import annotations

import asyncio
import os
import sys

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config.settings import settings
from app.auth.password import hash_password
from app.models.user import User
from app.utils.constants import UserRole

engine = create_async_engine(settings.DATABASE_URL, echo=False)
SessionLocal = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)


def _require_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        print(f"[ERROR] Environment variable '{name}' is required but not set.")
        sys.exit(1)
    return value


def _validate_password(password: str, label: str) -> None:
    if len(password) < 12:
        print(f"[ERROR] {label} must be at least 12 characters long.")
        sys.exit(1)


async def _super_admin_exists(db: AsyncSession) -> bool:
    result = await db.execute(
        select(User).where(User.role == UserRole.SUPER_ADMIN).limit(1)
    )
    return result.scalars().first() is not None


async def seed_super_admin(db: AsyncSession) -> User:
    email = _require_env("SEED_SUPER_ADMIN_EMAIL")
    password = _require_env("SEED_SUPER_ADMIN_PASSWORD")
    _validate_password(password, "SEED_SUPER_ADMIN_PASSWORD")

    first_name = os.environ.get("SEED_SUPER_ADMIN_FIRST_NAME", "Super").strip()
    last_name = os.environ.get("SEED_SUPER_ADMIN_LAST_NAME", "Admin").strip()
    phone = os.environ.get("SEED_SUPER_ADMIN_PHONE", "").strip() or None

    result = await db.execute(select(User).where(User.email == email))
    existing = result.scalars().first()
    if existing:
        print(f"  [SKIP] Super admin already exists: {email}")
        return existing

    user = User(
        email=email,
        phone=phone,
        password_hash=hash_password(password),
        first_name=first_name,
        last_name=last_name,
        role=UserRole.SUPER_ADMIN,
        is_active=True,
        is_email_verified=True,
        is_phone_verified=bool(phone),
    )
    db.add(user)
    await db.flush()
    print(f"  [OK] Super admin created: {email}")
    return user


async def seed_admin(db: AsyncSession) -> User | None:
    email = os.environ.get("SEED_ADMIN_EMAIL", "").strip()
    password = os.environ.get("SEED_ADMIN_PASSWORD", "").strip()

    if not email:
        print("  [SKIP] SEED_ADMIN_EMAIL not set — skipping platform admin.")
        return None

    _validate_password(password, "SEED_ADMIN_PASSWORD")

    first_name = os.environ.get("SEED_ADMIN_FIRST_NAME", "Platform").strip()
    last_name = os.environ.get("SEED_ADMIN_LAST_NAME", "Admin").strip()
    phone = os.environ.get("SEED_ADMIN_PHONE", "").strip() or None

    result = await db.execute(select(User).where(User.email == email))
    existing = result.scalars().first()
    if existing:
        print(f"  [SKIP] Admin already exists: {email}")
        return existing

    user = User(
        email=email,
        phone=phone,
        password_hash=hash_password(password),
        first_name=first_name,
        last_name=last_name,
        role=UserRole.ADMIN,
        is_active=True,
        is_email_verified=True,
        is_phone_verified=bool(phone),
    )
    db.add(user)
    await db.flush()
    print(f"  [OK] Platform admin created: {email}")
    return user


async def run_seed(reset: bool = False, skip_if_seeded: bool = False) -> None:
    print("\nCLMStore — Production Initializer")
    print("=" * 40)

    from app.database import Base as AppBase

    async with engine.begin() as conn:
        if reset:
            print("  [WARN] Dropping all tables — this is irreversible!")
            await conn.run_sync(AppBase.metadata.drop_all)
            print("  [OK] Tables dropped.")
        print("  [OK] Ensuring all tables exist...")
        await conn.run_sync(AppBase.metadata.create_all)

    async with SessionLocal() as db:
        try:
            if skip_if_seeded:
                if await _super_admin_exists(db):
                    print("  [SKIP] System already seeded. Exiting.")
                    return

            print("\n-- Admin Accounts --")
            await seed_super_admin(db)
            await seed_admin(db)

            await db.commit()
            print("\n[DONE] System initialized successfully.")
            print("       Log in at /api/v1/docs with the credentials you set.\n")

        except Exception as e:
            await db.rollback()
            print(f"\n[FAIL] Initialization failed: {e}")
            raise


if __name__ == "__main__":
    reset = "--reset" in sys.argv
    skip_if_seeded = "--skip-if-seeded" in sys.argv

    if reset:
        confirm = input("Are you sure you want to DROP all tables? Type 'yes' to confirm: ")
        if confirm.strip().lower() != "yes":
            print("Aborted.")
            sys.exit(0)

    asyncio.run(run_seed(reset=reset, skip_if_seeded=skip_if_seeded))
