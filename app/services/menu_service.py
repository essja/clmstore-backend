"""
CLMStore — Menu Service
"""
from __future__ import annotations

from typing import List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions.custom import NotFoundException, ForbiddenException
from app.models.menu import FoodCategory, MenuItem, MenuItemVariant, MenuItemAddon, MenuOptionGroup, MenuOption
from app.repositories.menu_repository import (
    FoodCategoryRepository,
    MenuItemRepository,
    MenuItemVariantRepository,
    MenuItemAddonRepository,
    MenuOptionGroupRepository,
    MenuOptionRepository,
)
from app.schemas.menu import (
    FoodCategoryCreate,
    MenuItemCreate,
    MenuItemUpdate,
    MenuItemVariantCreate,
    MenuItemAddonCreate,
    MenuOptionGroupCreate,
    MenuOptionGroupUpdate,
    MenuOptionCreate,
    MenuOptionUpdate,
)


class MenuService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.category_repo = FoodCategoryRepository(db)
        self.item_repo = MenuItemRepository(db)
        self.variant_repo = MenuItemVariantRepository(db)
        self.addon_repo = MenuItemAddonRepository(db)
        self.option_group_repo = MenuOptionGroupRepository(db)
        self.option_repo = MenuOptionRepository(db)

    # ── Food Categories CRUD ──────────────────────────────────────────────────
    async def create_category(self, restaurant_id: int, schema: FoodCategoryCreate) -> FoodCategory:
        cat = FoodCategory(
            restaurant_id=restaurant_id,
            name=schema.name,
            description=schema.description,
            sort_order=schema.sort_order,
            is_active=schema.is_active,
        )
        return await self.category_repo.create(cat)

    async def get_category(self, category_id: int) -> FoodCategory:
        cat = await self.category_repo.get(category_id)
        if not cat:
            raise NotFoundException("Food Category")
        return cat

    async def update_category(self, category_id: int, schema: FoodCategoryCreate) -> FoodCategory:
        cat = await self.get_category(category_id)
        return await self.category_repo.update(cat, schema)

    async def delete_category(self, category_id: int) -> None:
        await self.category_repo.delete(category_id)

    async def list_categories(self, restaurant_id: int, only_active: bool = True) -> List[FoodCategory]:
        return await self.category_repo.get_by_restaurant(restaurant_id, only_active)

    # ── Menu Items CRUD ───────────────────────────────────────────────────────
    async def create_menu_item(self, restaurant_id: int, schema: MenuItemCreate) -> MenuItem:
        item = MenuItem(
            restaurant_id=restaurant_id,
            category_id=schema.category_id,
            name=schema.name,
            description=schema.description,
            price=schema.price,
            image=getattr(schema, 'image', None),
            is_available=schema.is_available,
            is_popular=schema.is_popular,
            is_recommended=schema.is_recommended,
            is_vegan=schema.is_vegan,
            is_vegetarian=schema.is_vegetarian,
            is_spicy=schema.is_spicy,
            discount_percentage=schema.discount_percentage,
            stock_count=schema.stock_count,
            preparation_time_min=schema.preparation_time_min,
            calories=schema.calories,
            sort_order=schema.sort_order,
        )
        return await self.item_repo.create(item)

    async def get_menu_item(self, item_id: int) -> MenuItem:
        item = await self.item_repo.get_with_details(item_id)
        if not item:
            raise NotFoundException("Menu Item")
        return item

    async def update_menu_item(self, item_id: int, schema: MenuItemUpdate) -> MenuItem:
        item = await self.get_menu_item(item_id)
        return await self.item_repo.update(item, schema)

    async def upload_food_image(self, item_id: int, file_url: str) -> MenuItem:
        item = await self.get_menu_item(item_id)
        item.image = file_url
        self.db.add(item)
        return item

    async def _set_availability(self, item_id: int, is_available: bool) -> MenuItem:
        item = await self.get_menu_item(item_id)
        item.is_available = is_available
        self.db.add(item)
        return item

    async def update_stock(self, item_id: int, stock_count: Optional[int]) -> MenuItem:
        item = await self.get_menu_item(item_id)
        item.stock_count = stock_count
        self.db.add(item)
        return item

    async def delete_menu_item(self, item_id: int) -> None:
        await self.item_repo.delete(item_id)

    async def list_menu_items(
        self,
        restaurant_id: int,
        category_id: Optional[int] = None,
        only_available: bool = True,
    ) -> List[MenuItem]:
        return await self.item_repo.get_by_restaurant(restaurant_id, category_id, only_available)

    # ── Variants ──────────────────────────────────────────────────────────────
    async def add_variant(self, item_id: int, schema: MenuItemVariantCreate) -> MenuItemVariant:
        var = MenuItemVariant(
            menu_item_id=item_id,
            name=schema.name,
            price_modifier=schema.price_modifier,
            is_available=schema.is_available,
            sort_order=schema.sort_order,
        )
        return await self.variant_repo.create(var)

    async def delete_variant(self, variant_id: int) -> None:
        await self.variant_repo.delete(variant_id)

    # ── Addons ────────────────────────────────────────────────────────────────
    async def add_addon(self, item_id: int, schema: MenuItemAddonCreate) -> MenuItemAddon:
        addon = MenuItemAddon(
            menu_item_id=item_id,
            name=schema.name,
            price=schema.price,
            is_required=schema.is_required,
            max_selections=schema.max_selections,
            is_available=schema.is_available,
        )
        return await self.addon_repo.create(addon)

    async def delete_addon(self, addon_id: int) -> None:
        await self.addon_repo.delete(addon_id)

    # ── Router-facing wrappers ─────────────────────────────────────────────────

    async def get_menu(
        self,
        restaurant_id: int,
        category_id: Optional[int] = None,
        is_available: Optional[bool] = None,
        is_popular: Optional[bool] = None,
        is_recommended: Optional[bool] = None,
        is_discounted: Optional[bool] = None,
        query: Optional[str] = None,
    ) -> List[MenuItem]:
        items = await self.item_repo.get_by_restaurant(
            restaurant_id, category_id, only_available=False
        )
        if is_available is not None:
            items = [i for i in items if i.is_available == is_available]
        if is_popular is not None:
            items = [i for i in items if i.is_popular == is_popular]
        if is_recommended is not None:
            items = [i for i in items if i.is_recommended == is_recommended]
        if is_discounted is not None:
            if is_discounted:
                items = [i for i in items if i.discount_percentage and i.discount_percentage > 0]
            else:
                items = [i for i in items if not i.discount_percentage or i.discount_percentage == 0]
        if query:
            q = query.lower()
            items = [i for i in items if q in i.name.lower() or (i.description and q in i.description.lower())]
        return items

    async def get_item(self, restaurant_id: int, item_id: int) -> MenuItem:
        return await self.get_menu_item(item_id)

    async def create_item(self, restaurant_id: int, schema: "MenuItemCreate", current_user: "User") -> MenuItem:
        item = await self.create_menu_item(restaurant_id, schema)
        return await self.get_menu_item(item.id)

    async def update_item(self, restaurant_id: int, item_id: int, schema: "MenuItemUpdate", current_user: "User") -> MenuItem:
        return await self.update_menu_item(item_id, schema)

    async def delete_item(self, restaurant_id: int, item_id: int, current_user: "User") -> None:
        return await self.delete_menu_item(item_id)

    async def set_item_image(self, restaurant_id: int, item_id: int, url: str, current_user: "User") -> MenuItem:
        return await self.upload_food_image(item_id, url)

    async def toggle_availability(self, restaurant_id: int, item_id: int, current_user: "User") -> bool:
        item = await self.get_menu_item(item_id)
        new_state = not item.is_available
        await self._set_availability(item_id, new_state)
        return new_state

    async def update_stock(self, restaurant_id: int, item_id: int, stock_count: Optional[int], current_user: "User") -> MenuItem:
        item = await self.get_menu_item(item_id)
        item.stock_count = stock_count
        self.db.add(item)
        return item

    async def add_variant(self, restaurant_id: int, item_id: int, schema: "MenuItemVariantCreate", current_user: "User") -> "MenuItemVariant":
        var = MenuItemVariant(
            menu_item_id=item_id,
            name=schema.name,
            price_modifier=schema.price_modifier,
            is_available=schema.is_available,
            sort_order=schema.sort_order,
        )
        return await self.variant_repo.create(var)

    async def delete_variant(self, restaurant_id: int, item_id: int, variant_id: int, current_user: "User") -> None:
        await self.variant_repo.delete(variant_id)

    async def add_addon(self, restaurant_id: int, item_id: int, schema: "MenuItemAddonCreate", current_user: "User") -> "MenuItemAddon":
        addon = MenuItemAddon(
            menu_item_id=item_id,
            name=schema.name,
            price=schema.price,
            is_required=schema.is_required,
            max_selections=schema.max_selections,
            is_available=schema.is_available,
        )
        return await self.addon_repo.create(addon)

    async def delete_addon(self, restaurant_id: int, item_id: int, addon_id: int, current_user: "User") -> None:
        await self.addon_repo.delete(addon_id)

    async def set_category_image(self, restaurant_id: int, category_id: int, url: str, current_user: "User") -> "FoodCategory":
        cat = await self.get_category(category_id)
        cat.image = url
        self.db.add(cat)
        return cat

    async def create_category(self, restaurant_id: int, schema: "FoodCategoryCreate", current_user: "User" = None) -> "FoodCategory":
        from app.models.menu import FoodCategory
        cat = FoodCategory(
            restaurant_id=restaurant_id,
            name=schema.name,
            description=schema.description,
            sort_order=schema.sort_order,
            is_active=schema.is_active,
        )
        return await self.category_repo.create(cat)

    async def update_category(self, restaurant_id: int, category_id: int, schema: "FoodCategoryCreate", current_user: "User" = None) -> "FoodCategory":
        cat = await self.get_category(category_id)
        return await self.category_repo.update(cat, schema)

    async def delete_category(self, restaurant_id: int, category_id: int, current_user: "User" = None) -> None:
        await self.category_repo.delete(category_id)

    # ── Option Groups ─────────────────────────────────────────────────────────

    async def list_option_groups(self, restaurant_id: int, item_id: int) -> List[MenuOptionGroup]:
        return await self.option_group_repo.get_by_menu_item(item_id)

    async def create_option_group(
        self, restaurant_id: int, item_id: int, schema: MenuOptionGroupCreate, current_user: "User"
    ) -> MenuOptionGroup:
        group = MenuOptionGroup(
            menu_item_id=item_id,
            name=schema.name,
            group_type=schema.group_type,
            is_required=schema.is_required,
            min_selections=schema.min_selections,
            max_selections=schema.max_selections,
            display_order=schema.display_order,
        )
        group = await self.option_group_repo.create(group)
        # Create inline options if provided
        for opt_schema in schema.options:
            opt = MenuOption(
                option_group_id=group.id,
                name=opt_schema.name,
                price_modifier=opt_schema.price_modifier,
                is_default=opt_schema.is_default,
                is_available=opt_schema.is_available,
                display_order=opt_schema.display_order,
            )
            self.db.add(opt)
        await self.db.flush()
        return await self.option_group_repo.get_with_options(group.id)

    async def update_option_group(
        self, restaurant_id: int, item_id: int, group_id: int, schema: MenuOptionGroupUpdate, current_user: "User"
    ) -> MenuOptionGroup:
        group = await self.option_group_repo.get(group_id)
        if not group or group.menu_item_id != item_id:
            raise NotFoundException("Option Group")
        for field, value in schema.model_dump(exclude_unset=True).items():
            setattr(group, field, value)
        self.db.add(group)
        await self.db.flush()
        return await self.option_group_repo.get_with_options(group_id)

    async def delete_option_group(
        self, restaurant_id: int, item_id: int, group_id: int, current_user: "User"
    ) -> None:
        group = await self.option_group_repo.get(group_id)
        if not group or group.menu_item_id != item_id:
            raise NotFoundException("Option Group")
        await self.option_group_repo.delete(group_id)

    # ── Options ───────────────────────────────────────────────────────────────

    async def add_option(
        self, restaurant_id: int, item_id: int, group_id: int, schema: MenuOptionCreate, current_user: "User"
    ) -> MenuOption:
        group = await self.option_group_repo.get(group_id)
        if not group or group.menu_item_id != item_id:
            raise NotFoundException("Option Group")
        opt = MenuOption(
            option_group_id=group_id,
            name=schema.name,
            price_modifier=schema.price_modifier,
            is_default=schema.is_default,
            is_available=schema.is_available,
            display_order=schema.display_order,
        )
        return await self.option_repo.create(opt)

    async def update_option(
        self, restaurant_id: int, item_id: int, group_id: int, option_id: int, schema: MenuOptionUpdate, current_user: "User"
    ) -> MenuOption:
        opt = await self.option_repo.get(option_id)
        if not opt or opt.option_group_id != group_id:
            raise NotFoundException("Option")
        for field, value in schema.model_dump(exclude_unset=True).items():
            setattr(opt, field, value)
        self.db.add(opt)
        await self.db.flush()
        return opt

    async def delete_option(
        self, restaurant_id: int, item_id: int, group_id: int, option_id: int, current_user: "User"
    ) -> None:
        opt = await self.option_repo.get(option_id)
        if not opt or opt.option_group_id != group_id:
            raise NotFoundException("Option")
        await self.option_repo.delete(option_id)
