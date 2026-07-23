"""
CLMStore — Restaurants Router
Handles restaurant discovery, CRUD, approval, suspension, and hours management.
"""
from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, File, Path, Query, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies.auth import get_current_active_user
from app.dependencies.pagination import PaginationParams
from app.models.user import User
from app.schemas.common import MessageResponse, PaginatedResponse
from app.schemas.restaurant import (
    OpeningHoursCreate,
    OpeningHoursResponse,
    RestaurantCreate,
    RestaurantDocumentResponse,
    RestaurantEarningResponse,
    RestaurantEmployeeCreate,
    RestaurantEmployeeResponse,
    RestaurantResponse,
    RestaurantUpdate,
    RestaurantWithdrawalRequest,
    RestaurantWithdrawalResponse,
)
from app.services.restaurant_service import RestaurantService
from app.services.file_service import FileService
from app.utils.constants import OperatingStatus, RestaurantStatus, UserRole, StoreType

router = APIRouter()

# ── Helpers ───────────────────────────────────────────────────────────────────
def _require_owner_or_admin(current_user: User) -> None:
    from app.exceptions.custom import ForbiddenException
    if current_user.role not in (UserRole.RESTAURANT_OWNER, UserRole.ADMIN, UserRole.SUPER_ADMIN):
        raise ForbiddenException("Restaurant owners only.")


# ── GET /api/v1/restaurants ───────────────────────────────────────────────────
@router.get(
    "",
    response_model=PaginatedResponse[RestaurantResponse],
    summary="Browse and search restaurants",
    description=(
        "Returns a paginated list of verified, active restaurants. "
        "Supports search by name, filtering by cuisine type, and sorting."
    ),
)
async def list_restaurants(
    q: Optional[str] = Query(default=None, description="Search by name or cuisine"),
    store_type: Optional[StoreType] = Query(default=None, description="restaurant | grocery | pharmacy"),
    cuisine: Optional[str] = Query(default=None, description="Filter by cuisine type"),
    city: Optional[str] = Query(default="Freetown"),
    is_open: Optional[bool] = Query(default=None, description="Filter by currently open status"),
    featured: Optional[bool] = Query(default=None, description="Show only featured restaurants"),
    lat: Optional[float] = Query(default=None, ge=-90.0, le=90.0, description="User latitude for proximity search"),
    lon: Optional[float] = Query(default=None, ge=-180.0, le=180.0, description="User longitude for proximity search"),
    radius_km: float = Query(default=10.0, ge=0.1, le=50.0, description="Search radius in km"),
    sort_by: str = Query(default="rating", description="rating | distance | delivery_fee | name"),
    pagination: PaginationParams = Depends(),
    db: AsyncSession = Depends(get_db),
) -> PaginatedResponse[RestaurantResponse]:
    """
    **Examples:**
    - `GET /api/v1/restaurants?store_type=restaurant` — all restaurants
    - `GET /api/v1/restaurants?store_type=grocery` — grocery stores
    - `GET /api/v1/restaurants?store_type=pharmacy` — pharmacies
    - `GET /api/v1/restaurants?q=rice&is_open=true&lat=8.484&lon=-13.234&sort_by=distance`
    """
    service = RestaurantService(db)
    restaurants, total = await service.search_restaurants(
        query=q,
        store_type=store_type,
        cuisine=cuisine,
        city=city,
        is_open=is_open,
        featured=featured,
        lat=lat,
        lon=lon,
        radius_km=radius_km,
        sort_by=sort_by,
        skip=pagination.skip,
        limit=pagination.limit,
    )
    return PaginatedResponse(
        data=restaurants,  # already RestaurantResponse objects from service
        pagination=pagination.meta(total),
    )


# ── GET /api/v1/restaurants/my ───────────────────────────────────────────────
# NOTE: must be defined before /{restaurant_id} so FastAPI doesn't try to cast "my" as int
@router.get(
    "/my",
    response_model=RestaurantResponse,
    summary="Get the current owner's restaurant",
)
async def get_my_restaurant(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> RestaurantResponse:
    _require_owner_or_admin(current_user)
    from sqlalchemy import select
    from app.models.restaurant import Restaurant
    from app.exceptions.custom import NotFoundException
    result = await db.execute(select(Restaurant).where(Restaurant.owner_id == current_user.id))
    restaurant = result.scalar_one_or_none()
    if not restaurant:
        raise NotFoundException("Restaurant")
    return RestaurantResponse.model_validate(restaurant)


# ── PATCH /api/v1/restaurants/my ─────────────────────────────────────────────
@router.patch(
    "/my",
    response_model=RestaurantResponse,
    summary="Update (or create) the current owner's restaurant",
)
async def update_my_restaurant_owner(
    body: RestaurantUpdate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> RestaurantResponse:
    _require_owner_or_admin(current_user)
    import random
    from slugify import slugify
    from sqlalchemy import select
    from app.models.restaurant import Restaurant
    result = await db.execute(select(Restaurant).where(Restaurant.owner_id == current_user.id))
    restaurant = result.scalar_one_or_none()

    if restaurant:
        service = RestaurantService(db)
        updated = await service.update_restaurant(restaurant.id, body, current_user)
        return RestaurantResponse.model_validate(updated)

    # Owner has no restaurant yet — create one from the submitted fields
    name = body.name or f"{current_user.first_name or 'My'} Restaurant"
    slug = slugify(name)
    slug_taken = await db.execute(select(Restaurant).where(Restaurant.slug == slug))
    if slug_taken.scalar_one_or_none():
        slug = f"{slug}-{random.randint(100, 999)}"

    new_rest = Restaurant(
        owner_id=current_user.id,
        name=name,
        slug=slug,
        description=body.description,
        logo=body.logo,
        cover_image=body.cover_image,
        store_type=body.store_type or StoreType.RESTAURANT,
        cuisine_type=body.cuisine_type or "Sierra Leonean",
        address=body.address or "Freetown, Sierra Leone",
        city=body.city or "Freetown",
        latitude=body.latitude if body.latitude is not None else 8.4657,
        longitude=body.longitude if body.longitude is not None else -13.2317,
        phone=body.phone,
        email=body.email,
        min_order=body.min_order or 0.0,
        delivery_fee=body.delivery_fee or 10000.0,
        delivery_radius_km=body.delivery_radius_km or 5.0,
        min_delivery_time_min=body.min_delivery_time_min or 20,
        avg_delivery_time_min=body.avg_delivery_time_min or 35,
        status=RestaurantStatus.PENDING,
        is_open=False,
    )
    db.add(new_rest)
    await db.flush()
    await db.refresh(new_rest)
    return RestaurantResponse.model_validate(new_rest)


# ── GET /api/v1/restaurants/{restaurant_id} ───────────────────────────────────
@router.get(
    "/{restaurant_id}",
    response_model=RestaurantResponse,
    summary="Get restaurant details",
)
async def get_restaurant(
    restaurant_id: int = Path(..., ge=1),
    db: AsyncSession = Depends(get_db),
) -> RestaurantResponse:
    """Returns complete restaurant profile including opening hours and rating."""
    service = RestaurantService(db)
    restaurant = await service.get_by_id(restaurant_id)
    return RestaurantResponse.model_validate(restaurant)


# ── POST /api/v1/restaurants ─────────────────────────────────────────────────
@router.post(
    "",
    response_model=RestaurantResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new restaurant",
    description="Restaurant owners register a new restaurant. Starts in PENDING status awaiting admin approval.",
)
async def create_restaurant(
    body: RestaurantCreate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> RestaurantResponse:
    """
    **Request Body:**
    ```json
    {
        "name": "Mama's Kitchen",
        "description": "Authentic Sierra Leonean cuisine",
        "cuisine_type": "Sierra Leonean",
        "address": "15 Lumley Beach Road, Freetown",
        "city": "Freetown",
        "latitude": 8.4657,
        "longitude": -13.2317,
        "phone": "+23276123456",
        "email": "mamas@example.com",
        "min_order": 20000.0,
        "delivery_fee": 10000.0,
        "delivery_radius_km": 8.0
    }
    ```
    """
    _require_owner_or_admin(current_user)
    service = RestaurantService(db)
    restaurant = await service.create_restaurant(body, current_user.id)
    return RestaurantResponse.model_validate(restaurant)


# ── PATCH /api/v1/restaurants/{restaurant_id} ────────────────────────────────
@router.patch(
    "/{restaurant_id}",
    response_model=RestaurantResponse,
    summary="Update restaurant details",
)
async def update_restaurant(
    restaurant_id: int = Path(..., ge=1),
    body: RestaurantUpdate = ...,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> RestaurantResponse:
    service = RestaurantService(db)
    restaurant = await service.update_restaurant(restaurant_id, body, current_user)
    return RestaurantResponse.model_validate(restaurant)


# ── DELETE /api/v1/restaurants/{restaurant_id} ───────────────────────────────
@router.delete(
    "/{restaurant_id}",
    response_model=MessageResponse,
    summary="Delete (close) a restaurant",
)
async def delete_restaurant(
    restaurant_id: int = Path(..., ge=1),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    service = RestaurantService(db)
    await service.delete_restaurant(restaurant_id, current_user)
    return MessageResponse(message="Restaurant removed successfully.")


# ── POST /api/v1/restaurants/{restaurant_id}/logo ────────────────────────────
@router.post(
    "/{restaurant_id}/logo",
    response_model=RestaurantResponse,
    summary="Upload restaurant logo",
)
async def upload_logo(
    restaurant_id: int = Path(..., ge=1),
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> RestaurantResponse:
    service = RestaurantService(db)
    file_service = FileService()
    url = await file_service.upload_image(file, folder="restaurants/logos")
    restaurant = await service.update_restaurant(restaurant_id, RestaurantUpdate(), current_user)
    from app.repositories.restaurant_repository import RestaurantRepository
    repo = RestaurantRepository(db)
    r = await repo.get(restaurant_id)
    r.logo = url
    db.add(r)
    return RestaurantResponse.model_validate(r)


# ── POST /api/v1/restaurants/{restaurant_id}/cover ───────────────────────────
@router.post(
    "/{restaurant_id}/cover",
    response_model=RestaurantResponse,
    summary="Upload restaurant cover image",
)
async def upload_cover(
    restaurant_id: int = Path(..., ge=1),
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> RestaurantResponse:
    service = RestaurantService(db)
    file_service = FileService()
    url = await file_service.upload_image(file, folder="restaurants/covers")
    from app.repositories.restaurant_repository import RestaurantRepository
    repo = RestaurantRepository(db)
    r = await repo.get(restaurant_id)
    r.cover_image = url
    db.add(r)
    return RestaurantResponse.model_validate(r)


# ── POST /api/v1/restaurants/{restaurant_id}/documents ───────────────────────
@router.post(
    "/{restaurant_id}/documents",
    response_model=RestaurantDocumentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload restaurant business document",
)
async def upload_document(
    restaurant_id: int = Path(..., ge=1),
    doc_type: str = Query(..., description="business_license | tax_certificate | food_safety_certificate | health_certificate"),
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> RestaurantDocumentResponse:
    """Uploads a verification document (PDF or image) for the restaurant."""
    service = RestaurantService(db)
    doc = await service.upload_document(restaurant_id, doc_type, file, current_user)
    return RestaurantDocumentResponse.model_validate(doc)


# ── GET /api/v1/restaurants/{restaurant_id}/documents ────────────────────────
@router.get(
    "/{restaurant_id}/documents",
    response_model=List[RestaurantDocumentResponse],
    summary="List restaurant documents",
)
async def list_documents(
    restaurant_id: int = Path(..., ge=1),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> List[RestaurantDocumentResponse]:
    service = RestaurantService(db)
    docs = await service.get_documents(restaurant_id, current_user)
    return [RestaurantDocumentResponse.model_validate(d) for d in docs]


# ── GET /api/v1/restaurants/{restaurant_id}/opening-hours ────────────────────
@router.get(
    "/{restaurant_id}/opening-hours",
    response_model=List[OpeningHoursResponse],
    summary="Get restaurant opening hours",
)
async def get_opening_hours(
    restaurant_id: int = Path(..., ge=1),
    db: AsyncSession = Depends(get_db),
) -> List[OpeningHoursResponse]:
    service = RestaurantService(db)
    hours = await service.get_opening_hours(restaurant_id)
    return [OpeningHoursResponse.model_validate(h) for h in hours]


# ── PUT /api/v1/restaurants/{restaurant_id}/opening-hours ────────────────────
@router.put(
    "/{restaurant_id}/opening-hours",
    response_model=List[OpeningHoursResponse],
    summary="Set restaurant opening hours (full week)",
    description="Replaces all opening hours with the provided schedule.",
)
async def set_opening_hours(
    restaurant_id: int = Path(..., ge=1),
    body: List[OpeningHoursCreate] = ...,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> List[OpeningHoursResponse]:
    """
    **Request Body:**
    ```json
    [
        {"day_of_week": "monday", "open_time": "08:00:00", "close_time": "22:00:00", "is_closed": false},
        {"day_of_week": "sunday", "is_closed": true}
    ]
    ```
    """
    service = RestaurantService(db)
    hours = await service.set_opening_hours(restaurant_id, body, current_user)
    return [OpeningHoursResponse.model_validate(h) for h in hours]


# ── PATCH /api/v1/restaurants/{restaurant_id}/toggle-open ────────────────────
@router.patch(
    "/{restaurant_id}/toggle-open",
    response_model=MessageResponse,
    summary="Toggle restaurant open/closed status",
)
async def toggle_open(
    restaurant_id: int = Path(..., ge=1),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    service = RestaurantService(db)
    is_open = await service.toggle_open_status(restaurant_id, current_user)
    status_str = "open" if is_open else "closed"
    return MessageResponse(message=f"Restaurant is now {status_str}.")


# ── GET /api/v1/restaurants/{restaurant_id}/analytics ────────────────────────
@router.get(
    "/{restaurant_id}/analytics",
    summary="Restaurant earnings & order analytics",
)
async def get_analytics(
    restaurant_id: int = Path(..., ge=1),
    period: str = Query(default="week", description="today | week | month | year"),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Returns aggregated analytics for the restaurant:
    - Total orders, revenue, commission paid
    - Average order value
    - Top-selling items
    - Daily revenue chart data
    """
    service = RestaurantService(db)
    return await service.get_analytics(restaurant_id, period, current_user)


# ── GET /api/v1/restaurants/{restaurant_id}/employees ────────────────────────
@router.get(
    "/{restaurant_id}/employees",
    response_model=List[RestaurantEmployeeResponse],
    summary="List restaurant employees",
)
async def list_employees(
    restaurant_id: int = Path(..., ge=1),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> List[RestaurantEmployeeResponse]:
    service = RestaurantService(db)
    employees = await service.list_employees(restaurant_id, current_user)
    return [RestaurantEmployeeResponse.model_validate(e) for e in employees]


# ── POST /api/v1/restaurants/{restaurant_id}/employees ───────────────────────
@router.post(
    "/{restaurant_id}/employees",
    response_model=RestaurantEmployeeResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add employee to restaurant",
)
async def add_employee(
    restaurant_id: int = Path(..., ge=1),
    body: RestaurantEmployeeCreate = ...,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> RestaurantEmployeeResponse:
    service = RestaurantService(db)
    employee = await service.add_employee(restaurant_id, body, current_user)
    return RestaurantEmployeeResponse.model_validate(employee)


# ── DELETE /api/v1/restaurants/{restaurant_id}/employees/{user_id} ───────────
@router.delete(
    "/{restaurant_id}/employees/{user_id}",
    response_model=MessageResponse,
    summary="Remove employee from restaurant",
)
async def remove_employee(
    restaurant_id: int = Path(..., ge=1),
    user_id: int = Path(..., ge=1),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    service = RestaurantService(db)
    await service.remove_employee(restaurant_id, user_id, current_user)
    return MessageResponse(message="Employee removed from restaurant.")


# ── GET /api/v1/restaurants/my/earnings ──────────────────────────────────────
@router.get(
    "/my/earnings",
    response_model=List[RestaurantEarningResponse],
    summary="Get restaurant earnings history",
    description="Returns earnings records for the authenticated restaurant owner's restaurant.",
)
async def list_my_earnings(
    pagination: PaginationParams = Depends(),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> List[RestaurantEarningResponse]:
    _require_owner_or_admin(current_user)
    from sqlalchemy import select
    from app.models.restaurant import Restaurant, RestaurantEarning
    from app.exceptions.custom import NotFoundException

    result = await db.execute(
        select(Restaurant).where(Restaurant.owner_id == current_user.id)
    )
    restaurant = result.scalar_one_or_none()
    if not restaurant:
        raise NotFoundException("Restaurant")

    earnings_result = await db.execute(
        select(RestaurantEarning)
        .where(RestaurantEarning.restaurant_id == restaurant.id)
        .order_by(RestaurantEarning.created_at.desc())
        .offset(pagination.skip)
        .limit(pagination.limit)
    )
    return [RestaurantEarningResponse.model_validate(e) for e in earnings_result.scalars().all()]


# ── GET /api/v1/restaurants/my/earnings/summary ───────────────────────────────
@router.get(
    "/my/earnings/summary",
    summary="Get restaurant earnings summary",
)
async def my_earnings_summary(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    _require_owner_or_admin(current_user)
    from sqlalchemy import select
    from app.models.restaurant import Restaurant

    result = await db.execute(
        select(Restaurant).where(Restaurant.owner_id == current_user.id)
    )
    restaurant = result.scalar_one_or_none()
    from app.exceptions.custom import NotFoundException
    if not restaurant:
        raise NotFoundException("Restaurant")

    return {
        "current_balance": restaurant.current_balance,
        "total_earnings": restaurant.total_earnings,
        "commission_rate": restaurant.commission_rate,
        "restaurant_id": restaurant.id,
        "restaurant_name": restaurant.name,
    }


# ── POST /api/v1/restaurants/my/withdrawal ───────────────────────────────────
@router.post(
    "/my/withdrawal",
    response_model=RestaurantWithdrawalResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Request a balance withdrawal",
)
async def request_withdrawal(
    body: RestaurantWithdrawalRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> RestaurantWithdrawalResponse:
    """
    **Request Body:**
    ```json
    {
        "amount": 500000.0,
        "payment_method": "orange_money",
        "payment_details": "+23276123456"
    }
    ```
    **Minimum withdrawal:** 50,000 SLL
    """
    _require_owner_or_admin(current_user)
    from sqlalchemy import select
    from app.models.restaurant import Restaurant, RestaurantWithdrawal
    from app.exceptions.custom import NotFoundException, BusinessRuleException

    result = await db.execute(
        select(Restaurant).where(Restaurant.owner_id == current_user.id)
    )
    restaurant = result.scalar_one_or_none()
    if not restaurant:
        raise NotFoundException("Restaurant")

    if body.amount > restaurant.current_balance:
        raise BusinessRuleException(
            f"Insufficient balance. Available: {restaurant.current_balance:,.0f} SLL"
        )

    # Deduct balance immediately and hold pending admin approval
    restaurant.current_balance = round(restaurant.current_balance - body.amount, 2)
    db.add(restaurant)

    withdrawal = RestaurantWithdrawal(
        restaurant_id=restaurant.id,
        amount=body.amount,
        status="pending",
        payment_method=body.payment_method,
        payment_details=body.payment_details,
    )
    db.add(withdrawal)
    await db.flush()
    return RestaurantWithdrawalResponse.model_validate(withdrawal)


# ── GET /api/v1/restaurants/my/withdrawals ───────────────────────────────────
@router.get(
    "/my/withdrawals",
    response_model=List[RestaurantWithdrawalResponse],
    summary="Get restaurant withdrawal history",
)
async def list_my_withdrawals(
    pagination: PaginationParams = Depends(),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> List[RestaurantWithdrawalResponse]:
    _require_owner_or_admin(current_user)
    from sqlalchemy import select
    from app.models.restaurant import Restaurant, RestaurantWithdrawal
    from app.exceptions.custom import NotFoundException

    result = await db.execute(
        select(Restaurant).where(Restaurant.owner_id == current_user.id)
    )
    restaurant = result.scalar_one_or_none()
    if not restaurant:
        raise NotFoundException("Restaurant")

    w_result = await db.execute(
        select(RestaurantWithdrawal)
        .where(RestaurantWithdrawal.restaurant_id == restaurant.id)
        .order_by(RestaurantWithdrawal.created_at.desc())
        .offset(pagination.skip)
        .limit(pagination.limit)
    )
    return [RestaurantWithdrawalResponse.model_validate(w) for w in w_result.scalars().all()]


# ── PATCH /api/v1/restaurants/my/operating-status ────────────────────────────
@router.patch(
    "/my/operating-status",
    response_model=RestaurantResponse,
    summary="Set restaurant operating status (open / busy / temporarily_closed)",
)
async def set_operating_status(
    operating_status: str = Query(..., description="open | busy | temporarily_closed"),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> RestaurantResponse:
    """
    Updates the real-time operating status. Also flips `is_open` automatically:
    - `open` / `busy` → is_open = True
    - `temporarily_closed` → is_open = False
    """
    _require_owner_or_admin(current_user)

    valid = {s.value for s in OperatingStatus}
    if operating_status not in valid:
        from app.exceptions.custom import BusinessRuleException
        raise BusinessRuleException(f"Invalid status. Must be one of: {', '.join(valid)}")

    from sqlalchemy import select
    from app.models.restaurant import Restaurant
    from app.exceptions.custom import NotFoundException

    result = await db.execute(select(Restaurant).where(Restaurant.owner_id == current_user.id))
    restaurant = result.scalar_one_or_none()
    if not restaurant:
        raise NotFoundException("Restaurant")

    restaurant.operating_status = operating_status
    restaurant.is_open = operating_status in ("open", "busy")
    db.add(restaurant)
    await db.flush()
    return RestaurantResponse.model_validate(restaurant)
