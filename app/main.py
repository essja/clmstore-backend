"""
CLMStore — FastAPI Application Entry Point
"""
from __future__ import annotations

import time
from contextlib import asynccontextmanager
from typing import AsyncIterator

import os

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address

from app.config.settings import settings
from app.database import close_db, init_db
from app.exceptions.handlers import register_exception_handlers
from app.middleware.logging import StructuredLoggingMiddleware
from app.middleware.request_id import RequestIDMiddleware

# ── Router imports ────────────────────────────────────────────────────────────
from app.routers import (
    auth,
    users,
    restaurants,
    menu,
    cart,
    orders,
    payments,
    delivery,
    riders,
    reviews,
    coupons,
    notifications,
    location,
    files,
    admin,
    super_admin,
    search,
    whatsapp,
)
from app.routers import websocket as ws_router
from app.routers import ai_menu

logger = structlog.get_logger()

# ── Rate Limiter ──────────────────────────────────────────────────────────────
limiter = Limiter(key_func=get_remote_address, default_limits=[f"{settings.RATE_LIMIT_PER_MINUTE}/minute"])


# ── Lifespan ──────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    logger.info("clmstore_startup", version=settings.APP_VERSION, env=settings.ENVIRONMENT)
    yield
    await close_db()
    logger.info("clmstore_shutdown")


# ── App Factory ───────────────────────────────────────────────────────────────
def create_app() -> FastAPI:
    app = FastAPI(
        title="CLMStore API",
        description=(
            "CLMStore — A production-ready food delivery marketplace API for Sierra Leone. "
            "Similar to Uber Eats, Glovo, and DoorDash but built for the local market."
        ),
        version=settings.APP_VERSION,
        docs_url="/api/v1/docs",
        redoc_url="/api/v1/redoc",
        openapi_url="/api/v1/openapi.json",
        lifespan=lifespan,
        contact={
            "name": "CLMStore Tech Team",
            "email": "tech@clmstore.sl",
            "url": "https://clmstore.sl",
        },
        license_info={
            "name": "Proprietary",
            "url": "https://clmstore.sl/terms",
        },
    )

    # ── Rate Limiter ──────────────────────────────────────────────────────────
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.add_middleware(SlowAPIMiddleware)

    # ── CORS ──────────────────────────────────────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID", "X-RateLimit-Limit", "X-RateLimit-Remaining"],
    )

    # ── Compression ───────────────────────────────────────────────────────────
    app.add_middleware(GZipMiddleware, minimum_size=1000)

    # ── Custom Middleware ─────────────────────────────────────────────────────
    app.add_middleware(RequestIDMiddleware)
    app.add_middleware(StructuredLoggingMiddleware)

    # ── Exception Handlers ────────────────────────────────────────────────────
    register_exception_handlers(app)

    # ── API v1 Routers ────────────────────────────────────────────────────────
    prefix = "/api/v1"

    app.include_router(auth.router,          prefix=f"{prefix}/auth",          tags=["Authentication"])
    app.include_router(users.router,         prefix=f"{prefix}/users",         tags=["Users"])
    app.include_router(restaurants.router,   prefix=f"{prefix}/restaurants",   tags=["Restaurants"])
    app.include_router(menu.router,          prefix=f"{prefix}/restaurants",   tags=["Menu"])
    app.include_router(cart.router,          prefix=f"{prefix}/cart",          tags=["Cart"])
    app.include_router(orders.router,        prefix=f"{prefix}/orders",        tags=["Orders"])
    app.include_router(payments.router,      prefix=f"{prefix}/payments",      tags=["Payments"])
    app.include_router(delivery.router,      prefix=f"{prefix}/deliveries",    tags=["Deliveries"])
    app.include_router(riders.router,        prefix=f"{prefix}/riders",        tags=["Riders"])
    app.include_router(reviews.router,       prefix=f"{prefix}/reviews",       tags=["Reviews"])
    app.include_router(coupons.router,       prefix=f"{prefix}/coupons",       tags=["Coupons"])
    app.include_router(notifications.router, prefix=f"{prefix}/notifications", tags=["Notifications"])
    app.include_router(location.router,      prefix=f"{prefix}/location",      tags=["Location"])
    app.include_router(files.router,         prefix=f"{prefix}/files",         tags=["File Uploads"])
    app.include_router(admin.router,         prefix=f"{prefix}/admin",         tags=["Admin"])
    app.include_router(super_admin.router,   prefix=f"{prefix}/super-admin",   tags=["Super Admin"])
    app.include_router(search.router,        prefix=f"{prefix}/search",        tags=["Search"])
    app.include_router(whatsapp.router,      prefix=f"{prefix}/whatsapp",      tags=["WhatsApp Bot"])
    app.include_router(ws_router.router,     prefix=f"{prefix}/ws",            tags=["WebSocket"])
    app.include_router(ai_menu.router,       prefix=f"{prefix}/menu",          tags=["AI Menu"])

    # ── Static Files (uploads: PDFs, images) ────────────────────────────────
    upload_dir = os.path.abspath(settings.UPLOAD_DIR)
    os.makedirs(upload_dir, exist_ok=True)
    app.mount("/static/uploads", StaticFiles(directory=upload_dir), name="uploads")

    # ── Health Check ──────────────────────────────────────────────────────────
    @app.get("/api/v1/health", tags=["Health"], summary="API Health Check")
    async def health_check(request: Request) -> JSONResponse:
        from sqlalchemy import text as sa_text
        from app.database import AsyncSessionLocal
        db_status = "connected"
        try:
            async with AsyncSessionLocal() as session:
                await session.execute(sa_text("SELECT 1"))
        except Exception:
            db_status = "disconnected"

        healthy = db_status == "connected"
        return JSONResponse(
            status_code=200 if healthy else 503,
            content={
                "success": healthy,
                "status": "healthy" if healthy else "unhealthy",
                "version": settings.APP_VERSION,
                "environment": settings.ENVIRONMENT,
                "service": "CLMStore API",
                "database": db_status,
            },
        )

    @app.get("/", tags=["Health"], include_in_schema=False)
    async def root() -> JSONResponse:
        return JSONResponse(
            content={
                "message": "Welcome to CLMStore API",
                "docs": "/api/v1/docs",
                "version": settings.APP_VERSION,
            }
        )

    return app


app = create_app()
