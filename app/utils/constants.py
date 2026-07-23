"""
CLMStore — Application-wide Enums and Constants
"""
from __future__ import annotations

import enum


# ── User Roles ────────────────────────────────────────────────────────────────
class UserRole(str, enum.Enum):
    CUSTOMER = "customer"
    RESTAURANT_OWNER = "restaurant_owner"
    RIDER = "rider"
    ADMIN = "admin"
    SUPER_ADMIN = "super_admin"


# ── Store Type ────────────────────────────────────────────────────────────────
class StoreType(str, enum.Enum):
    RESTAURANT = "restaurant"
    GROCERY = "grocery"
    PHARMACY = "pharmacy"


# ── Restaurant Status ────────────────────────────────────────────────────────
class RestaurantStatus(str, enum.Enum):
    PENDING = "pending"          # Awaiting admin review
    VERIFIED = "verified"        # Approved and active
    SUSPENDED = "suspended"      # Temporarily suspended
    REJECTED = "rejected"        # Application rejected
    CLOSED = "closed"            # Permanently closed


# ── Operating Status (real-time, set by owner) ───────────────────────────────
class OperatingStatus(str, enum.Enum):
    OPEN = "open"                         # Accepting orders normally
    BUSY = "busy"                         # Accepting orders but slower
    TEMPORARILY_CLOSED = "temporarily_closed"  # Not accepting orders right now


# ── Order Status ─────────────────────────────────────────────────────────────
class OrderStatus(str, enum.Enum):
    PENDING = "pending"          # Placed, awaiting restaurant acceptance
    ACCEPTED = "accepted"        # Restaurant accepted
    PREPARING = "preparing"      # Restaurant is preparing
    READY = "ready"              # Ready for pickup by rider
    PICKED_UP = "picked_up"      # Rider picked up
    ON_THE_WAY = "on_the_way"    # Rider en route to customer
    DELIVERED = "delivered"      # Successfully delivered
    CANCELLED = "cancelled"      # Cancelled by customer/restaurant
    REFUNDED = "refunded"        # Refund processed


# ── Payment Status ────────────────────────────────────────────────────────────
class PaymentStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    REFUNDED = "refunded"
    PARTIALLY_REFUNDED = "partially_refunded"


# ── Payment Provider ──────────────────────────────────────────────────────────
class PaymentProvider(str, enum.Enum):
    CASH = "cash"
    ORANGE_MONEY = "orange_money"
    AFRIMONEY = "afrimoney"
    STRIPE = "stripe"
    PAYPAL = "paypal"
    VISA = "visa"
    MASTERCARD = "mastercard"


# ── Transaction Type ─────────────────────────────────────────────────────────
class TransactionType(str, enum.Enum):
    CHARGE = "charge"
    REFUND = "refund"
    WITHDRAWAL = "withdrawal"
    COMMISSION = "commission"
    PAYOUT = "payout"


# ── Delivery Status ───────────────────────────────────────────────────────────
class DeliveryStatus(str, enum.Enum):
    PENDING = "pending"          # Waiting for rider assignment
    ASSIGNED = "assigned"        # Rider assigned
    ACCEPTED = "accepted"        # Rider accepted delivery
    PICKING_UP = "picking_up"    # Rider heading to restaurant
    PICKED_UP = "picked_up"      # Rider has the order
    ON_THE_WAY = "on_the_way"    # En route to customer
    DELIVERED = "delivered"      # Delivered successfully
    FAILED = "failed"            # Delivery failed
    CANCELLED = "cancelled"      # Delivery cancelled


# ── Vehicle Type ─────────────────────────────────────────────────────────────
class VehicleType(str, enum.Enum):
    MOTORCYCLE = "motorcycle"
    BICYCLE = "bicycle"
    CAR = "car"
    VAN = "van"
    FOOT = "foot"


# ── Document Type ─────────────────────────────────────────────────────────────
class DocumentType(str, enum.Enum):
    # Restaurant documents
    BUSINESS_LICENSE = "business_license"
    TAX_CERTIFICATE = "tax_certificate"
    FOOD_SAFETY_CERT = "food_safety_certificate"
    HEALTH_CERTIFICATE = "health_certificate"
    # Rider documents
    DRIVERS_LICENSE = "drivers_license"
    NATIONAL_ID = "national_id"
    VEHICLE_INSURANCE = "vehicle_insurance"
    POLICE_CLEARANCE = "police_clearance"
    VEHICLE_IMAGE = "vehicle_image"


# ── Coupon Type ───────────────────────────────────────────────────────────────
class CouponType(str, enum.Enum):
    PERCENTAGE = "percentage"
    FIXED = "fixed"


# ── Review Target ─────────────────────────────────────────────────────────────
class ReviewTargetType(str, enum.Enum):
    RESTAURANT = "restaurant"
    FOOD = "food"
    RIDER = "rider"


# ── Notification Type ─────────────────────────────────────────────────────────
class NotificationType(str, enum.Enum):
    ORDER_PLACED = "order_placed"
    ORDER_ACCEPTED = "order_accepted"
    ORDER_REJECTED = "order_rejected"
    ORDER_PREPARING = "order_preparing"
    ORDER_READY = "order_ready"
    ORDER_PICKED_UP = "order_picked_up"
    ORDER_ON_THE_WAY = "order_on_the_way"
    ORDER_DELIVERED = "order_delivered"
    ORDER_CANCELLED = "order_cancelled"
    PAYMENT_RECEIVED = "payment_received"
    PAYMENT_FAILED = "payment_failed"
    REFUND_PROCESSED = "refund_processed"
    RIDER_ASSIGNED = "rider_assigned"
    ACCOUNT_VERIFIED = "account_verified"
    RESTAURANT_APPROVED = "restaurant_approved"
    RESTAURANT_SUSPENDED = "restaurant_suspended"
    WITHDRAWAL_APPROVED = "withdrawal_approved"
    WITHDRAWAL_REJECTED = "withdrawal_rejected"
    PROMOTION = "promotion"
    SYSTEM = "system"


# ── Notification Channel ─────────────────────────────────────────────────────
class NotificationChannel(str, enum.Enum):
    EMAIL = "email"
    SMS = "sms"
    PUSH = "push"
    IN_APP = "in_app"


# ── Support Ticket Status ─────────────────────────────────────────────────────
class TicketStatus(str, enum.Enum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    CLOSED = "closed"


# ── Dispute Status ────────────────────────────────────────────────────────────
class DisputeStatus(str, enum.Enum):
    OPEN = "open"
    UNDER_REVIEW = "under_review"
    RESOLVED = "resolved"
    ESCALATED = "escalated"


# ── Earnings Status ──────────────────────────────────────────────────────────
class EarningsStatus(str, enum.Enum):
    PENDING = "pending"
    AVAILABLE = "available"
    WITHDRAWN = "withdrawn"


# ── Day of Week ───────────────────────────────────────────────────────────────
class DayOfWeek(str, enum.Enum):
    MONDAY = "monday"
    TUESDAY = "tuesday"
    WEDNESDAY = "wednesday"
    THURSDAY = "thursday"
    FRIDAY = "friday"
    SATURDAY = "saturday"
    SUNDAY = "sunday"


# ── Cuisine Types ─────────────────────────────────────────────────────────────
CUISINE_TYPES = [
    "Sierra Leonean",
    "West African",
    "Chinese",
    "Indian",
    "Lebanese",
    "Italian",
    "American",
    "Fast Food",
    "Grills & BBQ",
    "Seafood",
    "Vegetarian",
    "Vegan",
    "Desserts & Pastries",
    "Beverages",
    "Pizza",
    "Burgers",
    "Rice Dishes",
    "Soups & Stews",
]

# ── File size limits ──────────────────────────────────────────────────────────
MAX_IMAGE_SIZE_BYTES = 10 * 1024 * 1024   # 10 MB
MAX_DOC_SIZE_BYTES = 20 * 1024 * 1024     # 20 MB

# ── Delivery fee tiers (SLL) ──────────────────────────────────────────────────
DELIVERY_FEE_TIERS = {
    3.0: 5000,    # 0–3 km: 5,000 SLL
    7.0: 10000,   # 3–7 km: 10,000 SLL
    15.0: 18000,  # 7–15 km: 18,000 SLL
    30.0: 30000,  # 15–30 km: 30,000 SLL
}

# ── OTP config ────────────────────────────────────────────────────────────────
OTP_LENGTH = 6
OTP_EXPIRE_MINUTES = 10
