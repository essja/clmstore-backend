"""
CLMStore — Global Food Search Router
GET /api/v1/search/food?q=&page=&limit=
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.menu import MenuItem
from app.models.restaurant import Restaurant

router = APIRouter()


@router.get("/food", summary="Search menu items by name or description across all restaurants")
async def search_food(
    q: str = Query(..., min_length=2, max_length=100, description="Search term"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    term = f"%{q.lower()}%"

    base_query = (
        select(MenuItem)
        .join(Restaurant, MenuItem.restaurant_id == Restaurant.id)
        .where(
            MenuItem.is_available == True,  # noqa: E712
            Restaurant.is_open == True,      # noqa: E712
            or_(
                func.lower(MenuItem.name).like(term),
                func.lower(MenuItem.description).like(term),
            ),
        )
        .options(selectinload(MenuItem.option_groups))
        .order_by(MenuItem.is_popular.desc(), MenuItem.name)
    )

    total_result = await db.execute(select(func.count()).select_from(base_query.subquery()))
    total: int = total_result.scalar_one()

    offset = (page - 1) * limit
    items_result = await db.execute(base_query.offset(offset).limit(limit))
    items = items_result.scalars().all()

    # Batch-load restaurant names
    restaurant_ids = list({item.restaurant_id for item in items})
    rest_result = await db.execute(
        select(Restaurant.id, Restaurant.name, Restaurant.slug).where(Restaurant.id.in_(restaurant_ids))
    )
    rest_map = {row.id: (row.name, row.slug) for row in rest_result}

    def serialize(item: MenuItem) -> dict[str, Any]:
        rest_name, rest_slug = rest_map.get(item.restaurant_id, (None, None))
        discount = item.discount_percentage or 0.0
        effective_price = round(item.price * (1 - discount / 100), 2) if discount else item.price
        return {
            "id": item.id,
            "name": item.name,
            "description": item.description,
            "price": item.price,
            "effective_price": effective_price,
            "discount_percentage": item.discount_percentage,
            "image": item.image,
            "is_available": item.is_available,
            "is_popular": item.is_popular,
            "category_id": item.category_id,
            "restaurant_id": item.restaurant_id,
            "restaurant_name": rest_name,
            "restaurant_slug": rest_slug,
            "option_groups": [],
        }

    return {
        "data": [serialize(i) for i in items],
        "total": total,
        "page": page,
        "limit": limit,
    }
