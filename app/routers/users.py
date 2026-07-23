"""
CLMStore — Users / Customer Profile Router
Manages customer profiles, addresses, favorites, and order history.
"""
from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, File, Path, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies.auth import get_current_active_user
from app.dependencies.pagination import PaginationParams
from app.exceptions.custom import ForbiddenException, NotFoundException
from app.models.user import User
from app.repositories.user_repository import UserAddressRepository, UserFavoriteRepository, UserRepository
from app.schemas.common import MessageResponse, PaginatedResponse
from app.schemas.user import (
    UserAddressCreate,
    UserAddressResponse,
    UserAddressUpdate,
    UserFavoriteResponse,
    UserProfileResponse,
    UserProfileUpdateRequest,
)
from app.services.file_service import FileService
from app.services.user_service import UserService

router = APIRouter()


# ── GET /api/v1/users/profile ─────────────────────────────────────────────────
@router.get(
    "/profile",
    response_model=UserProfileResponse,
    summary="Get current user profile",
)
async def get_profile(current_user: User = Depends(get_current_active_user)) -> UserProfileResponse:
    """Returns the authenticated user's full profile."""
    return UserProfileResponse.model_validate(current_user)


# ── PATCH /api/v1/users/profile ───────────────────────────────────────────────
@router.patch(
    "/profile",
    response_model=UserProfileResponse,
    summary="Update user profile",
)
async def update_profile(
    body: UserProfileUpdateRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> UserProfileResponse:
    """
    Update the authenticated user's profile fields.

    **Request Body:**
    ```json
    {
        "first_name": "John",
        "last_name": "Doe",
        "phone": "+23276123456"
    }
    ```
    """
    service = UserService(db)
    updated = await service.update_profile(current_user.id, body)
    return UserProfileResponse.model_validate(updated)


# ── POST /api/v1/users/profile/picture ───────────────────────────────────────
@router.post(
    "/profile/picture",
    response_model=UserProfileResponse,
    summary="Upload profile picture",
    description="Accepts JPEG, PNG or WebP images up to 10 MB.",
)
async def upload_profile_picture(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> UserProfileResponse:
    """
    Upload a profile picture. The image is stored in the configured storage backend.
    Returns the updated user profile with the new `profile_picture` URL.
    """
    file_service = FileService()
    url = await file_service.upload_image(file, folder="profiles")
    repo = UserRepository(db)
    current_user.profile_picture = url
    db.add(current_user)
    return UserProfileResponse.model_validate(current_user)


# ── GET /api/v1/users/addresses ──────────────────────────────────────────────
@router.get(
    "/addresses",
    response_model=List[UserAddressResponse],
    summary="List saved delivery addresses",
)
async def list_addresses(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> List[UserAddressResponse]:
    """Returns all saved delivery addresses for the authenticated user."""
    repo = UserAddressRepository(db)
    addresses = await repo.get_by_user_id(current_user.id)
    return [UserAddressResponse.model_validate(a) for a in addresses]


# ── POST /api/v1/users/addresses ─────────────────────────────────────────────
@router.post(
    "/addresses",
    response_model=UserAddressResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add a new delivery address",
)
async def add_address(
    body: UserAddressCreate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> UserAddressResponse:
    """
    Add a new saved address for the user.

    **Request Body:**
    ```json
    {
        "label": "Home",
        "address_line": "12 Wilkinson Road, Freetown",
        "city": "Freetown",
        "country": "Sierra Leone",
        "latitude": 8.4657,
        "longitude": -13.2317,
        "is_default": true,
        "notes": "Green gate, knock twice"
    }
    ```
    """
    service = UserService(db)
    address = await service.add_address(current_user.id, body)
    return UserAddressResponse.model_validate(address)


# ── PATCH /api/v1/users/addresses/{address_id} ───────────────────────────────
@router.patch(
    "/addresses/{address_id}",
    response_model=UserAddressResponse,
    summary="Update a saved delivery address",
)
async def update_address(
    address_id: int = Path(..., ge=1),
    body: UserAddressUpdate = ...,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> UserAddressResponse:
    service = UserService(db)
    address = await service.update_address(current_user.id, address_id, body)
    return UserAddressResponse.model_validate(address)


# ── DELETE /api/v1/users/addresses/{address_id} ──────────────────────────────
@router.delete(
    "/addresses/{address_id}",
    response_model=MessageResponse,
    summary="Delete a saved address",
)
async def delete_address(
    address_id: int = Path(..., ge=1),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    service = UserService(db)
    await service.delete_address(current_user.id, address_id)
    return MessageResponse(message="Address removed successfully.")


# ── POST /api/v1/users/addresses/{address_id}/set-default ───────────────────
@router.post(
    "/addresses/{address_id}/set-default",
    response_model=MessageResponse,
    summary="Set an address as the default",
)
async def set_default_address(
    address_id: int = Path(..., ge=1),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    service = UserService(db)
    await service.set_default_address(current_user.id, address_id)
    return MessageResponse(message="Default address updated.")


# ── GET /api/v1/users/favorites ──────────────────────────────────────────────
@router.get(
    "/favorites",
    response_model=List[UserFavoriteResponse],
    summary="List favourite restaurants",
)
async def list_favorites(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> List[UserFavoriteResponse]:
    repo = UserFavoriteRepository(db)
    favs = await repo.get_by_user_id(current_user.id)
    return [UserFavoriteResponse.model_validate(f) for f in favs]


# ── POST /api/v1/users/favorites/{restaurant_id} ─────────────────────────────
@router.post(
    "/favorites/{restaurant_id}",
    response_model=UserFavoriteResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add restaurant to favourites",
)
async def add_favorite(
    restaurant_id: int = Path(..., ge=1),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> UserFavoriteResponse:
    service = UserService(db)
    fav = await service.add_favorite(current_user.id, restaurant_id)
    return UserFavoriteResponse.model_validate(fav)


# ── DELETE /api/v1/users/favorites/{restaurant_id} ───────────────────────────
@router.delete(
    "/favorites/{restaurant_id}",
    response_model=MessageResponse,
    summary="Remove restaurant from favourites",
)
async def remove_favorite(
    restaurant_id: int = Path(..., ge=1),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    service = UserService(db)
    await service.remove_favorite(current_user.id, restaurant_id)
    return MessageResponse(message="Restaurant removed from favourites.")


# ── GET /api/v1/users/{user_id} ── KEEP LAST (catch-all) ─────────────────────
@router.get(
    "/{user_id}",
    response_model=UserProfileResponse,
    summary="Get user by ID (admin or self)",
)
async def get_user_by_id(
    user_id: int = Path(..., ge=1),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> UserProfileResponse:
    from app.utils.constants import UserRole
    if current_user.id != user_id and current_user.role not in (UserRole.ADMIN, UserRole.SUPER_ADMIN):
        raise ForbiddenException("You can only view your own profile.")
    repo = UserRepository(db)
    user = await repo.get(user_id)
    if not user:
        raise NotFoundException("User", user_id)
    return UserProfileResponse.model_validate(user)
