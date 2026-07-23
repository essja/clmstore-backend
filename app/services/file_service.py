"""
CLMStore — File Upload Service
Supports local disk storage (dev) and S3-compatible cloud storage (prod).
"""
from __future__ import annotations

import os
import uuid
from typing import BinaryIO, Optional

import aiofiles
import boto3
from botocore.exceptions import ClientError
import structlog
from fastapi import UploadFile

from app.config.settings import settings
from app.exceptions.custom import FileUploadException

logger = structlog.get_logger()


class FileService:
    def __init__(self) -> None:
        self.use_s3 = settings.USE_S3
        if self.use_s3:
            self.s3_client = boto3.client(
                "s3",
                aws_access_key_id=settings.S3_ACCESS_KEY,
                aws_secret_access_key=settings.S3_SECRET_KEY,
                endpoint_url=settings.S3_ENDPOINT_URL,
                region_name=settings.S3_REGION,
            )
            self.bucket_name = settings.S3_BUCKET

    async def upload_file(
        self,
        file: UploadFile,
        folder: str = "general",
        custom_filename: Optional[str] = None,
    ) -> str:
        """
        Uploads file to storage.
        Returns the public URL of the uploaded file.
        """
        # Validate file size
        file.file.seek(0, os.SEEK_END)
        size_bytes = file.file.tell()
        file.file.seek(0)

        max_size = settings.MAX_FILE_SIZE_MB * 1024 * 1024
        if size_bytes > max_size:
            raise FileUploadException(
                f"File size exceeds the limit of {settings.MAX_FILE_SIZE_MB}MB"
            )

        # Generate unique filename if not provided
        ext = os.path.splitext(file.filename or "")[1]
        filename = custom_filename or f"{uuid.uuid4()}{ext}"
        storage_path = f"{folder}/{filename}"

        if self.use_s3:
            return await self._upload_to_s3(file, storage_path)
        else:
            return await self._upload_to_local(file, storage_path)

    async def _upload_to_local(self, file: UploadFile, storage_path: str) -> str:
        """Saves file to local uploads directory."""
        local_path = os.path.join(settings.UPLOAD_DIR, storage_path)
        os.makedirs(os.path.dirname(local_path), exist_ok=True)

        try:
            async with aiofiles.open(local_path, "wb") as f:
                while content := await file.read(1024 * 1024):  # read in 1MB chunks
                    await f.write(content)
            # Return relative or full local URL path
            return f"/static/uploads/{storage_path}"
        except Exception as e:
            logger.error("local_upload_failed", error=str(e))
            raise FileUploadException("Failed to save file locally")

    async def _upload_to_s3(self, file: UploadFile, storage_path: str) -> str:
        """Uploads file to S3-compatible storage."""
        try:
            content_type = file.content_type or "binary/octet-stream"
            # Read all file contents
            contents = await file.read()
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=storage_path,
                Body=contents,
                ContentType=content_type,
                ACL="public-read",  # assumes public buckets
            )
            # Construct URL
            return f"{settings.CDN_BASE_URL}/{storage_path}"
        except ClientError as e:
            logger.error("s3_upload_failed", error=str(e))
            raise FileUploadException("Failed to upload file to cloud storage")
        except Exception as e:
            logger.error("s3_upload_failed_generic", error=str(e))
            raise FileUploadException("Cloud storage upload error")

    async def upload_image(self, file: UploadFile, folder: str = "general") -> str:
        return await self.upload_file(file, folder=folder)

    async def upload_document(self, file: UploadFile, folder: str = "documents") -> str:
        return await self.upload_file(file, folder=folder)

    async def upload_image_with_metadata(self, file: UploadFile, folder: str = "general") -> dict:
        import os
        file.file.seek(0, os.SEEK_END)
        size_bytes = file.file.tell()
        file.file.seek(0)
        url = await self.upload_file(file, folder=folder)
        return {
            "url": url,
            "file_name": file.filename,
            "content_type": file.content_type,
            "size_bytes": size_bytes,
        }

    async def upload_document_with_metadata(self, file: UploadFile, folder: str = "documents") -> dict:
        return await self.upload_image_with_metadata(file, folder=folder)

    async def delete_file(self, file_url: str) -> None:
        """Deletes file from storage."""
        if not file_url:
            return

        if self.use_s3:
            # Extract key from S3 URL
            if settings.CDN_BASE_URL in file_url:
                key = file_url.replace(f"{settings.CDN_BASE_URL}/", "")
                try:
                    self.s3_client.delete_object(Bucket=self.bucket_name, Key=key)
                except ClientError as e:
                    logger.error("s3_delete_failed", error=str(e), key=key)
        else:
            # Extract local path from static URL
            if "/static/uploads/" in file_url:
                rel_path = file_url.replace("/static/uploads/", "")
                local_path = os.path.join(settings.UPLOAD_DIR, rel_path)
                if os.path.exists(local_path):
                    try:
                        os.remove(local_path)
                    except Exception as e:
                        logger.error("local_delete_failed", error=str(e), path=local_path)
