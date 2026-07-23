"""
CLMStore — Order Background Tasks
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone, timedelta

import structlog

from app.core.celery_app import celery_app

logger = structlog.get_logger()


def _run(coro):
    """Run an async coroutine inside a Celery (sync) task."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@celery_app.task(name="app.tasks.orders.cancel_stale_orders", bind=True, max_retries=3)
def cancel_stale_orders(self):
    """Auto-cancel PENDING orders that haven't been accepted within 15 minutes."""
    async def _cancel():
        from app.database import AsyncSessionLocal
        from app.models.order import Order
        from app.utils.constants import OrderStatus
        from sqlalchemy import select

        cutoff = datetime.now(timezone.utc) - timedelta(minutes=15)
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(Order).where(
                    Order.status == OrderStatus.PENDING,
                    Order.created_at < cutoff,
                )
            )
            stale = result.scalars().all()
            for order in stale:
                order.status = OrderStatus.CANCELLED
                order.cancellation_reason = "Auto-cancelled: restaurant did not respond within 15 minutes."
                db.add(order)
                logger.info("order_auto_cancelled", order_id=order.id, order_number=order.order_number)
            await db.commit()
            return len(stale)

    try:
        count = _run(_cancel())
        logger.info("stale_orders_cancelled", count=count)
    except Exception as exc:
        logger.error("cancel_stale_orders_failed", error=str(exc))
        raise self.retry(exc=exc, countdown=60)


@celery_app.task(name="app.tasks.orders.send_daily_report", bind=True, max_retries=2)
def send_daily_report(self):
    """Send a daily earnings summary email to super admins."""
    async def _report():
        from app.database import AsyncSessionLocal
        from app.models.order import Order
        from app.models.user import User
        from app.utils.constants import OrderStatus, UserRole
        from app.services.notification_service import NotificationService
        from sqlalchemy import select, func
        from datetime import date

        today_start = datetime.combine(date.today(), datetime.min.time()).replace(tzinfo=timezone.utc)

        async with AsyncSessionLocal() as db:
            revenue_result = await db.execute(
                select(func.sum(Order.total_amount)).where(
                    Order.status == OrderStatus.DELIVERED,
                    Order.created_at >= today_start,
                )
            )
            revenue = revenue_result.scalar_one_or_none() or 0.0

            orders_result = await db.execute(
                select(func.count(Order.id)).where(
                    Order.status == OrderStatus.DELIVERED,
                    Order.created_at >= today_start,
                )
            )
            order_count = orders_result.scalar_one_or_none() or 0

            admins_result = await db.execute(
                select(User).where(User.role.in_([UserRole.SUPER_ADMIN, UserRole.ADMIN]))
            )
            admins = admins_result.scalars().all()

            notif_service = NotificationService(db)
            for admin in admins:
                await notif_service.send_email(
                    to_email=admin.email,
                    subject=f"CLMStore Daily Report — {date.today()}",
                    body=(
                        f"Today's summary:\n\n"
                        f"  Orders delivered: {order_count}\n"
                        f"  Revenue: SLL {revenue:,.0f}\n\n"
                        f"Log in to the admin dashboard for full details."
                    ),
                )

    try:
        _run(_report())
        logger.info("daily_report_sent")
    except Exception as exc:
        logger.error("daily_report_failed", error=str(exc))
        raise self.retry(exc=exc, countdown=300)
