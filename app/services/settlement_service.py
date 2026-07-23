"""
CLMStore — Settlement Service

Called when an order reaches DELIVERED status.
Automatically:
  1. Calculates what the restaurant earns (subtotal - platform commission)
  2. Calculates what the rider earns (delivery_fee - rider commission rate)
  3. Credits both balances
  4. Creates an earning record for audit trail
"""
from __future__ import annotations

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.restaurant import Restaurant, RestaurantEarning
from app.models.rider import RiderProfile, RiderEarning
from app.models.order import Order
from app.models.delivery import Delivery
from app.models.system_settings import SystemSettings
from app.utils.constants import EarningsStatus

logger = structlog.get_logger()

# Platform keeps this % of the delivery fee paid by the customer
RIDER_COMMISSION_RATE = 0.10  # 10% of delivery fee goes to platform


class SettlementService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def settle_order(self, order: Order) -> None:
        """
        Settle earnings for both the restaurant and the rider
        when an order is marked as delivered.
        Idempotent — skips if an earning record already exists for this order.
        """
        await self._settle_restaurant(order)
        await self._settle_rider(order)
        logger.info("settlement.complete", order_id=order.id, order_number=order.order_number)

    async def _settle_restaurant(self, order: Order) -> None:
        # Idempotency check
        existing = await self.db.execute(
            select(RestaurantEarning).where(RestaurantEarning.order_id == order.id)
        )
        if existing.scalar_one_or_none():
            return

        restaurant = await self.db.get(Restaurant, order.restaurant_id)
        if not restaurant:
            logger.warning("settlement.restaurant_not_found", order_id=order.id)
            return

        gross = order.subtotal  # customer subtotal (excluding delivery fee + service fee)
        commission_rate = restaurant.commission_rate  # e.g. 0.15
        commission_amount = round(gross * commission_rate, 2)
        net = round(gross - commission_amount, 2)

        earning = RestaurantEarning(
            restaurant_id=restaurant.id,
            order_id=order.id,
            gross_amount=gross,
            commission_rate=commission_rate,
            commission_amount=commission_amount,
            net_amount=net,
            status="settled",
        )
        self.db.add(earning)

        restaurant.current_balance = round(restaurant.current_balance + net, 2)
        restaurant.total_earnings = round(restaurant.total_earnings + net, 2)
        self.db.add(restaurant)

        logger.info(
            "settlement.restaurant",
            restaurant_id=restaurant.id,
            order_id=order.id,
            net=net,
            commission=commission_amount,
        )

    async def _settle_rider(self, order: Order) -> None:
        # Find the delivery for this order
        delivery_result = await self.db.execute(
            select(Delivery).where(Delivery.order_id == order.id)
        )
        delivery = delivery_result.scalar_one_or_none()
        if not delivery or not delivery.rider_id:
            return  # No rider assigned

        # Idempotency check
        existing = await self.db.execute(
            select(RiderEarning).where(RiderEarning.order_id == order.id)
        )
        if existing.scalar_one_or_none():
            return

        rider = await self.db.get(RiderProfile, delivery.rider_id)
        if not rider:
            logger.warning("settlement.rider_not_found", delivery_id=delivery.id)
            return

        delivery_fee = order.delivery_fee
        commission = round(delivery_fee * RIDER_COMMISSION_RATE, 2)
        net_earning = round(delivery_fee - commission, 2)

        earning = RiderEarning(
            rider_id=rider.id,
            order_id=order.id,
            amount=delivery_fee,
            commission_deducted=commission,
            net_earning=net_earning,
            status=EarningsStatus.AVAILABLE,
        )
        self.db.add(earning)

        rider.current_balance = round(rider.current_balance + net_earning, 2)
        rider.total_earnings = round(rider.total_earnings + net_earning, 2)
        rider.total_deliveries += 1
        self.db.add(rider)

        logger.info(
            "settlement.rider",
            rider_id=rider.id,
            order_id=order.id,
            net=net_earning,
            commission=commission,
        )
