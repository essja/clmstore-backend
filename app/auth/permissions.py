"""
CLMStore — Role-Based Permission Helpers
"""
from __future__ import annotations

from typing import Callable

from fastapi import Depends

from app.exceptions.custom import ForbiddenException
from app.utils.constants import UserRole


def require_roles(*roles: UserRole) -> Callable:
    """
    FastAPI dependency factory that enforces role-based access control.
    Usage:
        @router.get("/admin", dependencies=[Depends(require_roles(UserRole.ADMIN))])
    """
    from app.dependencies.auth import get_current_active_user  # avoid circular import
    from app.models.user import User

    async def _check(current_user: User = Depends(get_current_active_user)) -> User:
        if current_user.role not in roles:
            raise ForbiddenException(
                f"Access restricted to: {', '.join(r.value for r in roles)}"
            )
        return current_user

    return _check


def is_admin_or_super(current_user) -> bool:
    return current_user.role in (UserRole.ADMIN, UserRole.SUPER_ADMIN)


def is_restaurant_staff(current_user) -> bool:
    return current_user.role in (
        UserRole.RESTAURANT_OWNER,
        UserRole.ADMIN,
        UserRole.SUPER_ADMIN,
    )


def check_restaurant_ownership(restaurant_owner_id: int, current_user) -> None:
    """Raise ForbiddenException if user is not the restaurant owner or an admin."""
    if is_admin_or_super(current_user):
        return
    if current_user.id != restaurant_owner_id:
        raise ForbiddenException("You do not own this restaurant.")


def check_resource_ownership(resource_user_id: int, current_user) -> None:
    """Raise ForbiddenException if user does not own the resource and is not admin."""
    if is_admin_or_super(current_user):
        return
    if current_user.id != resource_user_id:
        raise ForbiddenException("You do not have access to this resource.")
