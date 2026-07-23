"""
CLMStore — Application Settings
Loads configuration from environment variables / .env file
"""
from __future__ import annotations

from functools import lru_cache
from typing import List

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # ── Application ─────────────────────────────────────────────
    APP_NAME: str = "CLMStore"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    ENVIRONMENT: str = "development"
    SECRET_KEY: str = "change-me-in-production-min-32-characters!!"

    # ── Database ─────────────────────────────────────────────────
    DATABASE_URL: str = "postgresql+asyncpg://clmstore:password@localhost:5432/clmstore_db"
    DATABASE_ECHO: bool = False
    DATABASE_POOL_SIZE: int = 10
    DATABASE_MAX_OVERFLOW: int = 20

    # ── Redis ────────────────────────────────────────────────────
    REDIS_URL: str = "redis://localhost:6379/0"

    # ── JWT ──────────────────────────────────────────────────────
    JWT_SECRET_KEY: str = "jwt-secret-change-in-production-min-32-chars!"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    PASSWORD_RESET_TOKEN_EXPIRE_HOURS: int = 2
    EMAIL_VERIFY_TOKEN_EXPIRE_HOURS: int = 24

    # ── CORS ─────────────────────────────────────────────────────
    ALLOWED_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:8080"]

    @field_validator("ALLOWED_ORIGINS", mode="before")
    @classmethod
    def parse_origins(cls, v: str | List[str]) -> List[str]:
        if isinstance(v, str):
            import json
            try:
                return json.loads(v)
            except Exception:
                return [o.strip() for o in v.split(",")]
        return v

    # ── WhatsApp Business Cloud API ──────────────────────────────
    WHATSAPP_PHONE_NUMBER_ID: str = ""
    WHATSAPP_ACCESS_TOKEN: str = ""
    WHATSAPP_VERIFY_TOKEN: str = "clmstore_wa_secure_verify_token_2026"
    WHATSAPP_BUSINESS_ACCOUNT_ID: str = ""
    WHATSAPP_API_VERSION: str = "v21.0"

    # ── File Uploads ─────────────────────────────────────────────
    UPLOAD_DIR: str = "uploads"
    MAX_FILE_SIZE_MB: int = 10
    ALLOWED_IMAGE_TYPES: List[str] = ["image/jpeg", "image/png", "image/webp"]
    ALLOWED_DOC_TYPES: List[str] = ["application/pdf", "image/jpeg", "image/png"]

    # ── S3 / MinIO ───────────────────────────────────────────────
    USE_S3: bool = False
    S3_BUCKET: str = "clmstore-media"
    S3_ACCESS_KEY: str = "minioadmin"
    S3_SECRET_KEY: str = "minioadmin"
    S3_ENDPOINT_URL: str = "http://localhost:9000"
    S3_REGION: str = "us-east-1"
    CDN_BASE_URL: str = "http://localhost:9000/clmstore-media"

    # ── Email (SMTP) ─────────────────────────────────────────────
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_TLS: bool = True
    FROM_EMAIL: str = "noreply@clmstore.sl"
    FROM_NAME: str = "CLMStore"

    # ── SMS — Africa's Talking ───────────────────────────────────
    AT_API_KEY: str = ""
    AT_USERNAME: str = "sandbox"
    AT_SENDER_ID: str = "CLMStore"

    # ── OneSignal Push Notifications ─────────────────────────────
    ONESIGNAL_APP_ID: str = ""
    ONESIGNAL_REST_API_KEY: str = ""

    # ── Stripe ───────────────────────────────────────────────────
    STRIPE_SECRET_KEY: str = ""
    STRIPE_WEBHOOK_SECRET: str = ""

    # ── Orange Money ─────────────────────────────────────────────
    ORANGE_MONEY_API_KEY: str = ""
    ORANGE_MONEY_MERCHANT_ID: str = ""
    ORANGE_MONEY_BASE_URL: str = "https://api.orange.com/orange-money-webpay/sl/v1"

    # ── Afrimoney ────────────────────────────────────────────────
    AFRIMONEY_API_KEY: str = ""
    AFRIMONEY_BASE_URL: str = "https://api.afrimoney.sl/v1"

    # ── PayPal ───────────────────────────────────────────────────
    PAYPAL_CLIENT_ID: str = ""
    PAYPAL_CLIENT_SECRET: str = ""
    PAYPAL_MODE: str = "sandbox"  # "sandbox" | "live"

    # ── OAuth — Google ───────────────────────────────────────────
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    GOOGLE_REDIRECT_URI: str = "http://localhost:8000/api/v1/auth/oauth/google/callback"

    # ── OAuth — Facebook ─────────────────────────────────────────
    FACEBOOK_CLIENT_ID: str = ""
    FACEBOOK_CLIENT_SECRET: str = ""
    FACEBOOK_REDIRECT_URI: str = "http://localhost:8000/api/v1/auth/oauth/facebook/callback"

    # ── Location / Geocoding ─────────────────────────────────────
    NOMINATIM_USER_AGENT: str = "CLMStore/1.0 (contact@clmstore.sl)"
    GOOGLE_MAPS_API_KEY: str = ""
    DEFAULT_CITY: str = "Freetown"
    DEFAULT_COUNTRY: str = "Sierra Leone"

    # ── Anthropic AI ─────────────────────────────────────────────
    ANTHROPIC_API_KEY: str = ""

    # ── Business Rules ───────────────────────────────────────────
    # These are fallback defaults only. The live values are stored
    # in the system_settings DB table and edited by the super admin.
    COMMISSION_RATE: float = 0.15           # 15% platform commission
    SERVICE_FEE: float = 5000.0             # Le 5,000 flat service fee
    TAX_RATE: float = 0.08                  # 8% VAT (Sierra Leone) — internal accounting only
    DEFAULT_CURRENCY: str = "SLL"
    CURRENCY_SYMBOL: str = "Le"
    DEFAULT_DELIVERY_FEE: float = 10000.0   # Le 10,000 flat default delivery fee
    MIN_WITHDRAWAL_AMOUNT: float = 50000.0  # SLL
    MAX_DELIVERY_RADIUS_KM: float = 30.0

    # ── Rate Limiting ─────────────────────────────────────────────
    RATE_LIMIT_PER_MINUTE: int = 60
    RATE_LIMIT_AUTH_PER_MINUTE: int = 10

    # ── Frontend URLs ─────────────────────────────────────────────
    FRONTEND_URL: str = "http://localhost:3000"
    PASSWORD_RESET_URL: str = "http://localhost:3000/reset-password"
    EMAIL_VERIFY_URL: str = "http://localhost:3000/verify-email"

    # ── Pagination ───────────────────────────────────────────────
    DEFAULT_PAGE_SIZE: int = 20
    MAX_PAGE_SIZE: int = 100

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == "production"

    @property
    def is_development(self) -> bool:
        return self.ENVIRONMENT == "development"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings: Settings = get_settings()
