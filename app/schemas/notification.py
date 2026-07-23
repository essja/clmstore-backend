"""
CLMStore — Notification Pydantic Schemas
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel

from app.utils.constants import NotificationType, NotificationChannel


class NotificationResponse(BaseModel):
    id: int
    user_id: int
    title: str
    body: str
    type: NotificationType
    channel: NotificationChannel
    data: Optional[dict]
    is_read: bool
    created_at: datetime

    class Config:
        from_attributes = True


class NotificationPreferencesResponse(BaseModel):
    email_enabled: bool = True
    sms_enabled: bool = True
    push_enabled: bool = True
    in_app_enabled: bool = True


class NotificationPreferencesUpdate(BaseModel):
    email_enabled: Optional[bool] = None
    sms_enabled: Optional[bool] = None
    push_enabled: Optional[bool] = None
    in_app_enabled: Optional[bool] = None
