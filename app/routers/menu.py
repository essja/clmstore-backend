"""
CLMStore — Menu / Food Router
Manages food categories, menu items, variants, addons, and images.
"""
from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, File, Path, Query, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies.auth import get_current_active_user
from app.models.user import User
from app.schemas.common import MessageResponse
from app.schemas.menu import (
    FoodCategoryCreate,
    FoodCategoryResponse,
    MenuItemAddonCreate,
    MenuItemAddonResponse,
    MenuItemCreate,
    MenuItemResponse,
    MenuItemStockUpdate,
    MenuItemUpdate,
    MenuItemVariantCreate,
    MenuItemVariantResponse,
    MenuOptionGroupCreate,
    MenuOptionGroupResponse,
    MenuOptionGroupUpdate,
    MenuOptionCreate,
    MenuOptionResponse,
    MenuOptionUpdate,
)
from app.services.menu_service import MenuService
from app.services.file_service import FileService

router = APIRouter()


# ═══════════════════════════════════════════════════════════════════════════════
# FOOD CATEGORIES
# ═══════════════════════════════════════════════════════════════════════════════

# ── GET /api/v1/restaurants/{restaurant_id}/categories ───────────────────────
@router.get(
    "/{restaurant_id}/categories",
    response_model=List[FoodCategoryResponse],
    summary="List food categories for a restaurant",
)
async def list_categories(
    restaurant_id: int = Path(..., ge=1),
    db: AsyncSession = Depends(get_db),
) -> List[FoodCategoryResponse]:
    service = MenuService(db)
    categories = await service.list_categories(restaurant_id)
    return [FoodCategoryResponse.model_validate(c) for c in categories]


# ── POST /api/v1/restaurants/{restaurant_id}/categories ──────────────────────
@router.post(
    "/{restaurant_id}/categories",
    response_model=FoodCategoryResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new food category",
)
async def create_category(
    restaurant_id: int = Path(..., ge=1),
    body: FoodCategoryCreate = ...,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> FoodCategoryResponse:
    """
    **Request Body:**
    ```json
    {
        "name": "Rice Dishes",
        "description": "All our signature rice meals",
        "sort_order": 1,
        "is_active": true
    }
    ```
    """
    service = MenuService(db)
    category = await service.create_category(restaurant_id, body, current_user)
    return FoodCategoryResponse.model_validate(category)


# ── PATCH /api/v1/restaurants/{restaurant_id}/categories/{category_id} ───────
@router.patch(
    "/{restaurant_id}/categories/{category_id}",
    response_model=FoodCategoryResponse,
    summary="Update a food category",
)
async def update_category(
    restaurant_id: int = Path(..., ge=1),
    category_id: int = Path(..., ge=1),
    body: FoodCategoryCreate = ...,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> FoodCategoryResponse:
    service = MenuService(db)
    category = await service.update_category(restaurant_id, category_id, body, current_user)
    return FoodCategoryResponse.model_validate(category)


# ── DELETE /api/v1/restaurants/{restaurant_id}/categories/{category_id} ──────
@router.delete(
    "/{restaurant_id}/categories/{category_id}",
    response_model=MessageResponse,
    summary="Delete a food category",
)
async def delete_category(
    restaurant_id: int = Path(..., ge=1),
    category_id: int = Path(..., ge=1),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    service = MenuService(db)
    await service.delete_category(restaurant_id, category_id, current_user)
    return MessageResponse(message="Category deleted successfully.")


# ── POST /api/v1/restaurants/{restaurant_id}/categories/{category_id}/image ──
@router.post(
    "/{restaurant_id}/categories/{category_id}/image",
    response_model=FoodCategoryResponse,
    summary="Upload category image",
)
async def upload_category_image(
    restaurant_id: int = Path(..., ge=1),
    category_id: int = Path(..., ge=1),
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> FoodCategoryResponse:
    file_service = FileService()
    url = await file_service.upload_image(file, folder="categories")
    service = MenuService(db)
    category = await service.set_category_image(restaurant_id, category_id, url, current_user)
    return FoodCategoryResponse.model_validate(category)


# ═══════════════════════════════════════════════════════════════════════════════
# MENU ITEMS (FOOD)
# ═══════════════════════════════════════════════════════════════════════════════

# ── GET /api/v1/restaurants/{restaurant_id}/menu ─────────────────────────────
@router.get(
    "/{restaurant_id}/menu",
    response_model=List[MenuItemResponse],
    summary="Get restaurant menu",
    description="Returns all menu items, optionally filtered by category or availability.",
)
async def get_menu(
    restaurant_id: int = Path(..., ge=1),
    category_id: Optional[int] = Query(default=None),
    is_available: Optional[bool] = Query(default=None),
    is_popular: Optional[bool] = Query(default=None),
    is_recommended: Optional[bool] = Query(default=None),
    is_discounted: Optional[bool] = Query(default=None),
    q: Optional[str] = Query(default=None, description="Search food items by name"),
    db: AsyncSession = Depends(get_db),
) -> List[MenuItemResponse]:
    service = MenuService(db)
    items = await service.get_menu(
        restaurant_id,
        category_id=category_id,
        is_available=is_available,
        is_popular=is_popular,
        is_recommended=is_recommended,
        is_discounted=is_discounted,
        query=q,
    )
    return [MenuItemResponse.model_validate(i) for i in items]


# ── GET /api/v1/restaurants/{restaurant_id}/menu/{item_id} ───────────────────
@router.get(
    "/{restaurant_id}/menu/{item_id}",
    response_model=MenuItemResponse,
    summary="Get a single menu item",
)
async def get_menu_item(
    restaurant_id: int = Path(..., ge=1),
    item_id: int = Path(..., ge=1),
    db: AsyncSession = Depends(get_db),
) -> MenuItemResponse:
    service = MenuService(db)
    item = await service.get_item(restaurant_id, item_id)
    return MenuItemResponse.model_validate(item)


# ── POST /api/v1/restaurants/{restaurant_id}/menu ────────────────────────────
@router.post(
    "/{restaurant_id}/menu",
    response_model=MenuItemResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new menu item",
)
async def create_menu_item(
    restaurant_id: int = Path(..., ge=1),
    body: MenuItemCreate = ...,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> MenuItemResponse:
    """
    **Request Body:**
    ```json
    {
        "name": "Jollof Rice",
        "description": "Classic Sierra Leonean jollof rice with chicken",
        "price": 35000.0,
        "category_id": 1,
        "is_available": true,
        "is_popular": true,
        "discount_percentage": 10.0,
        "preparation_time_min": 20,
        "calories": 650,
        "is_spicy": false
    }
    ```
    """
    service = MenuService(db)
    item = await service.create_item(restaurant_id, body, current_user)
    return MenuItemResponse.model_validate(item)


# ── PATCH /api/v1/restaurants/{restaurant_id}/menu/{item_id} ─────────────────
@router.patch(
    "/{restaurant_id}/menu/{item_id}",
    response_model=MenuItemResponse,
    summary="Update a menu item",
)
async def update_menu_item(
    restaurant_id: int = Path(..., ge=1),
    item_id: int = Path(..., ge=1),
    body: MenuItemUpdate = ...,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> MenuItemResponse:
    service = MenuService(db)
    item = await service.update_item(restaurant_id, item_id, body, current_user)
    return MenuItemResponse.model_validate(item)


# ── DELETE /api/v1/restaurants/{restaurant_id}/menu/{item_id} ────────────────
@router.delete(
    "/{restaurant_id}/menu/{item_id}",
    response_model=MessageResponse,
    summary="Delete a menu item",
)
async def delete_menu_item(
    restaurant_id: int = Path(..., ge=1),
    item_id: int = Path(..., ge=1),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    service = MenuService(db)
    await service.delete_item(restaurant_id, item_id, current_user)
    return MessageResponse(message="Menu item deleted successfully.")


# ── POST /api/v1/restaurants/{restaurant_id}/menu/{item_id}/image ─────────────
@router.post(
    "/{restaurant_id}/menu/{item_id}/image",
    response_model=MenuItemResponse,
    summary="Upload food image",
)
async def upload_food_image(
    restaurant_id: int = Path(..., ge=1),
    item_id: int = Path(..., ge=1),
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> MenuItemResponse:
    file_service = FileService()
    url = await file_service.upload_image(file, folder="menu")
    service = MenuService(db)
    item = await service.set_item_image(restaurant_id, item_id, url, current_user)
    return MenuItemResponse.model_validate(item)


# ── PATCH /api/v1/restaurants/{restaurant_id}/menu/{item_id}/toggle ───────────
@router.patch(
    "/{restaurant_id}/menu/{item_id}/toggle",
    response_model=MessageResponse,
    summary="Toggle menu item availability (pause/resume)",
)
async def toggle_item_availability(
    restaurant_id: int = Path(..., ge=1),
    item_id: int = Path(..., ge=1),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    service = MenuService(db)
    is_available = await service.toggle_availability(restaurant_id, item_id, current_user)
    state = "available" if is_available else "paused"
    return MessageResponse(message=f"Item is now {state}.")


# ── PATCH /api/v1/restaurants/{restaurant_id}/menu/{item_id}/stock ─────────────
@router.patch(
    "/{restaurant_id}/menu/{item_id}/stock",
    response_model=MenuItemResponse,
    summary="Update menu item stock count",
)
async def update_stock(
    restaurant_id: int = Path(..., ge=1),
    item_id: int = Path(..., ge=1),
    body: MenuItemStockUpdate = ...,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> MenuItemResponse:
    """
    Set `stock_count` to `null` for unlimited stock, or a positive integer for limited stock.
    """
    service = MenuService(db)
    item = await service.update_stock(restaurant_id, item_id, body.stock_count, current_user)
    return MenuItemResponse.model_validate(item)


# ═══════════════════════════════════════════════════════════════════════════════
# VARIANTS
# ═══════════════════════════════════════════════════════════════════════════════

# ── POST /api/v1/restaurants/{restaurant_id}/menu/{item_id}/variants ──────────
@router.post(
    "/{restaurant_id}/menu/{item_id}/variants",
    response_model=MenuItemVariantResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add a variant to a menu item (e.g. Small, Large)",
)
async def add_variant(
    restaurant_id: int = Path(..., ge=1),
    item_id: int = Path(..., ge=1),
    body: MenuItemVariantCreate = ...,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> MenuItemVariantResponse:
    """
    **Request Body:**
    ```json
    {"name": "Large", "price_modifier": 5000.0, "is_available": true}
    ```
    """
    service = MenuService(db)
    variant = await service.add_variant(restaurant_id, item_id, body, current_user)
    return MenuItemVariantResponse.model_validate(variant)


# ── DELETE /api/v1/restaurants/{restaurant_id}/menu/{item_id}/variants/{variant_id}
@router.delete(
    "/{restaurant_id}/menu/{item_id}/variants/{variant_id}",
    response_model=MessageResponse,
    summary="Remove a menu item variant",
)
async def delete_variant(
    restaurant_id: int = Path(..., ge=1),
    item_id: int = Path(..., ge=1),
    variant_id: int = Path(..., ge=1),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    service = MenuService(db)
    await service.delete_variant(restaurant_id, item_id, variant_id, current_user)
    return MessageResponse(message="Variant removed successfully.")


# ═══════════════════════════════════════════════════════════════════════════════
# ADDONS
# ═══════════════════════════════════════════════════════════════════════════════

# ── POST /api/v1/restaurants/{restaurant_id}/menu/{item_id}/addons ─────────────
@router.post(
    "/{restaurant_id}/menu/{item_id}/addons",
    response_model=MenuItemAddonResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add an addon to a menu item (e.g. Extra Cheese)",
)
async def add_addon(
    restaurant_id: int = Path(..., ge=1),
    item_id: int = Path(..., ge=1),
    body: MenuItemAddonCreate = ...,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> MenuItemAddonResponse:
    """
    **Request Body:**
    ```json
    {
        "name": "Extra Pepper Sauce",
        "price": 2000.0,
        "is_required": false,
        "max_selections": 1
    }
    ```
    """
    service = MenuService(db)
    addon = await service.add_addon(restaurant_id, item_id, body, current_user)
    return MenuItemAddonResponse.model_validate(addon)


# ── DELETE /api/v1/restaurants/{restaurant_id}/menu/{item_id}/addons/{addon_id}
@router.delete(
    "/{restaurant_id}/menu/{item_id}/addons/{addon_id}",
    response_model=MessageResponse,
    summary="Remove an addon from a menu item",
)
async def delete_addon(
    restaurant_id: int = Path(..., ge=1),
    item_id: int = Path(..., ge=1),
    addon_id: int = Path(..., ge=1),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    service = MenuService(db)
    await service.delete_addon(restaurant_id, item_id, addon_id, current_user)
    return MessageResponse(message="Addon removed successfully.")


# ═══════════════════════════════════════════════════════════════════════════════
# OPTION GROUPS (Customisation Groups)
# ═══════════════════════════════════════════════════════════════════════════════

# ── GET /api/v1/restaurants/{restaurant_id}/menu/{item_id}/option-groups ──────
@router.get(
    "/{restaurant_id}/menu/{item_id}/option-groups",
    response_model=List[MenuOptionGroupResponse],
    summary="List customisation groups for a menu item",
)
async def list_option_groups(
    restaurant_id: int = Path(..., ge=1),
    item_id: int = Path(..., ge=1),
    db: AsyncSession = Depends(get_db),
) -> List[MenuOptionGroupResponse]:
    service = MenuService(db)
    groups = await service.list_option_groups(restaurant_id, item_id)
    return [MenuOptionGroupResponse.model_validate(g) for g in groups]


# ── POST /api/v1/restaurants/{restaurant_id}/menu/{item_id}/option-groups ─────
@router.post(
    "/{restaurant_id}/menu/{item_id}/option-groups",
    response_model=MenuOptionGroupResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add a customisation group to a menu item",
)
async def create_option_group(
    restaurant_id: int = Path(..., ge=1),
    item_id: int = Path(..., ge=1),
    body: MenuOptionGroupCreate = ...,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> MenuOptionGroupResponse:
    """
    **Request Body:**
    ```json
    {
        "name": "Choose Size",
        "group_type": "single",
        "is_required": true,
        "min_selections": 1,
        "max_selections": 1,
        "display_order": 0,
        "options": [
            {"name": "Small", "price_modifier": 0, "is_default": true},
            {"name": "Large", "price_modifier": 5000}
        ]
    }
    ```
    """
    service = MenuService(db)
    group = await service.create_option_group(restaurant_id, item_id, body, current_user)
    return MenuOptionGroupResponse.model_validate(group)


# ── PATCH /api/v1/restaurants/{restaurant_id}/menu/{item_id}/option-groups/{group_id}
@router.patch(
    "/{restaurant_id}/menu/{item_id}/option-groups/{group_id}",
    response_model=MenuOptionGroupResponse,
    summary="Update a customisation group",
)
async def update_option_group(
    restaurant_id: int = Path(..., ge=1),
    item_id: int = Path(..., ge=1),
    group_id: int = Path(..., ge=1),
    body: MenuOptionGroupUpdate = ...,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> MenuOptionGroupResponse:
    service = MenuService(db)
    group = await service.update_option_group(restaurant_id, item_id, group_id, body, current_user)
    return MenuOptionGroupResponse.model_validate(group)


# ── DELETE /api/v1/restaurants/{restaurant_id}/menu/{item_id}/option-groups/{group_id}
@router.delete(
    "/{restaurant_id}/menu/{item_id}/option-groups/{group_id}",
    response_model=MessageResponse,
    summary="Delete a customisation group (and all its options)",
)
async def delete_option_group(
    restaurant_id: int = Path(..., ge=1),
    item_id: int = Path(..., ge=1),
    group_id: int = Path(..., ge=1),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    service = MenuService(db)
    await service.delete_option_group(restaurant_id, item_id, group_id, current_user)
    return MessageResponse(message="Option group deleted.")


# ═══════════════════════════════════════════════════════════════════════════════
# OPTIONS (within a group)
# ═══════════════════════════════════════════════════════════════════════════════

# ── POST …/option-groups/{group_id}/options ───────────────────────────────────
@router.post(
    "/{restaurant_id}/menu/{item_id}/option-groups/{group_id}/options",
    response_model=MenuOptionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add an option to a customisation group",
)
async def add_option(
    restaurant_id: int = Path(..., ge=1),
    item_id: int = Path(..., ge=1),
    group_id: int = Path(..., ge=1),
    body: MenuOptionCreate = ...,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> MenuOptionResponse:
    service = MenuService(db)
    opt = await service.add_option(restaurant_id, item_id, group_id, body, current_user)
    return MenuOptionResponse.model_validate(opt)


# ── PATCH …/option-groups/{group_id}/options/{option_id} ─────────────────────
@router.patch(
    "/{restaurant_id}/menu/{item_id}/option-groups/{group_id}/options/{option_id}",
    response_model=MenuOptionResponse,
    summary="Update a customisation option",
)
async def update_option(
    restaurant_id: int = Path(..., ge=1),
    item_id: int = Path(..., ge=1),
    group_id: int = Path(..., ge=1),
    option_id: int = Path(..., ge=1),
    body: MenuOptionUpdate = ...,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> MenuOptionResponse:
    service = MenuService(db)
    opt = await service.update_option(restaurant_id, item_id, group_id, option_id, body, current_user)
    return MenuOptionResponse.model_validate(opt)


# ── DELETE …/option-groups/{group_id}/options/{option_id} ────────────────────
@router.delete(
    "/{restaurant_id}/menu/{item_id}/option-groups/{group_id}/options/{option_id}",
    response_model=MessageResponse,
    summary="Delete a customisation option",
)
async def delete_option(
    restaurant_id: int = Path(..., ge=1),
    item_id: int = Path(..., ge=1),
    group_id: int = Path(..., ge=1),
    option_id: int = Path(..., ge=1),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    service = MenuService(db)
    await service.delete_option(restaurant_id, item_id, group_id, option_id, current_user)
    return MessageResponse(message="Option deleted.")
