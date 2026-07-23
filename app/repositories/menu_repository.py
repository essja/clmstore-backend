"""
CLMStore — Menu Repository
"""
from __future__ import annotations

from typing import List, Optional

from sqlalchemy import select, and_, or_, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.menu import FoodCategory, MenuItem, MenuItemVariant, MenuItemAddon, MenuOptionGroup, MenuOption
from app.repositories.base import BaseRepository


class FoodCategoryRepository(BaseRepository[FoodCategory]):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(FoodCategory, db)

    async def get_by_restaurant(self, restaurant_id: int, only_active: bool = True) -> List[FoodCategory]:
        stmt = select(FoodCategory).filter(FoodCategory.restaurant_id == restaurant_id)
        if only_active:
            stmt = stmt.filter(FoodCategory.is_active == True)
        stmt = stmt.order_by(FoodCategory.sort_order.asc())
        result = await self.db.execute(stmt)
        return list(result.scalars().all())


class MenuItemRepository(BaseRepository[MenuItem]):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(MenuItem, db)

    async def get_with_details(self, id: int) -> Optional[MenuItem]:
        result = await self.db.execute(
            select(MenuItem)
            .filter(MenuItem.id == id)
            .options(
                selectinload(MenuItem.variants),
                selectinload(MenuItem.addons),
                selectinload(MenuItem.option_groups).selectinload(MenuOptionGroup.options),
            )
        )
        return result.scalars().first()

    async def get_by_restaurant(
        self,
        restaurant_id: int,
        category_id: Optional[int] = None,
        only_available: bool = True,
    ) -> List[MenuItem]:
        stmt = select(MenuItem).filter(MenuItem.restaurant_id == restaurant_id)
        if category_id is not None:
            stmt = stmt.filter(MenuItem.category_id == category_id)
        if only_available:
            stmt = stmt.filter(MenuItem.is_available == True)
        stmt = stmt.order_by(MenuItem.sort_order.asc())
        stmt = stmt.options(
            selectinload(MenuItem.variants),
            selectinload(MenuItem.addons),
            selectinload(MenuItem.option_groups).selectinload(MenuOptionGroup.options),
        )

        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def search_global(
        self,
        q: Optional[str] = None,
        only_available: bool = True,
        is_popular: Optional[bool] = None,
        is_recommended: Optional[bool] = None,
        skip: int = 0,
        limit: int = 20,
    ) -> List[MenuItem]:
        stmt = select(MenuItem)
        if only_available:
            stmt = stmt.filter(MenuItem.is_available == True)
        if is_popular is not None:
            stmt = stmt.filter(MenuItem.is_popular == is_popular)
        if is_recommended is not None:
            stmt = stmt.filter(MenuItem.is_recommended == is_recommended)

        if q:
            stmt = stmt.filter(
                or_(
                    MenuItem.name.ilike(f"%{q}%"),
                    MenuItem.description.ilike(f"%{q}%"),
                )
            )

        stmt = stmt.offset(skip).limit(limit)
        stmt = stmt.options(
            selectinload(MenuItem.variants),
            selectinload(MenuItem.addons),
            selectinload(MenuItem.option_groups).selectinload(MenuOptionGroup.options),
        )

        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def count_search_global(
        self,
        q: Optional[str] = None,
        only_available: bool = True,
        is_popular: Optional[bool] = None,
        is_recommended: Optional[bool] = None,
    ) -> int:
        stmt = select(func.count(MenuItem.id))
        if only_available:
            stmt = stmt.filter(MenuItem.is_available == True)
        if is_popular is not None:
            stmt = stmt.filter(MenuItem.is_popular == is_popular)
        if is_recommended is not None:
            stmt = stmt.filter(MenuItem.is_recommended == is_recommended)

        if q:
            stmt = stmt.filter(
                or_(
                    MenuItem.name.ilike(f"%{q}%"),
                    MenuItem.description.ilike(f"%{q}%"),
                )
            )

        result = await self.db.execute(stmt)
        return result.scalar() or 0


class MenuItemVariantRepository(BaseRepository[MenuItemVariant]):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(MenuItemVariant, db)

    async def get_by_menu_item(self, menu_item_id: int) -> List[MenuItemVariant]:
        result = await self.db.execute(
            select(MenuItemVariant).filter(MenuItemVariant.menu_item_id == menu_item_id)
        )
        return list(result.scalars().all())


class MenuItemAddonRepository(BaseRepository[MenuItemAddon]):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(MenuItemAddon, db)

    async def get_by_menu_item(self, menu_item_id: int) -> List[MenuItemAddon]:
        result = await self.db.execute(
            select(MenuItemAddon).filter(MenuItemAddon.menu_item_id == menu_item_id)
        )
        return list(result.scalars().all())


class MenuOptionGroupRepository(BaseRepository[MenuOptionGroup]):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(MenuOptionGroup, db)

    async def get_by_menu_item(self, menu_item_id: int) -> List[MenuOptionGroup]:
        result = await self.db.execute(
            select(MenuOptionGroup)
            .filter(MenuOptionGroup.menu_item_id == menu_item_id)
            .options(selectinload(MenuOptionGroup.options))
            .order_by(MenuOptionGroup.display_order.asc())
        )
        return list(result.scalars().all())

    async def get_with_options(self, group_id: int) -> Optional[MenuOptionGroup]:
        result = await self.db.execute(
            select(MenuOptionGroup)
            .filter(MenuOptionGroup.id == group_id)
            .options(selectinload(MenuOptionGroup.options))
        )
        return result.scalars().first()


class MenuOptionRepository(BaseRepository[MenuOption]):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(MenuOption, db)

    async def get_by_group(self, group_id: int) -> List[MenuOption]:
        result = await self.db.execute(
            select(MenuOption)
            .filter(MenuOption.option_group_id == group_id)
            .order_by(MenuOption.display_order.asc())
        )
        return list(result.scalars().all())
