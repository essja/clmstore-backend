"""
CLMStore — Notifications Router
"""
from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, Path, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies.auth import get_current_active_user
from app.dependencies.pagination import PaginationParams
from app.models.user import User
from app.schemas.common import MessageResponse, PaginatedResponse
from app.schemas.notification import (
    NotificationPreferencesResponse,
    NotificationPreferencesUpdate,
    NotificationResponse,
)
from app.services.notification_service import NotificationService

router = APIRouter()


# ── GET /api/v1/notifications ────────────────────────────────────────────────
@router.get(
    "",
    response_model=PaginatedResponse[NotificationResponse],
    summary="List user notifications",
)
async def list_notifications(
    unread_only: bool = False,
    pagination: PaginationParams = Depends(),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> PaginatedResponse[NotificationResponse]:
    """Returns all in-app notifications for the authenticated user, newest first."""
    service = NotificationService(db)
    notifications, total = await service.get_notifications(
        user_id=current_user.id,
        unread_only=unread_only,
        skip=pagination.skip,
        limit=pagination.limit,
    )
    return PaginatedResponse(
        data=[NotificationResponse.model_validate(n) for n in notifications],
        pagination=pagination.meta(total),
    )


# ── GET /api/v1/notifications/unread-count ───────────────────────────────────
@router.get(
    "/unread-count",
    summary="Get count of unread notifications",
)
async def unread_count(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    **Response:**
    ```json
    {"unread_count": 5}
    ```
    """
    service = NotificationService(db)
    count = await service.get_unread_count(current_user.id)
    return {"unread_count": count}


# ── POST /api/v1/notifications/{notification_id}/read ────────────────────────
@router.post(
    "/{notification_id}/read",
    response_model=MessageResponse,
    summary="Mark notification as read",
)
async def mark_as_read(
    notification_id: int = Path(..., ge=1),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    service = NotificationService(db)
    await service.mark_read(notification_id, current_user.id)
    return MessageResponse(message="Notification marked as read.")


# ── POST /api/v1/notifications/mark-all-read ─────────────────────────────────
@router.post(
    "/mark-all-read",
    response_model=MessageResponse,
    summary="Mark all notifications as read",
)
async def mark_all_read(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    service = NotificationService(db)
    await service.mark_all_read(current_user.id)
    return MessageResponse(message="All notifications marked as read.")


# ── DELETE /api/v1/notifications/{notification_id} ───────────────────────────
@router.delete(
    "/{notification_id}",
    response_model=MessageResponse,
    summary="Delete a notification",
)
async def delete_notification(
    notification_id: int = Path(..., ge=1),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    service = NotificationService(db)
    await service.delete_notification(notification_id, current_user.id)
    return MessageResponse(message="Notification deleted.")


# ── GET /api/v1/notifications/preferences ────────────────────────────────────
@router.get(
    "/preferences",
    response_model=NotificationPreferencesResponse,
    summary="Get notification preferences",
)
async def get_preferences(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> NotificationPreferencesResponse:
    service = NotificationService(db)
    prefs = await service.get_preferences(current_user.id)
    return prefs


# ── PATCH /api/v1/notifications/preferences ──────────────────────────────────
@router.patch(
    "/preferences",
    response_model=NotificationPreferencesResponse,
    summary="Update notification preferences",
)
async def update_preferences(
    body: NotificationPreferencesUpdate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> NotificationPreferencesResponse:
    """
    **Request Body:**
    ```json
    {
        "email_enabled": true,
        "sms_enabled": false,
        "push_enabled": true,
        "in_app_enabled": true
    }
    ```
    """
    service = NotificationService(db)
    prefs = await service.update_preferences(current_user.id, body)
    return prefs


# ── POST /api/v1/notifications/device-token ──────────────────────────────────
@router.post(
    "/device-token",
    response_model=MessageResponse,
    summary="Register OneSignal Player ID for push notifications",
)
async def update_device_token(
    player_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    """
    Called by the mobile app after OneSignal SDK initializes.
    The app passes the OneSignal Player ID so the server can send
    push notifications to this specific device (iOS or Android).
    """
    current_user.onesignal_player_id = player_id
    db.add(current_user)
    return MessageResponse(message="Device registered for push notifications.")
