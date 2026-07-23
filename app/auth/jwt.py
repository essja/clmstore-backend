"""
CLMStore — JWT Authentication
"""
from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from jose import JWTError, jwt

from app.config.settings import settings
from app.exceptions.custom import InvalidTokenException, TokenExpiredException


def create_access_token(
    data: Dict[str, Any],
    expires_delta: Optional[timedelta] = None,
) -> str:
    """Create a short-lived JWT access token."""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire, "type": "access"})
    return jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def create_refresh_token(data: Dict[str, Any]) -> str:
    """Create a long-lived JWT refresh token."""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire, "type": "refresh"})
    return jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def create_password_reset_token(user_id: int) -> str:
    """Create a password reset token valid for 2 hours."""
    expire = datetime.now(timezone.utc) + timedelta(
        hours=settings.PASSWORD_RESET_TOKEN_EXPIRE_HOURS
    )
    payload = {"sub": str(user_id), "exp": expire, "type": "password_reset"}
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def create_email_verify_token(user_id: int) -> str:
    """Create an email verification token valid for 24 hours."""
    expire = datetime.now(timezone.utc) + timedelta(
        hours=settings.EMAIL_VERIFY_TOKEN_EXPIRE_HOURS
    )
    payload = {"sub": str(user_id), "exp": expire, "type": "email_verify"}
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_token(token: str, expected_type: Optional[str] = None) -> Dict[str, Any]:
    """
    Decode and validate a JWT token.
    Raises TokenExpiredException or InvalidTokenException on failure.
    """
    try:
        payload = jwt.decode(
            token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM]
        )
        if expected_type and payload.get("type") != expected_type:
            raise InvalidTokenException()
        return payload
    except JWTError as e:
        if "expired" in str(e).lower():
            raise TokenExpiredException()
        raise InvalidTokenException()


def generate_otp() -> str:
    """Generate a 6-digit numeric OTP."""
    return str(secrets.randbelow(1_000_000)).zfill(6)


def generate_secure_token(length: int = 32) -> str:
    """Generate a cryptographically secure URL-safe token."""
    return secrets.token_urlsafe(length)
