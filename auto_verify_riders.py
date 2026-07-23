import asyncio
from sqlalchemy import select
from app.database import AsyncSessionLocal
from app.models.user import User
from app.models.rider import RiderProfile
from app.utils.constants import UserRole

async def verify_all_riders():
    async with AsyncSessionLocal() as session:
        # Find all users with role RIDER
        stmt = select(User).where(User.role == UserRole.RIDER)
        result = await session.execute(stmt)
        riders = result.scalars().all()

        print(f"Found {len(riders)} rider users in system.")

        for user in riders:
            # Check if rider profile exists
            stmt_p = select(RiderProfile).where(RiderProfile.user_id == user.id)
            res_p = await session.execute(stmt_p)
            profile = res_p.scalar_one_or_none()

            if not profile:
                print(f"Creating RiderProfile for {user.email} (ID: {user.id})...")
                profile = RiderProfile(
                    user_id=user.id,
                    vehicle_type="motorcycle",
                    vehicle_plate="SL-1001",
                    vehicle_model="Honda CG 125",
                    vehicle_color="Red",
                    is_available=True,
                    is_verified=True,
                )
                session.add(profile)
            else:
                print(f"Verifying existing RiderProfile for {user.email} (ID: {user.id})...")
                profile.is_verified = True
                profile.is_available = True
                session.add(profile)

        await session.commit()
        print("SUCCESS: All rider profiles verified and set to active/verified!")

if __name__ == "__main__":
    asyncio.run(verify_all_riders())
