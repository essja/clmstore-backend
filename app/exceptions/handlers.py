"""
CLMStore — Global Exception Handlers
"""
from __future__ import annotations

import traceback

import structlog
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError

from app.exceptions.custom import CLMStoreException

logger = structlog.get_logger()


def _error_body(message: str, errors=None, request_id: str = "") -> dict:
    body = {"success": False, "message": message}
    if errors is not None:
        body["errors"] = errors
    if request_id:
        body["request_id"] = request_id
    return body


def register_exception_handlers(app: FastAPI) -> None:
    """Register all global exception handlers on the FastAPI app."""

    @app.exception_handler(CLMStoreException)
    async def clmstore_exception_handler(
        request: Request, exc: CLMStoreException
    ) -> JSONResponse:
        request_id = request.headers.get("X-Request-ID", "")
        logger.warning(
            "clmstore_error",
            message=exc.message,
            status_code=exc.status_code,
            path=str(request.url),
            request_id=request_id,
        )
        return JSONResponse(
            status_code=exc.status_code,
            content=_error_body(exc.message, exc.errors, request_id),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        request_id = request.headers.get("X-Request-ID", "")
        errors = []
        for error in exc.errors():
            field = " → ".join(str(loc) for loc in error["loc"])
            errors.append({"field": field, "message": error["msg"], "type": error["type"]})
        logger.info("validation_error", errors=errors, path=str(request.url))
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=_error_body("Validation failed. Please check your input.", errors, request_id),
        )

    @app.exception_handler(IntegrityError)
    async def integrity_error_handler(
        request: Request, exc: IntegrityError
    ) -> JSONResponse:
        request_id = request.headers.get("X-Request-ID", "")
        logger.warning("db_integrity_error", error=str(exc.orig), path=str(request.url))
        message = "A record with these details already exists."
        if "unique" in str(exc.orig).lower():
            message = "Duplicate entry detected. This record already exists."
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content=_error_body(message, request_id=request_id),
        )

    @app.exception_handler(Exception)
    async def generic_exception_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:
        request_id = request.headers.get("X-Request-ID", "")
        logger.error(
            "unhandled_exception",
            error=str(exc),
            traceback=traceback.format_exc(),
            path=str(request.url),
            request_id=request_id,
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=_error_body(
                "An internal server error occurred. Our team has been notified.",
                request_id=request_id,
            ),
        )
