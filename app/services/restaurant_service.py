"""
CLMStore — Restaurant Service
"""
from __future__ import annotations

from typing import List, Optional
from slugify import slugify

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions.custom import NotFoundException, ConflictException, ForbiddenException
from app.models.restaurant import Restaurant, RestaurantDocument, OpeningHours, RestaurantEmployee
from app.models.order import Order, OrderItem
from app.repositories.restaurant_repository import (
    RestaurantRepository,
    RestaurantDocumentRepository,
    OpeningHoursRepository,
    RestaurantEmployeeRepository,
)
from app.schemas.restaurant import (
    RestaurantCreate,
    RestaurantUpdate,
    OpeningHoursCreate,
    RestaurantEmployeeCreate,
    RestaurantResponse,
)
from app.utils.constants import RestaurantStatus, StoreType, UserRole, OrderStatus


class RestaurantService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.restaurant_repo = RestaurantRepository(db)
        self.doc_repo = RestaurantDocumentRepository(db)
        self.hours_repo = OpeningHoursRepository(db)
        self.employee_repo = RestaurantEmployeeRepository(db)

    # ── Discovery ─────────────────────────────────────────────────────────────

    async def search_restaurants(
        self,
        query: Optional[str] = None,
        store_type: Optional[StoreType] = None,
        cuisine: Optional[str] = None,
        city: Optional[str] = None,
        is_open: Optional[bool] = None,
        featured: Optional[bool] = None,
        lat: Optional[float] = None,
        lon: Optional[float] = None,
        radius_km: float = 10.0,
        sort_by: str = "rating",
        skip: int = 0,
        limit: int = 20,
    ) -> tuple[List[RestaurantResponse], int]:
        restaurants, distances = await self.restaurant_repo.search_and_filter(
            q=query,
            store_type=store_type,
            cuisine_type=cuisine,
            is_open=is_open,
            featured=featured,
            latitude=lat,
            longitude=lon,
            radius_km=radius_km if (lat is not None and lon is not None) else None,
            sort_by=sort_by,
            skip=skip,
            limit=limit,
        )
        total = await self.restaurant_repo.count_search_and_filter(
            q=query,
            store_type=store_type,
            cuisine_type=cuisine,
            is_open=is_open,
            featured=featured,
        )

        responses = []
        for restaurant, dist in zip(restaurants, distances):
            data = RestaurantResponse.model_validate(restaurant)
            if dist is not None:
                data.distance_km = round(dist, 2)
            responses.append(data)

        return responses, total

    async def get_by_id(self, restaurant_id: int) -> Restaurant:
        rest = await self.restaurant_repo.get(restaurant_id)
        if not rest:
            raise NotFoundException("Restaurant", restaurant_id)
        return rest

    # ── CRUD ──────────────────────────────────────────────────────────────────

    async def create_restaurant(self, schema: RestaurantCreate, owner_id: int) -> Restaurant:
        """Register a new restaurant/grocery/pharmacy (status starts as PENDING)."""
        slug = slugify(schema.name)
        existing = await self.restaurant_repo.get_by_slug(slug)
        if existing:
            import random
            slug = f"{slug}-{random.randint(100, 999)}"

        rest = Restaurant(
            owner_id=owner_id,
            name=schema.name,
            slug=slug,
            description=schema.description,
            store_type=schema.store_type,
            cuisine_type=schema.cuisine_type,
            address=schema.address,
            city=schema.city,
            latitude=schema.latitude,
            longitude=schema.longitude,
            phone=schema.phone,
            email=schema.email,
            min_order=schema.min_order,
            delivery_fee=schema.delivery_fee,
            delivery_radius_km=schema.delivery_radius_km,
            min_delivery_time_min=schema.min_delivery_time_min,
            avg_delivery_time_min=schema.avg_delivery_time_min,
            status=RestaurantStatus.PENDING,
            is_open=False,
        )
        return await self.restaurant_repo.create(rest)

    async def update_restaurant(
        self, restaurant_id: int, schema: RestaurantUpdate, current_user: "User"
    ) -> Restaurant:
        rest = await self.get_by_id(restaurant_id)
        is_admin = current_user.role in (UserRole.ADMIN, UserRole.SUPER_ADMIN)
        if not is_admin and rest.owner_id != current_user.id:
            raise ForbiddenException("Only the restaurant owner can update this restaurant")
        return await self.restaurant_repo.update(rest, schema)

    async def delete_restaurant(self, restaurant_id: int, current_user: "User") -> None:
        rest = await self.get_by_id(restaurant_id)
        is_admin = current_user.role in (UserRole.ADMIN, UserRole.SUPER_ADMIN)
        if not is_admin and rest.owner_id != current_user.id:
            raise ForbiddenException("Only the restaurant owner can remove this restaurant")
        rest.status = RestaurantStatus.SUSPENDED
        rest.is_open = False
        self.db.add(rest)

    async def toggle_open_status(self, restaurant_id: int, current_user: "User") -> bool:
        rest = await self.get_by_id(restaurant_id)
        is_admin = current_user.role in (UserRole.ADMIN, UserRole.SUPER_ADMIN)
        if not is_admin and rest.owner_id != current_user.id:
            raise ForbiddenException("Only the restaurant owner can toggle open status")
        rest.is_open = not rest.is_open
        self.db.add(rest)
        return rest.is_open

    # ── Documents ─────────────────────────────────────────────────────────────

    async def upload_document(
        self, restaurant_id: int, doc_type: str, file: "UploadFile", current_user: "User"
    ) -> RestaurantDocument:
        from app.services.file_service import FileService
        rest = await self.get_by_id(restaurant_id)
        is_admin = current_user.role in (UserRole.ADMIN, UserRole.SUPER_ADMIN)
        if not is_admin and rest.owner_id != current_user.id:
            raise ForbiddenException("Only the restaurant owner can upload documents")
        file_service = FileService()
        url = await file_service.upload_document(file, folder="restaurant_documents")
        doc = RestaurantDocument(
            restaurant_id=restaurant_id,
            doc_type=doc_type,
            file_url=url,
            is_verified=False,
        )
        return await self.doc_repo.create(doc)

    async def get_documents(self, restaurant_id: int, current_user: "User") -> List[RestaurantDocument]:
        rest = await self.get_by_id(restaurant_id)
        is_admin = current_user.role in (UserRole.ADMIN, UserRole.SUPER_ADMIN)
        if not is_admin and rest.owner_id != current_user.id:
            raise ForbiddenException("Only the restaurant owner can view documents")
        return await self.doc_repo.get_by_restaurant(restaurant_id)

    # ── Opening Hours ─────────────────────────────────────────────────────────

    async def get_opening_hours(self, restaurant_id: int) -> List[OpeningHours]:
        await self.get_by_id(restaurant_id)
        return await self.hours_repo.get_by_restaurant(restaurant_id)

    async def set_opening_hours(
        self, restaurant_id: int, hours_list: List[OpeningHoursCreate], current_user: "User"
    ) -> List[OpeningHours]:
        rest = await self.get_by_id(restaurant_id)
        is_admin = current_user.role in (UserRole.ADMIN, UserRole.SUPER_ADMIN)
        if not is_admin and rest.owner_id != current_user.id:
            raise ForbiddenException("Only the restaurant owner can set opening hours")
        existing = await self.hours_repo.get_by_restaurant(restaurant_id)
        for h in existing:
            await self.hours_repo.delete(h.id)
        saved = []
        for h in hours_list:
            hours_obj = OpeningHours(
                restaurant_id=restaurant_id,
                day_of_week=h.day_of_week,
                open_time=h.open_time,
                close_time=h.close_time,
                is_closed=h.is_closed,
            )
            await self.hours_repo.create(hours_obj)
            saved.append(hours_obj)
        return saved

    # ── Analytics ─────────────────────────────────────────────────────────────

    async def get_analytics(self, restaurant_id: int, period: str, current_user: "User") -> dict:
        rest = await self.get_by_id(restaurant_id)
        is_admin = current_user.role in (UserRole.ADMIN, UserRole.SUPER_ADMIN)
        if not is_admin and rest.owner_id != current_user.id:
            raise ForbiddenException("Only the restaurant owner can view analytics")

        from datetime import datetime, timezone, timedelta
        now = datetime.now(timezone.utc)
        if period == "today":
            since = now.replace(hour=0, minute=0, second=0, microsecond=0)
        elif period == "week":
            since = now - timedelta(days=7)
        elif period == "year":
            since = now - timedelta(days=365)
        else:
            since = now - timedelta(days=30)

        res = await self.db.execute(
            select(
                func.count(Order.id),
                func.sum(Order.subtotal),
                func.sum(Order.subtotal * rest.commission_rate),
                func.avg(Order.subtotal),
            ).filter(
                Order.restaurant_id == restaurant_id,
                Order.created_at >= since,
                Order.status == OrderStatus.DELIVERED,
            )
        )
        row = res.first()
        total_orders = int(row[0] or 0)
        total_revenue = float(row[1] or 0)
        commission_paid = float(row[2] or 0)
        avg_order_value = float(row[3] or 0)

        top_items_res = await self.db.execute(
            select(OrderItem.name, func.sum(OrderItem.quantity).label("sold"))
            .join(Order, Order.id == OrderItem.order_id)
            .filter(
                Order.restaurant_id == restaurant_id,
                Order.created_at >= since,
            )
            .group_by(OrderItem.name)
            .order_by(func.sum(OrderItem.quantity).desc())
            .limit(5)
        )
        top_items = [{"name": r[0], "quantity_sold": int(r[1] or 0)} for r in top_items_res.all()]

        daily_res = await self.db.execute(
            select(
                func.date_trunc("day", Order.created_at).label("day"),
                func.sum(Order.subtotal).label("revenue"),
            )
            .filter(
                Order.restaurant_id == restaurant_id,
                Order.created_at >= since,
                Order.status == OrderStatus.DELIVERED,
            )
            .group_by("day")
            .order_by("day")
        )
        daily = [{"date": str(r[0].date()), "revenue": float(r[1] or 0)} for r in daily_res.all()]

        return {
            "period": period,
            "restaurant_id": restaurant_id,
            "total_orders": total_orders,
            "total_revenue": total_revenue,
            "commission_paid": round(commission_paid, 2),
            "net_earnings": round(total_revenue - commission_paid, 2),
            "average_order_value": round(avg_order_value, 2),
            "top_selling_items": top_items,
            "daily_revenue": daily,
            "currency": "SLL",
        }

    # ── Employees ─────────────────────────────────────────────────────────────

    async def list_employees(self, restaurant_id: int, current_user: "User") -> List[RestaurantEmployee]:
        rest = await self.get_by_id(restaurant_id)
        is_admin = current_user.role in (UserRole.ADMIN, UserRole.SUPER_ADMIN)
        if not is_admin and rest.owner_id != current_user.id:
            raise ForbiddenException("Only the restaurant owner can list employees")
        return await self.employee_repo.get_by_restaurant(restaurant_id)

    async def add_employee(
        self, restaurant_id: int, schema: RestaurantEmployeeCreate, current_user: "User"
    ) -> RestaurantEmployee:
        rest = await self.get_by_id(restaurant_id)
        is_admin = current_user.role in (UserRole.ADMIN, UserRole.SUPER_ADMIN)
        if not is_admin and rest.owner_id != current_user.id:
            raise ForbiddenException("Only the restaurant owner can add employees")
        existing = await self.employee_repo.get_employee(restaurant_id, schema.user_id)
        if existing:
            raise ConflictException("Employee already added to this restaurant")
        emp = RestaurantEmployee(
            restaurant_id=restaurant_id,
            user_id=schema.user_id,
            role=schema.role,
            is_active=True,
        )
        return await self.employee_repo.create(emp)

    async def remove_employee(
        self, restaurant_id: int, user_id: int, current_user: "User"
    ) -> None:
        rest = await self.get_by_id(restaurant_id)
        is_admin = current_user.role in (UserRole.ADMIN, UserRole.SUPER_ADMIN)
        if not is_admin and rest.owner_id != current_user.id:
            raise ForbiddenException("Only the restaurant owner can remove employees")
        emp = await self.employee_repo.get_employee(restaurant_id, user_id)
        if not emp:
            raise NotFoundException("Employee")
        await self.employee_repo.delete(emp.id)

    # ── Admin actions ─────────────────────────────────────────────────────────

    async def approve_restaurant(self, restaurant_id: int, admin_id: int) -> Restaurant:
        rest = await self.get_by_id(restaurant_id)
        rest.status = RestaurantStatus.VERIFIED
        self.db.add(rest)
        return rest

    async def reject_restaurant(self, restaurant_id: int, reason: str, admin_id: int) -> Restaurant:
        rest = await self.get_by_id(restaurant_id)
        rest.status = RestaurantStatus.REJECTED
        self.db.add(rest)
        return rest

    async def suspend_restaurant(self, restaurant_id: int, reason: str, admin_id: int) -> Restaurant:
        rest = await self.get_by_id(restaurant_id)
        rest.status = RestaurantStatus.SUSPENDED
        rest.is_open = False
        self.db.add(rest)
        return rest
