"""
CLMStore — User Service
Handles profile updates, saved addresses, and user favorites.
"""
from __future__ import annotations

from typing import List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions.custom import NotFoundException, ConflictException, ForbiddenException
from app.models.user import User, UserAddress, UserFavorite
from app.repositories.user_repository import UserRepository, UserAddressRepository, UserFavoriteRepository
from app.schemas.user import UserProfileUpdateRequest, UserAddressCreate, UserAddressUpdate


class UserService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.user_repo = UserRepository(db)
        self.address_repo = UserAddressRepository(db)
        self.fav_repo = UserFavoriteRepository(db)

    async def get_profile(self, user_id: int) -> User:
        user = await self.user_repo.get(user_id)
        if not user or user.is_deleted:
            raise NotFoundException("User")
        return user

    async def update_profile(self, user_id: int, schema: UserProfileUpdateRequest) -> User:
        user = await self.get_profile(user_id)

        # Check phone uniqueness if modified
        if schema.phone and schema.phone != user.phone:
            existing = await self.user_repo.get_by_phone(schema.phone)
            if existing:
                raise ConflictException("Phone number already in use")
            user.is_phone_verified = False  # Reset phone verification flag on change

        return await self.user_repo.update(user, schema)

    async def update_avatar(self, user_id: int, file_url: str) -> User:
        user = await self.get_profile(user_id)
        user.profile_picture = file_url
        self.db.add(user)
        return user

    # ── User Address CRUD ─────────────────────────────────────────────────────
    async def list_addresses(self, user_id: int) -> List[UserAddress]:
        return await self.address_repo.get_by_user(user_id)

    async def add_address(self, user_id: int, schema: UserAddressCreate) -> UserAddress:
        return await self.create_address(user_id, schema)

    async def create_address(self, user_id: int, schema: UserAddressCreate) -> UserAddress:
        if schema.is_default:
            await self.address_repo.clear_default(user_id)

        addr = UserAddress(
            user_id=user_id,
            label=schema.label,
            address_line=schema.address_line,
            city=schema.city,
            country=schema.country,
            latitude=schema.latitude,
            longitude=schema.longitude,
            is_default=schema.is_default,
            notes=schema.notes,
        )
        return await self.address_repo.create(addr)

    async def update_address(self, user_id: int, address_id: int, schema: UserAddressUpdate) -> UserAddress:
        addr = await self.address_repo.get(address_id)
        if not addr or addr.user_id != user_id:
            raise NotFoundException("Address")

        if schema.is_default:
            await self.address_repo.clear_default(user_id)

        return await self.address_repo.update(addr, schema)

    async def delete_address(self, user_id: int, address_id: int) -> None:
        addr = await self.address_repo.get(address_id)
        if not addr or addr.user_id != user_id:
            raise NotFoundException("Address")
        await self.address_repo.delete(address_id)

    async def set_default_address(self, user_id: int, address_id: int) -> None:
        addr = await self.address_repo.get(address_id)
        if not addr or addr.user_id != user_id:
            raise NotFoundException("Address")
        await self.address_repo.clear_default(user_id)
        addr.is_default = True
        self.db.add(addr)

    # ── User Favorites CRUD ───────────────────────────────────────────────────
    async def list_favorites(self, user_id: int) -> List[UserFavorite]:
        return await self.fav_repo.get_by_user(user_id)

    async def add_favorite(self, user_id: int, restaurant_id: int) -> UserFavorite:
        # Check if already a favorite
        existing = await self.fav_repo.get_favorite(user_id, restaurant_id)
        if existing:
            return existing

        fav = UserFavorite(user_id=user_id, restaurant_id=restaurant_id)
        return await self.fav_repo.create(fav)

    async def remove_favorite(self, user_id: int, restaurant_id: int) -> None:
        existing = await self.fav_repo.get_favorite(user_id, restaurant_id)
        if not existing:
            raise NotFoundException("Favorite")
        await self.fav_repo.delete(existing.id)
