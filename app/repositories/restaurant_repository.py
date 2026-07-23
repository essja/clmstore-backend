"""
CLMStore — Restaurant Repository
"""
from __future__ import annotations

from typing import List, Optional

from sqlalchemy import select, and_, or_, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.restaurant import Restaurant, RestaurantDocument, OpeningHours, RestaurantEmployee
from app.repositories.base import BaseRepository
from app.utils.constants import RestaurantStatus, StoreType


class RestaurantRepository(BaseRepository[Restaurant]):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(Restaurant, db)

    async def get_by_slug(self, slug: str) -> Optional[Restaurant]:
        result = await self.db.execute(select(Restaurant).filter(Restaurant.slug == slug))
        return result.scalars().first()

    async def get_by_owner(self, owner_id: int) -> List[Restaurant]:
        result = await self.db.execute(select(Restaurant).filter(Restaurant.owner_id == owner_id))
        return list(result.scalars().all())

    async def search_and_filter(
        self,
        q: Optional[str] = None,
        store_type: Optional[StoreType] = None,
        cuisine_type: Optional[str] = None,
        is_open: Optional[bool] = None,
        featured: Optional[bool] = None,
        status: RestaurantStatus = RestaurantStatus.VERIFIED,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
        radius_km: Optional[float] = None,
        sort_by: str = "rating",
        skip: int = 0,
        limit: int = 20,
    ) -> tuple[List[Restaurant], List[Optional[float]]]:
        """
        Returns (restaurants, distances) where distances[i] is the km distance
        for restaurants[i] (None if no user location provided).
        """
        stmt = select(Restaurant).filter(Restaurant.status == status)

        if store_type:
            stmt = stmt.filter(Restaurant.store_type == store_type)

        if q:
            stmt = stmt.filter(
                or_(
                    Restaurant.name.ilike(f"%{q}%"),
                    Restaurant.description.ilike(f"%{q}%"),
                    Restaurant.cuisine_type.ilike(f"%{q}%"),
                )
            )

        if cuisine_type:
            stmt = stmt.filter(Restaurant.cuisine_type.ilike(f"%{cuisine_type}%"))

        if is_open is not None:
            stmt = stmt.filter(Restaurant.is_open == is_open)

        if featured is not None:
            stmt = stmt.filter(Restaurant.is_featured == featured)

        result = await self.db.execute(stmt)
        restaurants = list(result.scalars().all())

        distances: List[Optional[float]] = [None] * len(restaurants)

        if latitude is not None and longitude is not None:
            from app.utils.geo import haversine_distance
            pairs = []
            for r in restaurants:
                if r.latitude is not None and r.longitude is not None:
                    dist = haversine_distance(latitude, longitude, r.latitude, r.longitude)
                    if radius_km is None or dist <= radius_km:
                        pairs.append((r, dist))
                else:
                    pairs.append((r, None))

            if sort_by == "distance":
                pairs.sort(key=lambda x: x[1] if x[1] is not None else float("inf"))
            elif sort_by == "rating":
                pairs.sort(key=lambda x: x[0].avg_rating, reverse=True)
            elif sort_by == "delivery_fee":
                pairs.sort(key=lambda x: x[0].delivery_fee)
            elif sort_by == "name":
                pairs.sort(key=lambda x: x[0].name)

            pairs = pairs[skip : skip + limit]
            restaurants = [p[0] for p in pairs]
            distances = [p[1] for p in pairs]
            return restaurants, distances

        # No location — sort in memory
        if sort_by == "rating":
            restaurants.sort(key=lambda r: r.avg_rating, reverse=True)
        elif sort_by == "delivery_fee":
            restaurants.sort(key=lambda r: r.delivery_fee)
        elif sort_by == "name":
            restaurants.sort(key=lambda r: r.name)

        return restaurants[skip : skip + limit], distances[skip : skip + limit]

    async def count_search_and_filter(
        self,
        q: Optional[str] = None,
        store_type: Optional[StoreType] = None,
        cuisine_type: Optional[str] = None,
        is_open: Optional[bool] = None,
        featured: Optional[bool] = None,
        status: RestaurantStatus = RestaurantStatus.VERIFIED,
    ) -> int:
        stmt = select(func.count(Restaurant.id)).filter(Restaurant.status == status)
        if store_type:
            stmt = stmt.filter(Restaurant.store_type == store_type)
        if q:
            stmt = stmt.filter(
                or_(
                    Restaurant.name.ilike(f"%{q}%"),
                    Restaurant.description.ilike(f"%{q}%"),
                    Restaurant.cuisine_type.ilike(f"%{q}%"),
                )
            )
        if cuisine_type:
            stmt = stmt.filter(Restaurant.cuisine_type.ilike(f"%{cuisine_type}%"))
        if is_open is not None:
            stmt = stmt.filter(Restaurant.is_open == is_open)
        if featured is not None:
            stmt = stmt.filter(Restaurant.is_featured == featured)

        result = await self.db.execute(stmt)
        return result.scalar() or 0


    async def get_all_with_status(
        self,
        status_filter: Optional[str] = None,
        skip: int = 0,
        limit: int = 20,
    ) -> tuple[List[Restaurant], int]:
        stmt = select(Restaurant)
        if status_filter:
            stmt = stmt.filter(Restaurant.status == RestaurantStatus(status_filter))
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total_res = await self.db.execute(count_stmt)
        total = total_res.scalar() or 0
        stmt = stmt.order_by(Restaurant.created_at.desc()).offset(skip).limit(limit)
        result = await self.db.execute(stmt)
        return list(result.scalars().all()), total

    async def set_featured_restaurants(self, restaurant_ids: List[int]) -> None:
        """Clears all featured flags then marks the given IDs as featured."""
        from sqlalchemy import update
        await self.db.execute(update(Restaurant).values(is_featured=False))
        if restaurant_ids:
            await self.db.execute(
                update(Restaurant)
                .where(Restaurant.id.in_(restaurant_ids))
                .values(is_featured=True)
            )


class RestaurantDocumentRepository(BaseRepository[RestaurantDocument]):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(RestaurantDocument, db)

    async def get_by_restaurant(self, restaurant_id: int) -> List[RestaurantDocument]:
        result = await self.db.execute(
            select(RestaurantDocument).filter(RestaurantDocument.restaurant_id == restaurant_id)
        )
        return list(result.scalars().all())


class OpeningHoursRepository(BaseRepository[OpeningHours]):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(OpeningHours, db)

    async def get_by_restaurant(self, restaurant_id: int) -> List[OpeningHours]:
        result = await self.db.execute(
            select(OpeningHours).filter(OpeningHours.restaurant_id == restaurant_id)
        )
        return list(result.scalars().all())


class RestaurantEmployeeRepository(BaseRepository[RestaurantEmployee]):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(RestaurantEmployee, db)

    async def get_by_restaurant(self, restaurant_id: int) -> List[RestaurantEmployee]:
        result = await self.db.execute(
            select(RestaurantEmployee).filter(RestaurantEmployee.restaurant_id == restaurant_id)
        )
        return list(result.scalars().all())

    async def get_employee(self, restaurant_id: int, user_id: int) -> Optional[RestaurantEmployee]:
        result = await self.db.execute(
            select(RestaurantEmployee).filter(
                RestaurantEmployee.restaurant_id == restaurant_id,
                RestaurantEmployee.user_id == user_id,
            )
        )
        return result.scalars().first()
