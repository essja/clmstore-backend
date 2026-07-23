"""
CLMStore — File Uploads Router
Centralized file upload endpoint supporting images and documents.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, File, Query, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies.auth import get_current_active_user
from app.models.user import User
from app.services.file_service import FileService

router = APIRouter()


# ── POST /api/v1/files/images ────────────────────────────────────────────────
@router.post(
    "/images",
    status_code=status.HTTP_201_CREATED,
    summary="Upload an image",
    description=(
        "Uploads an image (JPEG / PNG / WebP) to the configured storage backend "
        "(local disk or S3/MinIO). Max 10 MB. "
        "Returns the public URL of the uploaded file."
    ),
)
async def upload_image(
    file: UploadFile = File(...),
    folder: str = Query(default="general", description="Storage subfolder: profiles | restaurants/logos | restaurants/covers | menu | categories | reviews"),
    current_user: User = Depends(get_current_active_user),
) -> dict:
    """
    **Request:** multipart/form-data with `file` field.

    **Response:**
    ```json
    {
        "url": "http://localhost:9000/clmstore-media/menu/jollof-rice-1234.jpg",
        "file_name": "jollof-rice-1234.jpg",
        "content_type": "image/jpeg",
        "size_bytes": 204800
    }
    ```
    """
    service = FileService()
    result = await service.upload_image_with_metadata(file, folder=folder)
    return result


# ── POST /api/v1/files/documents ─────────────────────────────────────────────
@router.post(
    "/documents",
    status_code=status.HTTP_201_CREATED,
    summary="Upload a document",
    description=(
        "Uploads a document (PDF / JPEG / PNG) for business or rider verification. "
        "Max 20 MB. Returns the URL of the uploaded document."
    ),
)
async def upload_document(
    file: UploadFile = File(...),
    folder: str = Query(default="documents", description="Storage subfolder: restaurant_documents | rider_documents"),
    current_user: User = Depends(get_current_active_user),
) -> dict:
    """
    **Request:** multipart/form-data with `file` field.

    **Response:**
    ```json
    {
        "url": "http://localhost:9000/clmstore-media/rider_documents/license-5678.pdf",
        "file_name": "license-5678.pdf",
        "content_type": "application/pdf",
        "size_bytes": 512000
    }
    ```
    """
    service = FileService()
    result = await service.upload_document_with_metadata(file, folder=folder)
    return result
