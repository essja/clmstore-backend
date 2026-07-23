"""
CLMStore — Authentication and Authorization Dependencies
Extracts JWT tokens and validates role permissions on route endpoints.
"""
from __future__ import annotations

from fastapi import Depends, Header
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.jwt import decode_token
from app.exceptions.custom import UnauthorizedException, ForbiddenException
from app.models.user import User
from app.database import get_db
from app.repositories.user_repository import UserRepository
from app.utils.constants import UserRole

# Standard OAuth2 scheme for Swagger UI auth integration
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Extract and validate the active user from the JWT header token."""
    payload = decode_token(token, expected_type="access")
    user_id_str = payload.get("sub")
    if not user_id_str:
        raise UnauthorizedException("Malformed token: sub claim is missing")

    try:
        user_id = int(user_id_str)
    except ValueError:
        raise UnauthorizedException("Malformed token: invalid subject claim type")

    repo = UserRepository(db)
    user = await repo.get(user_id)
    if not user or user.is_deleted:
        raise UnauthorizedException("Your session is invalid or user does not exist")

    return user


async def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """Ensure user profile is not suspended or disabled."""
    if not current_user.is_active:
        raise ForbiddenException("Your account is suspended")
    return current_user


class RoleChecker:
    def __init__(self, allowed_roles: List[UserRole]) -> None:
        self.allowed_roles = allowed_roles

    def __call__(self, user: User = Depends(get_current_active_user)) -> User:
        if user.role not in self.allowed_roles:
            raise ForbiddenException(
                f"Requires one of the following permissions: {', '.join(r.value for r in self.allowed_roles)}"
            )
        return user
