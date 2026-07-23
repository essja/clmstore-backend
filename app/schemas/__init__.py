"""
CLMStore Schemas Package
"""
from __future__ import annotations

from app.schemas.common import MessageResponse, PaginationMeta, PaginatedResponse, Token, TokenData
from app.schemas.user import (
    UserAddressBase,
    UserAddressCreate,
    UserAddressUpdate,
    UserAddressResponse,
    UserRegisterRequest,
    UserLoginRequest,
    TokenRefreshRequest,
    ForgotPasswordRequest,
    ResetPasswordRequest,
    PhoneVerifyRequest,
    EmailVerifyRequest,
    UserProfileResponse,
    UserProfileUpdateRequest,
    UserFavoriteResponse,
)
from app.schemas.restaurant import (
    OpeningHoursBase,
    OpeningHoursCreate,
    OpeningHoursResponse,
    RestaurantDocumentBase,
    RestaurantDocumentCreate,
    RestaurantDocumentResponse,
    RestaurantEmployeeCreate,
    RestaurantEmployeeResponse,
    RestaurantBase,
    RestaurantCreate,
    RestaurantUpdate,
    RestaurantResponse,
)
from app.schemas.menu import (
    MenuItemVariantBase,
    MenuItemVariantCreate,
    MenuItemVariantResponse,
    MenuItemAddonBase,
    MenuItemAddonCreate,
    MenuItemAddonResponse,
    FoodCategoryBase,
    FoodCategoryCreate,
    FoodCategoryResponse,
    MenuItemBase,
    MenuItemCreate,
    MenuItemUpdate,
    MenuItemResponse,
    MenuItemStockUpdate,
)
from app.schemas.cart import (
    AddonSelection,
    CartItemAddRequest,
    CartItemUpdateRequest,
    CartItemResponse,
    CartResponse,
    ApplyCouponRequest,
    MergeCartRequest,
)
from app.schemas.order import (
    OrderItemResponse,
    OrderStatusHistoryResponse,
    OrderCreateRequest,
    OrderResponse,
    OrderCancelRequest,
    OrderRejectRequest,
    OrderAssignRiderRequest,
)
from app.schemas.payment import (
    PaymentInitiateRequest,
    PaymentVerifyResponse,
    TransactionResponse,
    InvoiceResponse,
    ReceiptResponse,
    PaymentResponse,
    RefundRequest,
)
from app.schemas.rider import (
    RiderProfileRegisterRequest,
    RiderProfileUpdateRequest,
    RiderDocumentCreate,
    RiderDocumentResponse,
    RiderProfileResponse,
    RiderEarningResponse,
    RiderWithdrawalRequest,
    RiderWithdrawalResponse,
)
from app.schemas.delivery import DeliveryBase, DeliveryResponse, DeliveryFailRequest
from app.schemas.location import Coordinates, LocationUpdateRequest, RiderLocationResponse, GeocodingResult, DistanceCalculationRequest, DistanceCalculationResponse
from app.schemas.review import ReviewCreateRequest, ReviewResponse, RatingSummary
from app.schemas.coupon import CouponBase, CouponCreate, CouponUpdate, CouponResponse, CouponValidateRequest
from app.schemas.notification import NotificationResponse, NotificationPreferencesResponse, NotificationPreferencesUpdate
from app.schemas.admin import (
    DashboardStatsResponse,
    SupportTicketBase,
    SupportTicketCreate,
    SupportTicketResponse,
    SupportTicketUpdate,
    DisputeCreate,
    DisputeResponse,
    DisputeResolveRequest,
    SystemSettingsResponse,
    SystemSettingsUpdateRequest,
    HomepageBannerCreate,
    HomepageBannerResponse,
    FeaturedRestaurantsUpdateRequest,
)
