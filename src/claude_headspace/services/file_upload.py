"""File upload service for voice bridge file/image sharing."""

import logging
import os
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Magic bytes signatures for common file types
MAGIC_SIGNATURES = {
    b"\x89PNG\r\n\x1a\n": "image/png",
    b"\xff\xd8\xff": "image/jpeg",
    b"GIF87a": "image/gif",
    b"GIF89a": "image/gif",
    b"RIFF": "image/webp",  # WebP starts with RIFF....WEBP
    b"%PDF": "application/pdf",
}

# Extension to MIME type mapping
EXTENSION_MIME_MAP = {
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "gif": "image/gif",
    "webp": "image/webp",
    "pdf": "application/pdf",
    "txt": "text/plain",
    "md": "text/markdown",
    "py": "text/x-python",
    "js": "text/javascript",
    "ts": "text/typescript",
    "json": "application/json",
    "yaml": "text/yaml",
    "yml": "text/yaml",
    "html": "text/html",
    "css": "text/css",
    "rb": "text/x-ruby",
    "sh": "text/x-shellscript",
    "sql": "text/x-sql",
    "csv": "text/csv",
    "log": "text/plain",
}

IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}


class FileUploadService:
    """Handles file upload validation, storage, serving, and cleanup."""

    def __init__(self, config: dict, app_root: str):
        fu_config = config.get("file_upload", {})
        self.upload_dir_name = fu_config.get("upload_dir", "uploads")
        self.upload_dir = Path(app_root) / self.upload_dir_name
        self.max_file_size = fu_config.get("max_file_size_mb", 10) * 1024 * 1024
        self.max_total_storage = fu_config.get("max_total_storage_mb", 500) * 1024 * 1024
        self.retention_days = fu_config.get("retention_days", 7)
        self.allowed_image_types = set(fu_config.get("allowed_image_types", ["png", "jpg", "jpeg", "gif", "webp"]))
        self.allowed_document_types = set(fu_config.get("allowed_document_types", ["pdf"]))
        self.allowed_text_types = set(fu_config.get("allowed_text_types", [
            "txt", "md", "py", "js", "ts", "json", "yaml", "yml",
            "html", "css", "rb", "sh", "sql", "csv", "log",
        ]))
        self.all_allowed_extensions = self.allowed_image_types | self.allowed_document_types | self.allowed_text_types

    def ensure_upload_dir(self) -> None:
        """Create upload directory if it doesn't exist."""
        self.upload_dir.mkdir(parents=True, exist_ok=True)

    def validate_file(self, filename: str, file_size: int, file_obj: Any = None) -> dict:
        """Validate file type, size, and storage quota.

        Returns:
            dict with 'valid' (bool) and 'error' (str, if invalid)
        """
        # Extract and check extension
        ext = self._get_extension(filename)
        if not ext or ext not in self.all_allowed_extensions:
            allowed_list = ", ".join(sorted(self.all_allowed_extensions))
            return {"valid": False, "error": f"File type '.{ext}' is not allowed. Accepted: {allowed_list}"}

        # Check file size
        if file_size > self.max_file_size:
            max_mb = self.max_file_size / (1024 * 1024)
            return {"valid": False, "error": f"File too large ({file_size / (1024 * 1024):.1f}MB). Maximum: {max_mb:.0f}MB"}

        # Check magic bytes for image and PDF files (content inspection)
        if file_obj and ext in (self.allowed_image_types | self.allowed_document_types):
            detected_mime = self._detect_mime_from_content(file_obj)
            expected_mime = EXTENSION_MIME_MAP.get(ext)
            if detected_mime and expected_mime and detected_mime != expected_mime:
                return {
                    "valid": False,
                    "error": f"File content does not match extension '.{ext}' (detected: {detected_mime})",
                }

        # Check storage quota
        current_usage = self.get_storage_usage()
        if current_usage + file_size > self.max_total_storage:
            return {"valid": False, "error": "Storage quota exceeded. Please wait for old files to be cleaned up."}

        return {"valid": True}

    def save_file(self, file_obj: Any, original_filename: str) -> dict:
        """Save uploaded file with unique name.

        Args:
            file_obj: File-like object with read() and seek()
            original_filename: Original filename from the upload

        Returns:
            dict with file metadata
        """
        self.ensure_upload_dir()

        ext = self._get_extension(original_filename) or "bin"
        stored_filename = f"{uuid.uuid4().hex}.{ext}"
        stored_path = self.upload_dir / stored_filename

        # Save file
        file_obj.seek(0)
        data = file_obj.read()
        stored_path.write_bytes(data)

        file_size = len(data)
        mime_type = EXTENSION_MIME_MAP.get(ext, "application/octet-stream")
        is_image = ext in IMAGE_EXTENSIONS

        metadata = {
            "original_filename": original_filename,
            "stored_filename": stored_filename,
            "file_type": "image" if is_image else "document" if ext in self.allowed_document_types else "text",
            "mime_type": mime_type,
            "file_size": file_size,
            "server_path": str(stored_path.resolve()),
            "serving_url": f"/api/voice/uploads/{stored_filename}",
        }

        logger.info(
            f"File saved: {original_filename} -> {stored_filename} "
            f"({file_size} bytes, {mime_type})"
        )
        return metadata

    def get_serving_url(self, stored_filename: str) -> str:
        """Build URL for the file serving endpoint."""
        return f"/api/voice/uploads/{stored_filename}"

    def get_absolute_path(self, stored_filename: str) -> str:
        """Return absolute disk path for tmux delivery."""
        return str((self.upload_dir / stored_filename).resolve())

    def get_storage_usage(self) -> int:
        """Calculate total bytes used in upload directory."""
        if not self.upload_dir.exists():
            return 0
        total = 0
        for f in self.upload_dir.iterdir():
            if f.is_file():
                total += f.stat().st_size
        return total

    def cleanup_expired(self) -> int:
        """Delete files older than retention period.

        Returns:
            Number of files deleted.
        """
        if not self.upload_dir.exists():
            return 0

        cutoff = time.time() - (self.retention_days * 86400)
        deleted = 0
        for f in self.upload_dir.iterdir():
            if f.is_file():
                try:
                    if f.stat().st_mtime < cutoff:
                        f.unlink()
                        deleted += 1
                        logger.debug(f"Cleaned up expired upload: {f.name}")
                except OSError as e:
                    logger.warning(f"Failed to delete expired upload {f.name}: {e}")
        if deleted:
            logger.info(f"Cleaned up {deleted} expired upload(s)")
        return deleted

    def startup_sweep(self) -> None:
        """Run cleanup on app startup."""
        self.ensure_upload_dir()
        deleted = self.cleanup_expired()
        usage = self.get_storage_usage()
        usage_mb = usage / (1024 * 1024)
        logger.info(
            f"File upload startup sweep: {deleted} expired file(s) removed, "
            f"{usage_mb:.1f}MB in use"
        )

    def _get_extension(self, filename: str) -> str | None:
        """Extract lowercase file extension."""
        if not filename or "." not in filename:
            return None
        ext = filename.rsplit(".", 1)[-1].lower()
        return ext if ext else None

    def _detect_mime_from_content(self, file_obj: Any) -> str | None:
        """Detect MIME type from file content via magic bytes."""
        try:
            pos = file_obj.tell()
            header = file_obj.read(16)
            file_obj.seek(pos)
        except (OSError, AttributeError):
            return None

        if not header:
            return None

        for signature, mime_type in MAGIC_SIGNATURES.items():
            if header.startswith(signature):
                # Special case: WebP needs RIFF....WEBP check
                if signature == b"RIFF" and len(header) >= 12:
                    if header[8:12] != b"WEBP":
                        continue
                return mime_type

        return None

    @staticmethod
    def is_safe_filename(filename: str) -> bool:
        """Check if filename is safe (no path traversal)."""
        if not filename:
            return False
        if "/" in filename or "\\" in filename:
            return False
        if ".." in filename:
            return False
        if "\x00" in filename:
            return False
        return True
