"""
CLMStore — Response Formatters
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional


def success_response(
    data: Any = None,
    message: str = "Success",
    status_code: int = 200,
) -> Dict[str, Any]:
    return {
        "success": True,
        "message": message,
        "data": data,
    }


def error_response(
    message: str,
    errors: Optional[Any] = None,
    status_code: int = 400,
) -> Dict[str, Any]:
    return {
        "success": False,
        "message": message,
        "errors": errors,
    }


def format_currency(amount: float, currency: str = "SLL") -> str:
    """Format amount as currency string."""
    if currency == "SLL":
        return f"Le {amount:,.0f}"
    elif currency == "USD":
        return f"${amount:,.2f}"
    return f"{currency} {amount:,.2f}"


def format_datetime(dt: Optional[datetime]) -> Optional[str]:
    """Format datetime as ISO 8601 string."""
    if dt is None:
        return None
    return dt.isoformat()


def mask_phone(phone: str) -> str:
    """Mask middle digits of phone number for display."""
    if len(phone) < 8:
        return phone
    return phone[:4] + "****" + phone[-3:]


def mask_email(email: str) -> str:
    """Mask email for display: user@example.com → u***@example.com."""
    parts = email.split("@")
    if len(parts) != 2:
        return email
    user, domain = parts
    masked_user = user[0] + "***" if len(user) > 1 else "***"
    return f"{masked_user}@{domain}"
