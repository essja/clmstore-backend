"""
CLMStore — Delivery Coordination Service
Handles rider GPS coordinates, automatic assignment, live tracking, and WebSocket routes.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Dict, List, Optional, Set

import structlog
from fastapi import WebSocket
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions.custom import NotFoundException, BusinessRuleException, ForbiddenException
from app.models.delivery import Delivery, RiderLocation
from app.models.rider import RiderProfile
from app.repositories.delivery_repository import DeliveryRepository, RiderLocationRepository
from app.repositories.rider_repository import RiderProfileRepository
from app.repositories.order_repository import OrderRepository
from app.repositories.user_repository import UserRepository
from app.utils.constants import DeliveryStatus, OrderStatus, NotificationType
from app.services.notification_service import NotificationService

logger = structlog.get_logger()


# ── Active WebSocket Connections Manager ─────────────────────────────────────
class ConnectionManager:
    def __init__(self) -> None:
        # Map of delivery_id -> set of active WebSockets (customers + admins tracking the rider)
        self.active_connections: Dict[int, Set[WebSocket]] = {}
        # Map of rider_id -> set of active WebSockets (riders uploading GPS)
        self.rider_connections: Dict[int, WebSocket] = {}

    async def connect_tracker(self, delivery_id: int, websocket: WebSocket) -> None:
        await websocket.accept()
        if delivery_id not in self.active_connections:
            self.active_connections[delivery_id] = set()
        self.active_connections[delivery_id].add(websocket)

    def disconnect_tracker(self, delivery_id: int, websocket: WebSocket) -> None:
        if delivery_id in self.active_connections:
            self.active_connections[delivery_id].discard(websocket)
            if not self.active_connections[delivery_id]:
                del self.active_connections[delivery_id]

    async def broadcast_location(self, delivery_id: int, message: dict) -> None:
        if delivery_id in self.active_connections:
            # Broadcast to all connected listeners
            disconnected = set()
            for connection in self.active_connections[delivery_id]:
                try:
                    await connection.send_json(message)
                except Exception:
                    disconnected.add(connection)

            for conn in disconnected:
                self.disconnect_tracker(delivery_id, conn)


gps_manager = ConnectionManager()


class DeliveryService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.delivery_repo = DeliveryRepository(db)
        self.location_repo = RiderLocationRepository(db)
        self.rider_repo = RiderProfileRepository(db)
        self.order_repo = OrderRepository(db)
        self.user_repo = UserRepository(db)
        self.notif_service = NotificationService(db)

    async def create_delivery_assignment(self, order_id: int) -> Delivery:
        """Create a delivery entity for a newly placed order."""
        order = await self.order_repo.get(order_id)
        if not order:
            raise NotFoundException("Order")

        restaurant = order.restaurant
        if not restaurant:
            raise NotFoundException("Restaurant details")

        # Get coordinates
        pickup_lat = restaurant.latitude or 8.484
        pickup_lng = restaurant.longitude or -13.234
        dropoff_lat = 8.484
        dropoff_lng = -13.234

        if order.delivery_address_snapshot:
            dropoff_lat = order.delivery_address_snapshot.get("latitude") or 8.484
            dropoff_lng = order.delivery_address_snapshot.get("longitude") or -13.234

        # Calculate distance
        from app.utils.geo import haversine_distance, calculate_eta_minutes
        distance = haversine_distance(pickup_lat, pickup_lng, dropoff_lat, dropoff_lng)
        duration = calculate_eta_minutes(distance)

        delivery = Delivery(
            order_id=order.id,
            status=DeliveryStatus.PENDING,
            pickup_latitude=pickup_lat,
            pickup_longitude=pickup_lng,
            dropoff_latitude=dropoff_lat,
            dropoff_longitude=dropoff_lng,
            distance_km=round(distance, 2),
            estimated_duration_min=duration,
        )
        await self.delivery_repo.create(delivery)
        await self.db.flush()

        # Try automatic rider assignment asynchronously
        await self._auto_assign_rider(delivery.id)

        return delivery

    async def _auto_assign_rider(self, delivery_id: int) -> Optional[int]:
        """Auto-assign the closest available rider within 10 km."""
        delivery = await self.delivery_repo.get(delivery_id)
        if not delivery:
            return None

        available_riders = await self.rider_repo.get_available_riders()
        if not available_riders:
            logger.info("no_available_riders_found", delivery_id=delivery_id)
            return None

        # Fetch locations of available riders
        closest_rider = None
        min_dist = float("inf")

        for rider in available_riders:
            loc = await self.location_repo.get_by_rider(rider.user_id)
            if loc:
                from app.utils.geo import haversine_distance
                dist = haversine_distance(
                    delivery.pickup_latitude, delivery.pickup_longitude, loc.latitude, loc.longitude
                )
                if dist < min_dist and dist <= 10.0:  # Within 10 km
                    min_dist = dist
                    closest_rider = rider

        if closest_rider:
            await self._assign_to_delivery(delivery_id, closest_rider.user_id)
            return closest_rider.user_id

        return None

    async def _assign_to_delivery(self, delivery_id: int, rider_user_id: int) -> Delivery:
        """Manually assign order delivery to a rider."""
        delivery = await self.delivery_repo.get(delivery_id)
        if not delivery:
            raise NotFoundException("Delivery")

        rider_profile = await self.rider_repo.get_by_user(rider_user_id)
        if not rider_profile or not rider_profile.is_verified:
            raise BusinessRuleException("Selected rider is not verified")

        delivery.rider_id = rider_user_id
        delivery.status = DeliveryStatus.ASSIGNED
        delivery.assigned_at = datetime.now(timezone.utc)
        self.db.add(delivery)

        # Notify rider
        rider_user = await self.user_repo.get(rider_user_id)
        if rider_user:
            await self.notif_service.dispatch_notification(
                user_id=rider_user.id,
                title="New Delivery Assignment",
                body=f"You have been assigned a delivery of {delivery.distance_km} km. Please accept it.",
                notif_type=NotificationType.RIDER_ASSIGNED,
                recipient_email=rider_user.email,
                recipient_phone=rider_user.phone,
                onesignal_player_id=rider_user.onesignal_player_id,
            )

        await self.db.flush()
        return delivery

    async def accept_delivery(self, order_id: int, current_user: "User") -> Delivery:
        delivery = await self.delivery_repo.get_by_order(order_id)
        if not delivery:
            raise NotFoundException("Delivery")
        rider_user_id = current_user.id
        if delivery.rider_id != rider_user_id:
            raise ForbiddenException("You are not assigned to this delivery")
        if delivery.status != DeliveryStatus.ASSIGNED:
            raise BusinessRuleException("Delivery has already been accepted or processed")

        delivery.status = DeliveryStatus.ACCEPTED
        delivery.accepted_at = datetime.now(timezone.utc)
        self.db.add(delivery)

        order = await self.order_repo.get(delivery.order_id)
        if order:
            order.rider_id = rider_user_id
            order.status = OrderStatus.ACCEPTED
            self.db.add(order)

        await self.db.flush()
        return delivery

    async def reject_delivery(self, order_id: int, current_user: "User") -> None:
        delivery = await self.delivery_repo.get_by_order(order_id)
        if not delivery:
            raise NotFoundException("Delivery")
        if delivery.rider_id != current_user.id:
            raise ForbiddenException("You are not assigned to this delivery")
        delivery.status = DeliveryStatus.PENDING
        delivery.rider_id = None
        delivery.assigned_at = None
        self.db.add(delivery)
        await self.db.flush()

    async def mark_picked_up(self, order_id: int, current_user: "User") -> Delivery:
        delivery = await self.delivery_repo.get_by_order(order_id)
        if not delivery:
            raise NotFoundException("Delivery")
        if delivery.rider_id != current_user.id:
            raise ForbiddenException("You are not assigned to this delivery")
        if delivery.status not in (DeliveryStatus.ACCEPTED, DeliveryStatus.PICKING_UP):
            raise BusinessRuleException("Order has not been accepted yet")
        delivery.status = DeliveryStatus.PICKED_UP
        delivery.picked_up_at = datetime.now(timezone.utc)
        self.db.add(delivery)
        order = await self.order_repo.get(delivery.order_id)
        if order:
            order.status = OrderStatus.ON_THE_WAY
            self.db.add(order)
        await self.db.flush()
        return delivery

    async def fail_delivery(self, order_id: int, reason: str, current_user: "User") -> Delivery:
        delivery = await self.delivery_repo.get_by_order(order_id)
        if not delivery:
            raise NotFoundException("Delivery")
        if delivery.rider_id != current_user.id:
            raise ForbiddenException("You are not assigned to this delivery")
        delivery.status = DeliveryStatus.FAILED
        delivery.failure_reason = reason
        delivery.failed_at = datetime.now(timezone.utc)
        self.db.add(delivery)
        order = await self.order_repo.get(delivery.order_id)
        if order:
            order.status = OrderStatus.FAILED
            self.db.add(order)
        await self.db.flush()
        return delivery

    async def update_rider_live_location(
        self, rider_id: int, lat: float, lng: float, bearing: Optional[float] = None
    ) -> None:
        """Update live coordinate database entry and broadcast to observers via websocket."""
        loc = await self.location_repo.get_by_rider(rider_id)
        if not loc:
            loc = RiderLocation(
                rider_id=rider_id,
                latitude=lat,
                longitude=lng,
                bearing=bearing,
            )
            await self.location_repo.create(loc)
        else:
            loc.latitude = lat
            loc.longitude = lng
            loc.bearing = bearing
            loc.updated_at = datetime.utcnow()
            self.db.add(loc)

        await self.db.flush()

        # Get active delivery for this rider to broadcast
        active_deliveries = await self.delivery_repo.get_active_deliveries_for_rider(rider_id)
        for d in active_deliveries:
            await gps_manager.broadcast_location(
                d.id,
                {
                    "delivery_id": d.id,
                    "rider_id": rider_id,
                    "latitude": lat,
                    "longitude": lng,
                    "bearing": bearing,
                    "timestamp": datetime.utcnow().isoformat(),
                },
            )

    async def complete_delivery(self, order_id: int, current_user: "User") -> Delivery:
        delivery = await self.delivery_repo.get_by_order(order_id)
        if not delivery:
            raise NotFoundException("Delivery")
        rider_user_id = current_user.id
        if delivery.rider_id != rider_user_id:
            raise ForbiddenException("Unauthorized")

        delivery.status = DeliveryStatus.DELIVERED
        delivery.delivered_at = datetime.now(timezone.utc)
        self.db.add(delivery)

        # Update Order to Completed
        order = await self.order_repo.get(delivery.order_id)
        if order:
            order.status = OrderStatus.DELIVERED
            self.db.add(order)

            # Update Rider earnings profile
            rider_profile = await self.rider_repo.get_by_user(rider_user_id)
            if rider_profile:
                # Add delivery fee amount directly to balance
                net_earning = order.delivery_fee
                rider_profile.total_earnings += net_earning
                rider_profile.current_balance += net_earning
                rider_profile.total_deliveries += 1
                self.db.add(rider_profile)

                # Log Rider earning transaction record
                from app.models.rider import RiderEarning
                from app.utils.constants import EarningsStatus
                earning = RiderEarning(
                    rider_id=rider_profile.id,
                    order_id=order.id,
                    amount=order.delivery_fee,
                    net_earning=net_earning,
                    status=EarningsStatus.AVAILABLE,
                )
                self.db.add(earning)

        await self.db.flush()
        return delivery

    async def assign_rider(self, order_id: int, rider_id: int, current_user: "User") -> "Order":
        from app.utils.constants import UserRole
        from app.exceptions.custom import ForbiddenException
        if current_user.role not in (UserRole.ADMIN, UserRole.SUPER_ADMIN, UserRole.RESTAURANT_OWNER):
            raise ForbiddenException("Not allowed to assign riders")
        delivery = await self.delivery_repo.get_by_order(order_id)
        if not delivery:
            delivery = await self.create_delivery_assignment(order_id)
        await self._assign_to_delivery(delivery.id, rider_id)
        order = await self.order_repo.get(order_id)
        if not order:
            raise NotFoundException("Order")
        return order

    async def auto_assign_rider(self, order_id: int, current_user: "User") -> "Order":
        from app.utils.constants import UserRole
        from app.exceptions.custom import ForbiddenException
        if current_user.role not in (UserRole.ADMIN, UserRole.SUPER_ADMIN):
            raise ForbiddenException("Admin access required")
        delivery = await self.delivery_repo.get_by_order(order_id)
        if not delivery:
            delivery = await self.create_delivery_assignment(order_id)
        await self._auto_assign_rider(delivery.id)
        order = await self.order_repo.get(order_id)
        if not order:
            raise NotFoundException("Order")
        return order

    async def update_rider_location(self, rider_id: int, body: "LocationUpdateRequest") -> "RiderLocationResponse":
        from app.schemas.location import RiderLocationResponse
        await self.update_rider_live_location(rider_id, body.latitude, body.longitude, body.bearing)
        loc = await self.location_repo.get_by_rider(rider_id)
        return RiderLocationResponse.model_validate(loc)

    async def get_rider_location(self, rider_id: int) -> "RiderLocationResponse":
        from app.schemas.location import RiderLocationResponse
        loc = await self.location_repo.get_by_rider(rider_id)
        if not loc:
            raise NotFoundException("Rider location not available")
        return RiderLocationResponse.model_validate(loc)
