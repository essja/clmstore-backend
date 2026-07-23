"""
CLMStore — Custom Validators
"""
from __future__ import annotations

import re
from typing import Optional


# ── Phone Number ──────────────────────────────────────────────────────────────
SIERRA_LEONE_PHONE_RE = re.compile(r"^\+232[0-9]{8}$")
INTERNATIONAL_PHONE_RE = re.compile(r"^\+[1-9]\d{6,14}$")


def validate_phone(phone: str) -> str:
    """
    Validate and normalise a Sierra Leone phone number.
    Accepts: +23276123456, +23277123456, +23279123456, +23230123456, +23231123456
    """
    # Strip spaces/dashes
    clean = re.sub(r"[\s\-]", "", phone)
    # Normalise local format (076...) to international (+23276...)
    if re.match(r"^0[0-9]{8}$", clean):
        clean = "+232" + clean[1:]
    if not INTERNATIONAL_PHONE_RE.match(clean):
        raise ValueError(f"Invalid phone number: {phone}")
    return clean


def validate_password(password: str) -> str:
    """
    Enforce password policy:
    - Minimum 8 characters
    - At least one uppercase letter
    - At least one lowercase letter
    - At least one digit
    - At least one special character
    """
    if len(password) < 8:
        raise ValueError("Password must be at least 8 characters long.")
    if not re.search(r"[A-Z]", password):
        raise ValueError("Password must contain at least one uppercase letter.")
    if not re.search(r"[a-z]", password):
        raise ValueError("Password must contain at least one lowercase letter.")
    if not re.search(r"\d", password):
        raise ValueError("Password must contain at least one digit.")
    if not re.search(r"[!@#$%^&*()_+\-=\[\]{};':\"\\|,.<>\/?]", password):
        raise ValueError("Password must contain at least one special character.")
    return password


def validate_price(price: float) -> float:
    if price < 0:
        raise ValueError("Price cannot be negative.")
    if price > 10_000_000:  # 10 million SLL cap for a single item
        raise ValueError("Price exceeds maximum allowed value.")
    return round(price, 2)


def validate_rating(rating: float) -> float:
    if not (1.0 <= rating <= 5.0):
        raise ValueError("Rating must be between 1 and 5.")
    return round(rating, 1)


def validate_latitude(lat: float) -> float:
    if not (-90.0 <= lat <= 90.0):
        raise ValueError("Latitude must be between -90 and 90.")
    return lat


def validate_longitude(lon: float) -> float:
    if not (-180.0 <= lon <= 180.0):
        raise ValueError("Longitude must be between -180 and 180.")
    return lon


def sanitise_string(value: Optional[str]) -> Optional[str]:
    """Strip leading/trailing whitespace and normalise internal whitespace."""
    if value is None:
        return None
    return " ".join(value.split())


def validate_coupon_code(code: str) -> str:
    """Coupon codes: 4–20 alphanumeric uppercase characters."""
    code = code.upper().strip()
    if not re.match(r"^[A-Z0-9]{4,20}$", code):
        raise ValueError("Coupon code must be 4–20 uppercase alphanumeric characters.")
    return code
