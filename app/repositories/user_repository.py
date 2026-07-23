"""
CLMStore — User Repository
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User, UserAddress, UserFavorite, RefreshToken, OTPVerification
from app.repositories.base import BaseRepository


class UserRepository(BaseRepository[User]):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(User, db)

    async def get_by_email(self, email: str) -> Optional[User]:
        result = await self.db.execute(select(User).filter(User.email == email, User.is_deleted == False))
        return result.scalars().first()

    async def get_by_phone(self, phone: str) -> Optional[User]:
        result = await self.db.execute(select(User).filter(User.phone == phone, User.is_deleted == False))
        return result.scalars().first()

    async def get_by_oauth(self, provider: str, oauth_id: str) -> Optional[User]:
        result = await self.db.execute(
            select(User).filter(
                User.oauth_provider == provider,
                User.oauth_id == oauth_id,
                User.is_deleted == False,
            )
        )
        return result.scalars().first()

    async def search_users(
        self,
        role: Optional[str] = None,
        is_active: Optional[bool] = None,
        query: Optional[str] = None,
        skip: int = 0,
        limit: int = 20,
    ) -> tuple[list, int]:
        from sqlalchemy import func, or_
        stmt = select(User).filter(User.is_deleted == False)
        if role is not None:
            stmt = stmt.filter(User.role == role)
        if is_active is not None:
            stmt = stmt.filter(User.is_active == is_active)
        if query:
            stmt = stmt.filter(
                or_(
                    User.first_name.ilike(f"%{query}%"),
                    User.last_name.ilike(f"%{query}%"),
                    User.email.ilike(f"%{query}%"),
                    User.phone.ilike(f"%{query}%"),
                )
            )
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total_res = await self.db.execute(count_stmt)
        total = total_res.scalar() or 0
        stmt = stmt.order_by(User.created_at.desc()).offset(skip).limit(limit)
        result = await self.db.execute(stmt)
        return list(result.scalars().all()), total


class UserAddressRepository(BaseRepository[UserAddress]):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(UserAddress, db)

    async def get_by_user(self, user_id: int) -> List[UserAddress]:
        result = await self.db.execute(select(UserAddress).filter(UserAddress.user_id == user_id))
        return list(result.scalars().all())

    async def get_by_user_id(self, user_id: int) -> List[UserAddress]:
        return await self.get_by_user(user_id)

    async def clear_default(self, user_id: int) -> None:
        """Set is_default = False for all addresses of this user."""
        addresses = await self.get_by_user(user_id)
        for addr in addresses:
            if addr.is_default:
                addr.is_default = False
                self.db.add(addr)
        await self.db.flush()


class UserFavoriteRepository(BaseRepository[UserFavorite]):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(UserFavorite, db)

    async def get_by_user(self, user_id: int) -> List[UserFavorite]:
        result = await self.db.execute(select(UserFavorite).filter(UserFavorite.user_id == user_id))
        return list(result.scalars().all())

    async def get_by_user_id(self, user_id: int) -> List[UserFavorite]:
        return await self.get_by_user(user_id)

    async def get_favorite(self, user_id: int, restaurant_id: int) -> Optional[UserFavorite]:
        result = await self.db.execute(
            select(UserFavorite).filter(
                UserFavorite.user_id == user_id,
                UserFavorite.restaurant_id == restaurant_id,
            )
        )
        return result.scalars().first()


class RefreshTokenRepository(BaseRepository[RefreshToken]):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(RefreshToken, db)

    async def get_by_hash(self, token_hash: str) -> Optional[RefreshToken]:
        result = await self.db.execute(
            select(RefreshToken).filter(
                RefreshToken.token_hash == token_hash,
                RefreshToken.is_revoked == False,
                RefreshToken.expires_at > datetime.now(timezone.utc),
            )
        )
        return result.scalars().first()

    async def create_or_replace(self, token: RefreshToken) -> RefreshToken:
        """Insert a refresh token, removing any existing row with the same hash first."""
        existing = await self.db.execute(
            select(RefreshToken).filter(RefreshToken.token_hash == token.token_hash)
        )
        dup = existing.scalars().first()
        if dup:
            await self.db.delete(dup)
            await self.db.flush()
        self.db.add(token)
        await self.db.flush()
        return token

    async def revoke_all_for_user(self, user_id: int) -> None:
        result = await self.db.execute(
            select(RefreshToken).filter(
                RefreshToken.user_id == user_id, RefreshToken.is_revoked == False
            )
        )
        for token in result.scalars().all():
            token.is_revoked = True
            self.db.add(token)
        await self.db.flush()


class OTPVerificationRepository(BaseRepository[OTPVerification]):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(OTPVerification, db)

    async def get_valid_otp(self, user_id: int, code: str, purpose: str) -> Optional[OTPVerification]:
        result = await self.db.execute(
            select(OTPVerification).filter(
                OTPVerification.user_id == user_id,
                OTPVerification.otp_code == code,
                OTPVerification.purpose == purpose,
                OTPVerification.is_used == False,
                OTPVerification.expires_at > datetime.now(timezone.utc),
            )
        )
        return result.scalars().first()
