"""
CLMStore — Order Service
Coordinates cart checkout, totals calculation (VAT, service fees, coupons), and order workflows.
"""
from __future__ import annotations

import random
from datetime import datetime, timezone
from typing import List, Optional

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import settings
from app.exceptions.custom import NotFoundException, BusinessRuleException, OrderStateException
from app.models.order import Order, OrderItem, OrderStatusHistory
from app.repositories.order_repository import OrderRepository, OrderStatusHistoryRepository
from app.repositories.cart_repository import CartRepository
from app.repositories.restaurant_repository import RestaurantRepository
from app.repositories.user_repository import UserAddressRepository, UserRepository
from app.repositories.coupon_repository import CouponUsageRepository
from app.schemas.order import OrderCreateRequest
from app.utils.constants import OrderStatus, NotificationType, PaymentStatus
from app.services.location_service import LocationService
from app.services.notification_service import NotificationService

logger = structlog.get_logger()


class OrderService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.order_repo = OrderRepository(db)
        self.history_repo = OrderStatusHistoryRepository(db)
        self.cart_repo = CartRepository(db)
        self.restaurant_repo = RestaurantRepository(db)
        self.address_repo = UserAddressRepository(db)
        self.user_repo = UserRepository(db)
        self.usage_repo = CouponUsageRepository(db)
        self.location_service = LocationService()
        self.notif_service = NotificationService(db)

    async def calculate_order_totals(self, cart_id: int, address_id: int) -> dict:
        """Calculate detailed financial breakdown for checkout."""
        cart = await self.cart_repo.get(cart_id)
        if not cart or not cart.items:
            raise BusinessRuleException("Cart is empty")

        restaurant = await self.restaurant_repo.get(cart.restaurant_id)
        if not restaurant:
            raise NotFoundException("Restaurant")

        address = await self.address_repo.get(address_id)
        if not address:
            raise NotFoundException("Address")

        subtotal = cart.subtotal

        # 1. Calculate Delivery Fee using Location details
        distance_km = 0.0
        if restaurant.latitude and restaurant.longitude and address.latitude and address.longitude:
            from app.utils.geo import haversine_distance
            distance_km = haversine_distance(
                restaurant.latitude, restaurant.longitude, address.latitude, address.longitude
            )
        # Check delivery radius
        if distance_km > restaurant.delivery_radius_km:
            raise BusinessRuleException(
                f"Address is outside the restaurant's delivery radius of {restaurant.delivery_radius_km} km"
            )

        delivery_fee = restaurant.delivery_fee
        if delivery_fee <= 0:
            # Fallback to dynamic distance calculation if restaurant has free default but charges dynamic
            from app.utils.geo import calculate_delivery_fee
            delivery_fee = calculate_delivery_fee(distance_km)

        # 2. Flat service fee — load from SystemSettings, fallback to config
        from app.models.system_settings import SystemSettings
        sys_settings = await SystemSettings.load(self.db)
        service_fee = sys_settings.service_fee

        # 3. Tax — internal accounting only, NOT added to customer total
        tax_amount = round(subtotal * sys_settings.tax_rate, 2)

        # 4. Coupon Discount
        discount_amount = 0.0
        if cart.coupon:
            coupon = cart.coupon
            from app.utils.constants import CouponType
            if coupon.type == CouponType.PERCENTAGE:
                discount_amount = round(subtotal * (coupon.value / 100), 2)
                if coupon.max_discount is not None:
                    discount_amount = min(discount_amount, coupon.max_discount)
            else:
                discount_amount = min(coupon.value, subtotal)

        # Tax is NOT added to customer total — it is an internal accounting figure
        total_amount = round(subtotal + delivery_fee + service_fee - discount_amount, 2)
        total_amount = max(total_amount, 0.0)

        # Estimate delivery duration
        from app.utils.geo import calculate_eta_minutes
        eta_min = calculate_eta_minutes(distance_km) + restaurant.avg_delivery_time_min

        return {
            "subtotal": subtotal,
            "delivery_fee": delivery_fee,
            "service_fee": service_fee,
            "tax_amount": tax_amount,
            "discount_amount": discount_amount,
            "total_amount": total_amount,
            "distance_km": round(distance_km, 2),
            "eta_min": eta_min,
            "address_snapshot": {
                "label": address.label,
                "address_line": address.address_line,
                "city": address.city,
                "latitude": address.latitude,
                "longitude": address.longitude,
            },
        }

    async def checkout_cart(self, user_id: int, schema: OrderCreateRequest) -> Order:
        """Convert the user's active cart into a pending order."""
        cart = await self.cart_repo.get_by_user_id(user_id)
        if not cart or len(cart.items) == 0:
            raise BusinessRuleException("Your cart is empty")

        # Calculate totals
        totals = await self.calculate_order_totals(cart.id, schema.delivery_address_id)

        # Generate unique order number (format: CLM-784562)
        rand_suffix = str(random.randint(100000, 999999))
        order_number = f"CLM-{rand_suffix}"

        # Create Order
        order = Order(
            order_number=order_number,
            user_id=user_id,
            restaurant_id=cart.restaurant_id,
            delivery_address_id=schema.delivery_address_id,
            coupon_id=cart.coupon_id,
            status=OrderStatus.PENDING,
            payment_method=schema.payment_method,
            payment_status="pending",
            subtotal=totals["subtotal"],
            delivery_fee=totals["delivery_fee"],
            service_fee=totals["service_fee"],
            tax_amount=totals["tax_amount"],
            discount_amount=totals["discount_amount"],
            total_amount=totals["total_amount"],
            delivery_address_snapshot=totals["address_snapshot"],
            delivery_distance_km=totals["distance_km"],
            estimated_delivery_min=totals["eta_min"],
            notes=schema.notes,
        )
        await self.order_repo.create(order)
        await self.db.flush()

        # Add Order Items
        for item in cart.items:
            order_item = OrderItem(
                order_id=order.id,
                menu_item_id=item.menu_item_id,
                name=item.menu_item.name,
                description=item.menu_item.description,
                unit_price=item.item_price,
                quantity=item.quantity,
                variants=[{"name": item.variant.name, "price_modifier": item.variant.price_modifier}] if item.variant else None,
                addons=item.addons,
                subtotal=item.subtotal,
            )
            self.db.add(order_item)

            # Deduct stock if limited
            if item.menu_item.stock_count is not None:
                item.menu_item.stock_count = max(item.menu_item.stock_count - item.quantity, 0)
                self.db.add(item.menu_item)

        # Record initial status history
        await self._add_status_history(order.id, OrderStatus.PENDING, "Order placed successfully", user_id)

        # Apply coupon usage to database if applicable
        if cart.coupon_id:
            from app.models.coupon import CouponUsage
            usage = CouponUsage(
                coupon_id=cart.coupon_id,
                user_id=user_id,
                order_id=order.id,
                discount_amount=totals["discount_amount"],
            )
            self.db.add(usage)
            # Increment coupon used count
            cart.coupon.used_count += 1
            self.db.add(cart.coupon)

        # Deactivate cart
        cart.is_active = False
        self.db.add(cart)

        await self.db.flush()

        # Notify restaurant owner
        restaurant = await self.restaurant_repo.get(order.restaurant_id)
        owner = await self.user_repo.get(restaurant.owner_id)
        if owner:
            await self.notif_service.dispatch_notification(
                user_id=owner.id,
                title="New Order Received",
                body=f"Order {order_number} has been placed. Action required.",
                notif_type=NotificationType.ORDER_PLACED,
                recipient_email=owner.email,
                recipient_phone=owner.phone,
                onesignal_player_id=owner.onesignal_player_id,
            )

        # Reload full details
        return await self.order_repo.get_with_details(order.id)

    async def transition_order_status(
        self, order_id: int, target_status: OrderStatus, changed_by: int, note: Optional[str] = None
    ) -> Order:
        """Handle state-machine transitions of orders safely."""
        order = await self.order_repo.get(order_id)
        if not order:
            raise NotFoundException("Order")

        current = order.status

        # Enforce valid transitions
        allowed = False
        if current == OrderStatus.PENDING:
            allowed = target_status in [OrderStatus.ACCEPTED, OrderStatus.CANCELLED]
        elif current == OrderStatus.ACCEPTED:
            allowed = target_status in [OrderStatus.PREPARING, OrderStatus.CANCELLED]
        elif current == OrderStatus.PREPARING:
            allowed = target_status in [OrderStatus.READY, OrderStatus.CANCELLED]
        elif current == OrderStatus.READY:
            allowed = target_status in [OrderStatus.PICKED_UP, OrderStatus.CANCELLED]
        elif current == OrderStatus.PICKED_UP:
            allowed = target_status in [OrderStatus.ON_THE_WAY]
        elif current == OrderStatus.ON_THE_WAY:
            allowed = target_status in [OrderStatus.DELIVERED, OrderStatus.CANCELLED]
        elif current == OrderStatus.DELIVERED:
            allowed = target_status == OrderStatus.REFUNDED

        if not allowed:
            raise OrderStateException(current.value, target_status.value)

        order.status = target_status
        self.db.add(order)

        await self._add_status_history(order_id, target_status, note or f"Order marked as {target_status.value}", changed_by)

        # Trigger customer alerts
        customer = await self.user_repo.get(order.user_id)
        if customer:
            notif_map = {
                OrderStatus.ACCEPTED: NotificationType.ORDER_ACCEPTED,
                OrderStatus.PREPARING: NotificationType.ORDER_PREPARING,
                OrderStatus.READY: NotificationType.ORDER_READY,
                OrderStatus.PICKED_UP: NotificationType.ORDER_PICKED_UP,
                OrderStatus.ON_THE_WAY: NotificationType.ORDER_ON_THE_WAY,
                OrderStatus.DELIVERED: NotificationType.ORDER_DELIVERED,
                OrderStatus.CANCELLED: NotificationType.ORDER_CANCELLED,
            }
            if target_status in notif_map:
                await self.notif_service.dispatch_notification(
                    user_id=customer.id,
                    title=f"Order Status: {target_status.value.title()}",
                    body=f"Your order {order.order_number} is now {target_status.value}.",
                    notif_type=notif_map[target_status],
                    recipient_email=customer.email,
                    recipient_phone=customer.phone,
                    onesignal_player_id=customer.onesignal_player_id,
                )

        # Trigger settlement when order is delivered
        if target_status == OrderStatus.DELIVERED:
            from app.services.settlement_service import SettlementService
            await SettlementService(self.db).settle_order(order)

        await self.db.flush()
        return await self.order_repo.get_with_details(order.id)

    async def cancel_order(self, order_id: int, user_id: int, reason: str) -> Order:
        """Cancel order if not already accepted/preparing."""
        order = await self.order_repo.get(order_id)
        if not order:
            raise NotFoundException("Order")

        # Customer can cancel before preparation begins (e.g. status == PENDING)
        # Admins or Owners can cancel at other stages
        user = await self.user_repo.get(user_id)
        if user.role == "customer" and order.status != OrderStatus.PENDING:
            raise BusinessRuleException("Cannot cancel order after restaurant has accepted it")

        order.cancellation_reason = reason
        self.db.add(order)

        # Return stock if cancelled
        for item in order.items:
            # We must load full items details
            db_item = await self.db.get(OrderItem, item.id)
            if db_item and db_item.menu_item_id:
                from app.models.menu import MenuItem
                menu_item = await self.db.get(MenuItem, db_item.menu_item_id)
                if menu_item and menu_item.stock_count is not None:
                    menu_item.stock_count += db_item.quantity
                    self.db.add(menu_item)

        return await self.transition_order_status(
            order_id, OrderStatus.CANCELLED, user_id, f"Cancelled: {reason}"
        )

    async def _add_status_history(
        self, order_id: int, status: OrderStatus, note: str, changed_by: int
    ) -> None:
        hist = OrderStatusHistory(
            order_id=order_id,
            status=status,
            note=note,
            changed_by=changed_by,
        )
        await self.history_repo.create(hist)
