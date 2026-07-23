"""
CLMStore — Celery Application

Broker:  Redis (REDIS_URL)
Backend: Redis (REDIS_URL)

Registered task modules:
  app.tasks.orders   — auto-cancel stale orders, settlement retries
  app.tasks.notifications — SMS/email retry queue
"""
from __future__ import annotations

from celery import Celery
from celery.schedules import crontab

from app.config.settings import settings

celery_app = Celery(
    "clmstore",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=[
        "app.tasks.orders",
        "app.tasks.notifications",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    result_expires=3600,
    beat_schedule={
        # Auto-cancel orders that have been PENDING for > 15 minutes
        "cancel-stale-pending-orders": {
            "task": "app.tasks.orders.cancel_stale_orders",
            "schedule": crontab(minute="*/15"),
        },
        # Daily earnings settlement report
        "daily-settlement-report": {
            "task": "app.tasks.orders.send_daily_report",
            "schedule": crontab(hour=8, minute=0),
        },
    },
)
