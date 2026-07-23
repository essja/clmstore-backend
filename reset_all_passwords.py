import asyncio
from sqlalchemy import select
from app.database import AsyncSessionLocal
from app.models.user import User
from app.auth.password import hash_password

async def reset_passwords():
    async with AsyncSessionLocal() as session:
        stmt = select(User)
        result = await session.execute(stmt)
        users = result.scalars().all()

        passwords_map = {}

        for user in users:
            if "admin" in user.role.value.lower():
                pwd = "Admin@1234"
            else:
                pwd = "Password123!"
            
            user.password_hash = hash_password(pwd)
            passwords_map[user.email] = pwd

        await session.commit()
        print("PASSWORDS_RESET_SUCCESS")
        for email, pwd in passwords_map.items():
            print(f"EMAIL:{email} | PASSWORD:{pwd}")

if __name__ == "__main__":
    asyncio.run(reset_passwords())
