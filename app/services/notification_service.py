"""
CLMStore — Notification Dispatcher Service

Channel priority:
  1. WebSocket       — real-time while app is open (zero cost, instant)
  2. OneSignal push  — background/closed app on iOS and Android (one API call)
  3. Africa's Talking SMS — fallback for critical events; works on any phone
  4. Email (SMTP)    — receipts, password reset, non-urgent alerts
"""
from __future__ import annotations

import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

import africastalking
import httpx
import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import settings
from app.models.notification import Notification
from app.repositories.notification_repository import NotificationRepository
from app.utils.constants import NotificationChannel, NotificationType

logger = structlog.get_logger()

# Notification types that are critical enough to also send via SMS
_SMS_CRITICAL = {
    NotificationType.ORDER_PLACED,
    NotificationType.ORDER_ACCEPTED,
    NotificationType.ORDER_DELIVERED,
    NotificationType.ORDER_CANCELLED,
    NotificationType.PAYMENT_RECEIVED,
    NotificationType.PAYMENT_FAILED,
    NotificationType.ACCOUNT_VERIFIED,
}

_ONESIGNAL_API_URL = "https://onesignal.com/api/v1/notifications"


class NotificationService:
    def __init__(self, db: Optional[AsyncSession] = None) -> None:
        self.db = db
        if db:
            self.repo = NotificationRepository(db)

        # ── Africa's Talking SMS ──────────────────────────────────────────────
        if settings.AT_API_KEY:
            try:
                africastalking.initialize(settings.AT_USERNAME, settings.AT_API_KEY)
                self.sms_client = africastalking.SMS
            except Exception as e:
                logger.error("africastalking_init_failed", error=str(e))
                self.sms_client = None
        else:
            self.sms_client = None

    # ── Email ─────────────────────────────────────────────────────────────────
    async def send_email(self, recipient: str, subject: str, body_html: str) -> bool:
        if not settings.SMTP_USER or not settings.SMTP_PASSWORD:
            logger.info("smtp_not_configured", recipient=recipient, subject=subject)
            return True

        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = f"{settings.FROM_NAME} <{settings.FROM_EMAIL}>"
            msg["To"] = recipient
            msg.attach(MIMEText(body_html, "html"))

            if settings.SMTP_PORT == 465:
                with smtplib.SMTP_SSL(settings.SMTP_HOST, settings.SMTP_PORT) as server:
                    server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
                    server.sendmail(settings.FROM_EMAIL, recipient, msg.as_string())
            else:
                with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
                    if settings.SMTP_TLS:
                        server.starttls()
                    server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
                    server.sendmail(settings.FROM_EMAIL, recipient, msg.as_string())
            return True
        except Exception as e:
            logger.error("email_send_failed", error=str(e), recipient=recipient)
            return False

    # ── SMS ───────────────────────────────────────────────────────────────────
    async def send_sms(self, phone: str, message: str) -> bool:
        if not self.sms_client:
            logger.info("sms_not_configured", phone=phone, message=message)
            return True

        try:
            response = self.sms_client.send(
                message, [phone], sender_id=settings.AT_SENDER_ID or None
            )
            logger.info("sms_sent", phone=phone, response=response)
            return True
        except Exception as e:
            logger.error("sms_send_failed", error=str(e), phone=phone)
            return False

    # ── OneSignal Push ────────────────────────────────────────────────────────
    async def send_push(
        self,
        player_id: str,
        title: str,
        body: str,
        data: Optional[dict] = None,
    ) -> bool:
        """
        Send a push notification via OneSignal's REST API.

        One API call — works on iOS and Android.
        Register your app at https://onesignal.com, get your App ID and REST API Key,
        then set ONESIGNAL_APP_ID and ONESIGNAL_REST_API_KEY in your .env file.
        """
        if not settings.ONESIGNAL_APP_ID or not settings.ONESIGNAL_REST_API_KEY:
            logger.info("onesignal_not_configured", player_id=player_id)
            return True

        if not player_id:
            return True

        payload: dict = {
            "app_id": settings.ONESIGNAL_APP_ID,
            "include_player_ids": [player_id],
            "headings": {"en": title},
            "contents": {"en": body},
        }
        if data:
            payload["data"] = data

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    _ONESIGNAL_API_URL,
                    json=payload,
                    headers={
                        "Authorization": f"Basic {settings.ONESIGNAL_REST_API_KEY}",
                        "Content-Type": "application/json",
                    },
                )
            if response.status_code == 200:
                logger.info("onesignal_push_sent", player_id=player_id)
                return True
            else:
                logger.warning(
                    "onesignal_push_failed",
                    player_id=player_id,
                    status=response.status_code,
                    body=response.text,
                )
                return False
        except Exception as e:
            logger.error("onesignal_push_error", error=str(e), player_id=player_id)
            return False

    # ── Main dispatcher ───────────────────────────────────────────────────────
    async def dispatch_notification(
        self,
        user_id: int,
        title: str,
        body: str,
        notif_type: NotificationType,
        recipient_email: Optional[str] = None,
        recipient_phone: Optional[str] = None,
        onesignal_player_id: Optional[str] = None,
        data: Optional[dict] = None,
    ) -> None:
        """
        Dispatches a notification across all appropriate channels:

          1. Saves to DB (always) — drives the in-app notification bell
          2. OneSignal push — if player_id is set (iOS + Android)
          3. SMS — only for critical event types listed in _SMS_CRITICAL
          4. Email — if recipient_email is provided

        WebSocket notifications are pushed separately by the router/service
        layer that calls push_notification_to_user() from websocket.py.
        """
        # Load user notification preferences from DB
        pref_email = pref_sms = pref_push = pref_in_app = True
        if self.db and user_id:
            from app.repositories.user_repository import UserRepository
            _u = await UserRepository(self.db).get(user_id)
            if _u:
                pref_email   = _u.notif_email
                pref_sms     = _u.notif_sms
                pref_push    = _u.notif_push
                pref_in_app  = _u.notif_in_app

        # 1. Save to DB for in-app notification history
        if self.db and pref_in_app:
            db_notif = Notification(
                user_id=user_id,
                title=title,
                body=body,
                type=notif_type,
                channel=NotificationChannel.IN_APP,
                data=data,
                is_read=False,
            )
            await self.repo.create(db_notif)

        # 2. OneSignal push notification
        if onesignal_player_id and pref_push:
            await self.send_push(onesignal_player_id, title, body, data)

        # 3. SMS — only for critical events (order placed, delivered, payment, etc.)
        if recipient_phone and notif_type in _SMS_CRITICAL and pref_sms:
            sms_text = f"[{settings.APP_NAME}] {title}: {body}"
            await self.send_sms(recipient_phone, sms_text)

        # 4. Email
        if recipient_email and pref_email:
            await self.send_email(
                recipient_email,
                title,
                f"<h3>{title}</h3><p>{body}</p>",
            )

    # ── In-app inbox (router-facing) ──────────────────────────────────────────

    async def get_notifications(
        self,
        user_id: int,
        unread_only: bool = False,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list, int]:
        from sqlalchemy import select, func
        from app.models.notification import Notification
        stmt = select(Notification).filter(Notification.user_id == user_id)
        if unread_only:
            stmt = stmt.filter(Notification.is_read == False)
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total_res = await self.db.execute(count_stmt)
        total = total_res.scalar() or 0
        stmt = stmt.order_by(Notification.created_at.desc()).offset(skip).limit(limit)
        result = await self.db.execute(stmt)
        return list(result.scalars().all()), total

    async def get_unread_count(self, user_id: int) -> int:
        from sqlalchemy import select, func
        from app.models.notification import Notification
        res = await self.db.execute(
            select(func.count(Notification.id)).filter(
                Notification.user_id == user_id,
                Notification.is_read == False,
            )
        )
        return res.scalar() or 0

    async def mark_read(self, notification_id: int, user_id: int) -> None:
        from app.models.notification import Notification
        notif = await self.repo.get(notification_id)
        if notif and notif.user_id == user_id:
            notif.is_read = True
            self.db.add(notif)

    async def mark_all_read(self, user_id: int) -> None:
        await self.repo.mark_all_as_read(user_id)

    async def delete_notification(self, notification_id: int, user_id: int) -> None:
        from app.exceptions.custom import NotFoundException, ForbiddenException
        notif = await self.repo.get(notification_id)
        if not notif:
            raise NotFoundException("Notification", notification_id)
        if notif.user_id != user_id:
            raise ForbiddenException()
        await self.repo.delete(notification_id)

    async def get_preferences(self, user_id: int) -> "NotificationPreferencesResponse":
        from app.schemas.notification import NotificationPreferencesResponse
        from app.repositories.user_repository import UserRepository
        user = await UserRepository(self.db).get(user_id)
        if not user:
            return NotificationPreferencesResponse(
                email_enabled=True, sms_enabled=True, push_enabled=True, in_app_enabled=True
            )
        return NotificationPreferencesResponse(
            email_enabled=user.notif_email,
            sms_enabled=user.notif_sms,
            push_enabled=user.notif_push,
            in_app_enabled=user.notif_in_app,
        )

    async def update_preferences(
        self, user_id: int, body: "NotificationPreferencesUpdate"
    ) -> "NotificationPreferencesResponse":
        from app.schemas.notification import NotificationPreferencesResponse
        from app.repositories.user_repository import UserRepository
        user_repo = UserRepository(self.db)
        user = await user_repo.get(user_id)
        if not user:
            from app.exceptions.custom import NotFoundException
            raise NotFoundException("User")
        updates = body.model_dump(exclude_unset=True)
        if "email_enabled" in updates:
            user.notif_email = updates["email_enabled"]
        if "sms_enabled" in updates:
            user.notif_sms = updates["sms_enabled"]
        if "push_enabled" in updates:
            user.notif_push = updates["push_enabled"]
        if "in_app_enabled" in updates:
            user.notif_in_app = updates["in_app_enabled"]
        self.db.add(user)
        await self.db.flush()
        return NotificationPreferencesResponse(
            email_enabled=user.notif_email,
            sms_enabled=user.notif_sms,
            push_enabled=user.notif_push,
            in_app_enabled=user.notif_in_app,
        )
