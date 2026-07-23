"""
CLMStore — Custom Exception Classes
"""
from __future__ import annotations

from typing import Any, Dict, Optional


class CLMStoreException(Exception):
    """Base exception for all CLMStore errors."""

    def __init__(
        self,
        message: str,
        status_code: int = 400,
        errors: Optional[Any] = None,
    ) -> None:
        self.message = message
        self.status_code = status_code
        self.errors = errors
        super().__init__(message)


class NotFoundException(CLMStoreException):
    """Resource not found."""
    def __init__(self, resource: str = "Resource", resource_id: Any = None) -> None:
        msg = f"{resource} not found" if resource_id is None else f"{resource} with id '{resource_id}' not found"
        super().__init__(msg, status_code=404)


class UnauthorizedException(CLMStoreException):
    """Authentication required."""
    def __init__(self, message: str = "Authentication required") -> None:
        super().__init__(message, status_code=401)


class ForbiddenException(CLMStoreException):
    """Insufficient permissions."""
    def __init__(self, message: str = "You do not have permission to perform this action") -> None:
        super().__init__(message, status_code=403)


class ConflictException(CLMStoreException):
    """Resource already exists / conflict."""
    def __init__(self, message: str = "Resource already exists") -> None:
        super().__init__(message, status_code=409)


class ValidationException(CLMStoreException):
    """Input validation failure."""
    def __init__(self, message: str, errors: Optional[Any] = None) -> None:
        super().__init__(message, status_code=422, errors=errors)


class BusinessRuleException(CLMStoreException):
    """Business rule violation."""
    def __init__(self, message: str) -> None:
        super().__init__(message, status_code=400)


class PaymentException(CLMStoreException):
    """Payment processing error."""
    def __init__(self, message: str, provider_error: Optional[str] = None) -> None:
        super().__init__(message, status_code=402, errors={"provider_error": provider_error})


class FileUploadException(CLMStoreException):
    """File upload error."""
    def __init__(self, message: str) -> None:
        super().__init__(message, status_code=400)


class RateLimitException(CLMStoreException):
    """Rate limit exceeded."""
    def __init__(self) -> None:
        super().__init__("Too many requests. Please slow down.", status_code=429)


class ServiceUnavailableException(CLMStoreException):
    """External service unavailable."""
    def __init__(self, service: str = "Service") -> None:
        super().__init__(f"{service} is currently unavailable.", status_code=503)


class TokenExpiredException(UnauthorizedException):
    def __init__(self) -> None:
        super().__init__("Token has expired.")


class InvalidTokenException(UnauthorizedException):
    def __init__(self) -> None:
        super().__init__("Invalid or malformed token.")


class OrderStateException(BusinessRuleException):
    """Invalid order state transition."""
    def __init__(self, current: str, attempted: str) -> None:
        super().__init__(f"Cannot transition order from '{current}' to '{attempted}'.")
