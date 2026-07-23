"""
CLMStore — Platform Analytics and Reports Service
"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import List

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.restaurant import Restaurant
from app.models.order import Order
from app.models.rider import RiderProfile
from app.schemas.admin import DashboardStatsResponse
from app.utils.constants import UserRole, OrderStatus


def _period_start(period: str) -> datetime:
    """Return UTC start of the requested period."""
    now = datetime.now(timezone.utc)
    if period == "today":
        return now.replace(hour=0, minute=0, second=0, microsecond=0)
    if period == "week":
        return now - timedelta(days=7)
    if period == "year":
        return now - timedelta(days=365)
    # default: month
    return now - timedelta(days=30)


class AnalyticsService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_dashboard_stats(self, period: str = "today") -> DashboardStatsResponse:
        """Fetch general platforms stats for Admin dashboard."""
        # 1. Total Customers
        c_res = await self.db.execute(select(func.count(User.id)).filter(User.role == UserRole.CUSTOMER))
        total_customers = c_res.scalar() or 0

        # 2. Total Restaurants
        rest_res = await self.db.execute(select(func.count(Restaurant.id)))
        total_restaurants = rest_res.scalar() or 0

        # 3. Total Riders
        rider_res = await self.db.execute(select(func.count(RiderProfile.id)))
        total_riders = rider_res.scalar() or 0

        # 4. Total Orders
        order_res = await self.db.execute(select(func.count(Order.id)))
        total_orders = order_res.scalar() or 0

        # 5. Financial metrics
        fin_res = await self.db.execute(
            select(
                func.sum(Order.total_amount),
                func.sum(Order.service_fee),
            )
        )
        fin_row = fin_res.first()
        total_revenue = float(fin_row[0] or 0.0) if fin_row else 0.0
        total_commission = float(fin_row[1] or 0.0) if fin_row else 0.0

        # 6. Status distribution
        status_res = await self.db.execute(
            select(Order.status, func.count(Order.id)).group_by(Order.status)
        )
        order_status_counts = {str(status.value): count for status, count in status_res.all()}

        # 7. Daily sales (last 7 days stub)
        daily_res = await self.db.execute(
            select(
                func.date_trunc("day", Order.created_at).label("day"),
                func.sum(Order.total_amount).label("sales"),
            )
            .group_by("day")
            .order_by("day")
            .limit(7)
        )
        daily_revenue = [{"date": str(row[0].date()), "revenue": float(row[1] or 0.0)} for row in daily_res.all()]

        return DashboardStatsResponse(
            total_customers=total_customers,
            total_restaurants=total_restaurants,
            total_riders=total_riders,
            total_orders=total_orders,
            total_revenue=total_revenue,
            total_commission=total_commission,
            order_status_counts=order_status_counts,
            daily_revenue=daily_revenue,
        )

    async def get_revenue_analytics(self, period: str = "month") -> dict:
        """Platform revenue breakdown for the given period."""
        since = _period_start(period)
        delivered_statuses = [OrderStatus.DELIVERED]

        base_q = select(
            func.sum(Order.total_amount),
            func.sum(Order.service_fee),
            func.sum(Order.tax_amount),
            func.sum(Order.subtotal),
            func.count(Order.id),
        ).filter(
            Order.created_at >= since,
            Order.status.in_(delivered_statuses),
        )
        res = await self.db.execute(base_q)
        row = res.first()

        gross = float(row[0] or 0)
        service_fees = float(row[1] or 0)
        tax = float(row[2] or 0)
        subtotal = float(row[3] or 0)
        order_count = int(row[4] or 0)

        commission_rate = 0.15
        commission = gross * commission_rate

        # Daily revenue breakdown
        daily_res = await self.db.execute(
            select(
                func.date_trunc("day", Order.created_at).label("day"),
                func.sum(Order.total_amount).label("revenue"),
                func.count(Order.id).label("orders"),
            )
            .filter(Order.created_at >= since, Order.status.in_(delivered_statuses))
            .group_by("day")
            .order_by("day")
        )
        daily = [
            {"date": str(r[0].date()), "revenue": float(r[1] or 0), "orders": int(r[2] or 0)}
            for r in daily_res.all()
        ]

        return {
            "period": period,
            "currency": "SLL",
            "gross_revenue": gross,
            "platform_commission": round(commission, 2),
            "service_fees_collected": service_fees,
            "tax_collected": tax,
            "net_payable_to_restaurants": round(gross - commission - service_fees - tax, 2),
            "total_orders": order_count,
            "average_order_value": round(gross / order_count, 2) if order_count else 0,
            "daily_breakdown": daily,
        }

    async def get_order_analytics(self, period: str = "month") -> dict:
        """Order volume and status breakdown for the given period."""
        since = _period_start(period)

        status_res = await self.db.execute(
            select(Order.status, func.count(Order.id))
            .filter(Order.created_at >= since)
            .group_by(Order.status)
        )
        status_counts = {str(s.value): c for s, c in status_res.all()}

        total = sum(status_counts.values())
        delivered = status_counts.get("delivered", 0)
        cancelled = status_counts.get("cancelled", 0)

        # Hourly distribution (useful for peak-hour staffing)
        hourly_res = await self.db.execute(
            select(
                func.date_part("hour", Order.created_at).label("hour"),
                func.count(Order.id).label("count"),
            )
            .filter(Order.created_at >= since)
            .group_by("hour")
            .order_by("hour")
        )
        hourly = [{"hour": int(r[0]), "orders": int(r[1])} for r in hourly_res.all()]

        return {
            "period": period,
            "total_orders": total,
            "delivered": delivered,
            "cancelled": cancelled,
            "completion_rate": round(delivered / total * 100, 1) if total else 0,
            "cancellation_rate": round(cancelled / total * 100, 1) if total else 0,
            "status_breakdown": status_counts,
            "hourly_distribution": hourly,
        }

    async def get_top_restaurants(self, limit: int = 10, period: str = "month") -> dict:
        """Top restaurants by revenue and order count."""
        since = _period_start(period)

        res = await self.db.execute(
            select(
                Order.restaurant_id,
                Restaurant.name,
                func.count(Order.id).label("orders"),
                func.sum(Order.subtotal).label("revenue"),
                func.avg(Order.subtotal).label("avg_order"),
            )
            .join(Restaurant, Restaurant.id == Order.restaurant_id)
            .filter(
                Order.created_at >= since,
                Order.status == OrderStatus.DELIVERED,
            )
            .group_by(Order.restaurant_id, Restaurant.name)
            .order_by(func.sum(Order.subtotal).desc())
            .limit(limit)
        )
        rows = res.all()

        return {
            "period": period,
            "top_restaurants": [
                {
                    "restaurant_id": r[0],
                    "name": r[1],
                    "orders": int(r[2] or 0),
                    "revenue": float(r[3] or 0),
                    "avg_order_value": round(float(r[4] or 0), 2),
                }
                for r in rows
            ],
        }

    async def get_top_riders(self, limit: int = 10, period: str = "month") -> dict:
        """Top riders by deliveries completed and earnings."""
        since = _period_start(period)
        from app.models.rider import RiderEarning, RiderProfile

        res = await self.db.execute(
            select(
                RiderProfile.user_id,
                User.first_name,
                User.last_name,
                func.count(RiderEarning.id).label("deliveries"),
                func.sum(RiderEarning.net_earning).label("earnings"),
            )
            .join(RiderProfile, RiderProfile.id == RiderEarning.rider_id)
            .join(User, User.id == RiderProfile.user_id)
            .filter(RiderEarning.created_at >= since)
            .group_by(RiderProfile.user_id, User.first_name, User.last_name)
            .order_by(func.count(RiderEarning.id).desc())
            .limit(limit)
        )
        rows = res.all()

        return {
            "period": period,
            "top_riders": [
                {
                    "rider_id": r[0],
                    "name": f"{r[1]} {r[2]}".strip(),
                    "deliveries": int(r[3] or 0),
                    "total_earnings": float(r[4] or 0),
                }
                for r in rows
            ],
        }
