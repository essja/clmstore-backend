"""
CLMStore — Notification Retry Tasks
Handles SMS and push notification retries for critical events.
"""
from __future__ import annotations

import asyncio
import structlog

from app.core.celery_app import celery_app

logger = structlog.get_logger()


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@celery_app.task(name="app.tasks.notifications.send_sms_async", bind=True, max_retries=3)
def send_sms_async(self, phone: str, message: str):
    """Send an SMS via Africa's Talking with automatic retry on failure."""
    async def _send():
        from app.services.notification_service import NotificationService
        service = NotificationService()
        return await service.send_sms(phone, message)

    try:
        success = _run(_send())
        if not success:
            raise RuntimeError("SMS delivery returned False")
        logger.info("sms_task_sent", phone=phone)
    except Exception as exc:
        logger.warning("sms_task_retry", phone=phone, attempt=self.request.retries)
        raise self.retry(exc=exc, countdown=30 * (2 ** self.request.retries))


@celery_app.task(name="app.tasks.notifications.send_push_async", bind=True, max_retries=3)
def send_push_async(self, player_id: str, title: str, body: str, data: dict | None = None):
    """Send a OneSignal push notification with retry."""
    async def _send():
        from app.services.notification_service import NotificationService
        service = NotificationService()
        return await service.send_push(player_id, title, body, data)

    try:
        success = _run(_send())
        if not success:
            raise RuntimeError("Push delivery returned False")
        logger.info("push_task_sent", player_id=player_id)
    except Exception as exc:
        logger.warning("push_task_retry", player_id=player_id, attempt=self.request.retries)
        raise self.retry(exc=exc, countdown=15 * (2 ** self.request.retries))
