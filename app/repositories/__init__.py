"""
CLMStore Repositories Package
"""
from __future__ import annotations

from app.repositories.base import BaseRepository
from app.repositories.user_repository import (
    UserRepository,
    UserAddressRepository,
    UserFavoriteRepository,
    RefreshTokenRepository,
    OTPVerificationRepository,
)
from app.repositories.restaurant_repository import (
    RestaurantRepository,
    RestaurantDocumentRepository,
    OpeningHoursRepository,
    RestaurantEmployeeRepository,
)
from app.repositories.menu_repository import (
    FoodCategoryRepository,
    MenuItemRepository,
    MenuItemVariantRepository,
    MenuItemAddonRepository,
)
from app.repositories.cart_repository import CartRepository, CartItemRepository
from app.repositories.order_repository import (
    OrderRepository,
    OrderItemRepository,
    OrderStatusHistoryRepository,
)
from app.repositories.payment_repository import (
    PaymentRepository,
    TransactionRepository,
    InvoiceRepository,
    ReceiptRepository,
)
from app.repositories.rider_repository import (
    RiderProfileRepository,
    RiderDocumentRepository,
    RiderEarningRepository,
    RiderWithdrawalRepository,
)
from app.repositories.delivery_repository import DeliveryRepository, RiderLocationRepository
from app.repositories.review_repository import ReviewRepository
from app.repositories.coupon_repository import CouponRepository, CouponUsageRepository
from app.repositories.notification_repository import NotificationRepository

__all__ = [
    "BaseRepository",
    "UserRepository",
    "UserAddressRepository",
    "UserFavoriteRepository",
    "RefreshTokenRepository",
    "OTPVerificationRepository",
    "RestaurantRepository",
    "RestaurantDocumentRepository",
    "OpeningHoursRepository",
    "RestaurantEmployeeRepository",
    "FoodCategoryRepository",
    "MenuItemRepository",
    "MenuItemVariantRepository",
    "MenuItemAddonRepository",
    "CartRepository",
    "CartItemRepository",
    "OrderRepository",
    "OrderItemRepository",
    "OrderStatusHistoryRepository",
    "PaymentRepository",
    "TransactionRepository",
    "InvoiceRepository",
    "ReceiptRepository",
    "RiderProfileRepository",
    "RiderDocumentRepository",
    "RiderEarningRepository",
    "RiderWithdrawalRepository",
    "DeliveryRepository",
    "RiderLocationRepository",
    "ReviewRepository",
    "CouponRepository",
    "CouponUsageRepository",
    "NotificationRepository",
]
