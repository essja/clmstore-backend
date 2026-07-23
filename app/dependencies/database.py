"""
CLMStore — Database Dependency
"""
from __future__ import annotations

from app.database import get_db

# Expose for routers
__all__ = ["get_db"]
