import asyncio
from sqlalchemy import select
from app.database import AsyncSessionLocal
from app.models.user import User

async def list_users():
    async with AsyncSessionLocal() as session:
        stmt = select(User).order_by(User.created_at.desc())
        result = await session.execute(stmt)
        users = result.scalars().all()

        print(f"Total Users Found: {len(users)}")
        print("=" * 80)
        for u in users:
            print(f"ID: {u.id} | Email: {u.email} | Name: {u.first_name} {u.last_name} | Role: {u.role} | Phone: {u.phone} | Active: {u.is_active}")
        print("=" * 80)

if __name__ == "__main__":
    asyncio.run(list_users())
