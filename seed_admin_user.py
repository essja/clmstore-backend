import asyncio
import sys
from sqlalchemy import select
from app.database import AsyncSessionLocal
from app.models.user import User
from app.auth.password import hash_password
from app.utils.constants import UserRole

async def seed_admin():
    async with AsyncSessionLocal() as session:
        # Check if admin user exists
        stmt = select(User).where(User.email == "admin@clmstore.com")
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()

        if user:
            print("Found existing admin user admin@clmstore.com, updating password and role...")
            user.password_hash = hash_password("Admin@1234")
            user.role = UserRole.SUPER_ADMIN
            user.is_active = True
            user.is_email_verified = True
        else:
            print("Creating new super admin user admin@clmstore.com...")
            user = User(
                email="admin@clmstore.com",
                phone="+23276000000",
                password_hash=hash_password("Admin@1234"),
                first_name="Super",
                last_name="Admin",
                role=UserRole.SUPER_ADMIN,
                is_active=True,
                is_email_verified=True,
                is_phone_verified=True,
            )
            session.add(user)

        await session.commit()
        print("SUCCESS: Admin account created/updated!")
        print("Email: admin@clmstore.com")
        print("Password: Admin@1234")
        print("Role: super_admin")

if __name__ == "__main__":
    asyncio.run(seed_admin())
