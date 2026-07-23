"""
CLMStore — WebSocket Router
Real-time live rider tracking and order status push updates.
"""
from __future__ import annotations

import json
from typing import Dict, Set

import structlog
from fastapi import APIRouter, Path, Query, WebSocket, WebSocketDisconnect, status
from starlette.websockets import WebSocketState

logger = structlog.get_logger()

router = APIRouter()


# ── Connection Manager ────────────────────────────────────────────────────────
class ConnectionManager:
    """Manages active WebSocket connections grouped by room (order_id or rider_id)."""

    def __init__(self) -> None:
        self.active_connections: Dict[str, Set[WebSocket]] = {}

    async def connect(self, room: str, websocket: WebSocket) -> None:
        await websocket.accept()
        if room not in self.active_connections:
            self.active_connections[room] = set()
        self.active_connections[room].add(websocket)
        logger.info("ws_connect", room=room, total=len(self.active_connections[room]))

    def disconnect(self, room: str, websocket: WebSocket) -> None:
        if room in self.active_connections:
            self.active_connections[room].discard(websocket)
            if not self.active_connections[room]:
                del self.active_connections[room]
        logger.info("ws_disconnect", room=room)

    async def broadcast_to_room(self, room: str, message: dict) -> None:
        """Send a JSON message to all subscribers of a room."""
        if room not in self.active_connections:
            return
        dead: Set[WebSocket] = set()
        for ws in self.active_connections[room].copy():
            try:
                if ws.client_state == WebSocketState.CONNECTED:
                    await ws.send_json(message)
            except Exception:
                dead.add(ws)
        for ws in dead:
            self.disconnect(room, ws)

    async def send_to_websocket(self, websocket: WebSocket, message: dict) -> None:
        try:
            await websocket.send_json(message)
        except Exception:
            pass


manager = ConnectionManager()


# ── WS /api/v1/ws/orders/{order_id}/track ────────────────────────────────────
@router.websocket("/orders/{order_id}/track")
async def order_tracking_ws(
    websocket: WebSocket,
    order_id: int = Path(..., ge=1),
    token: str = Query(..., description="JWT access token for authentication"),
) -> None:
    """
    **WebSocket endpoint for real-time order tracking.**

    Clients subscribe to an order's room and receive live updates:
    - Rider GPS location updates (every ~5 seconds)
    - Order status changes (accepted, preparing, ready, picked_up, on_the_way, delivered)

    **Connection URL:** `ws://api.clmstore.sl/api/v1/ws/orders/42/track?token=<JWT>`

    **Received Messages:**
    ```json
    {
        "type": "location_update",
        "order_id": 42,
        "rider_id": 7,
        "latitude": 8.4701,
        "longitude": -13.2345,
        "eta_minutes": 8,
        "timestamp": "2024-06-15T14:30:00Z"
    }
    ```

    ```json
    {
        "type": "status_change",
        "order_id": 42,
        "status": "on_the_way",
        "message": "Your order is on the way!",
        "timestamp": "2024-06-15T14:28:00Z"
    }
    ```
    """
    # Validate JWT token
    try:
        from app.auth.jwt import decode_token
        decode_token(token, expected_type="access")
    except Exception:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    room = f"order:{order_id}"
    await manager.connect(room, websocket)

    try:
        await manager.send_to_websocket(websocket, {
            "type": "connected",
            "order_id": order_id,
            "message": f"Subscribed to order {order_id} tracking.",
        })

        while True:
            # Keep connection alive; actual updates are pushed from delivery service
            data = await websocket.receive_text()
            if data == "ping":
                await manager.send_to_websocket(websocket, {"type": "pong"})

    except WebSocketDisconnect:
        manager.disconnect(room, websocket)
    except Exception as e:
        logger.error("ws_error", room=room, error=str(e))
        manager.disconnect(room, websocket)


# ── WS /api/v1/ws/riders/{rider_id}/location ─────────────────────────────────
@router.websocket("/riders/{rider_id}/location")
async def rider_location_ws(
    websocket: WebSocket,
    rider_id: int = Path(..., ge=1),
    token: str = Query(..., description="JWT access token"),
) -> None:
    """
    **WebSocket for riders to broadcast live GPS location.**

    The rider's app continuously sends location payloads. The server fans out
    updates to all subscribers of the rider's active order tracking room.

    **Connection URL:** `ws://api.clmstore.sl/api/v1/ws/riders/7/location?token=<JWT>`

    **Sent by rider (every ~3-5 seconds):**
    ```json
    {
        "latitude": 8.4701,
        "longitude": -13.2345,
        "bearing": 180.0
    }
    ```

    **Broadcast to order subscribers:**
    ```json
    {
        "type": "location_update",
        "rider_id": 7,
        "latitude": 8.4701,
        "longitude": -13.2345,
        "bearing": 180.0,
        "timestamp": "2024-06-15T14:30:00Z"
    }
    ```
    """
    try:
        from app.auth.jwt import decode_token
        payload = decode_token(token, expected_type="access")
        token_user_id = int(payload.get("sub", 0))
        if token_user_id != rider_id:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return
    except Exception:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    await websocket.accept()
    logger.info("rider_ws_connected", rider_id=rider_id)

    from datetime import datetime, timezone
    from app.database import AsyncSessionLocal
    from app.repositories.delivery_repository import DeliveryRepository

    active_order_id: int | None = None
    location_count = 0

    async def _refresh_active_order() -> int | None:
        async with AsyncSessionLocal() as db:
            deliveries = await DeliveryRepository(db).get_active_deliveries_for_rider(rider_id)
            return deliveries[0].order_id if deliveries else None

    # Resolve the active order upfront so the first location update goes to the right room
    active_order_id = await _refresh_active_order()

    try:
        while True:
            text = await websocket.receive_text()
            try:
                data = json.loads(text)
                lat = data.get("latitude")
                lon = data.get("longitude")
                bearing = data.get("bearing")

                if lat is None or lon is None:
                    continue

                location_count += 1
                # Re-check every 20 updates (delivery assignment can change)
                if location_count % 20 == 0:
                    active_order_id = await _refresh_active_order()

                payload_out = {
                    "type": "location_update",
                    "rider_id": rider_id,
                    "latitude": lat,
                    "longitude": lon,
                    "bearing": bearing,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }

                if active_order_id:
                    await manager.broadcast_to_room(f"order:{active_order_id}", payload_out)

            except json.JSONDecodeError:
                pass

    except WebSocketDisconnect:
        logger.info("rider_ws_disconnected", rider_id=rider_id)
    except Exception as e:
        logger.error("rider_ws_error", rider_id=rider_id, error=str(e))


# ── WS /api/v1/ws/notifications ──────────────────────────────────────────────
@router.websocket("/notifications")
async def user_notifications_ws(
    websocket: WebSocket,
    token: str = Query(..., description="JWT access token"),
) -> None:
    """
    **WebSocket for real-time in-app notifications.**

    Customers, restaurant owners, and riders receive instant notifications
    without polling the REST API.

    **Connection URL:** `ws://api.clmstore.sl/api/v1/ws/notifications?token=<JWT>`

    **Received:**
    ```json
    {
        "type": "notification",
        "title": "Order Accepted",
        "body": "Your order CLM-20240615-123456 has been accepted.",
        "notification_type": "order_accepted",
        "data": {"order_id": 42},
        "timestamp": "2024-06-15T14:28:00Z"
    }
    ```
    """
    try:
        from app.auth.jwt import decode_token
        payload = decode_token(token, expected_type="access")
        user_id = int(payload.get("sub", 0))
    except Exception:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    room = f"user:{user_id}:notifications"
    await manager.connect(room, websocket)

    try:
        await manager.send_to_websocket(websocket, {
            "type": "connected",
            "user_id": user_id,
            "message": "Connected to notification stream.",
        })

        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await manager.send_to_websocket(websocket, {"type": "pong"})

    except WebSocketDisconnect:
        manager.disconnect(room, websocket)


# ── Utility: Push notification to user via WebSocket ─────────────────────────
async def push_notification_to_user(user_id: int, message: dict) -> None:
    """Called by NotificationService to push real-time notification via WebSocket."""
    room = f"user:{user_id}:notifications"
    await manager.broadcast_to_room(room, message)


# ── Utility: Broadcast order status update ────────────────────────────────────
async def broadcast_order_status(order_id: int, status_data: dict) -> None:
    """Called by OrderService to push status changes to order subscribers."""
    room = f"order:{order_id}"
    await manager.broadcast_to_room(room, status_data)
