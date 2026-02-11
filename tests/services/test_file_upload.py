"""Tests for FileUploadService."""

import io
import os
import time
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.claude_headspace.services.file_upload import FileUploadService


# ──────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────


@pytest.fixture
def upload_dir(tmp_path):
    """Provide a temporary upload directory."""
    d = tmp_path / "uploads"
    d.mkdir()
    return d


@pytest.fixture
def config():
    """Minimal file_upload config."""
    return {
        "file_upload": {
            "upload_dir": "uploads",
            "max_file_size_mb": 10,
            "max_total_storage_mb": 500,
            "retention_days": 7,
            "allowed_image_types": ["png", "jpg", "jpeg", "gif", "webp"],
            "allowed_document_types": ["pdf"],
            "allowed_text_types": ["txt", "md", "py", "js", "json"],
        }
    }


@pytest.fixture
def service(config, tmp_path):
    """Create a FileUploadService using a temp directory."""
    svc = FileUploadService(config=config, app_root=str(tmp_path))
    svc.ensure_upload_dir()
    return svc


def _make_file(content: bytes, name: str = "test.png"):
    """Create an in-memory file-like object."""
    f = io.BytesIO(content)
    f.name = name
    return f


# ──────────────────────────────────────────────────────────────
# File type validation tests
# ──────────────────────────────────────────────────────────────


class TestValidateFileExtension:
    def test_allowed_image_extension(self, service):
        result = service.validate_file("photo.png", 1000)
        assert result["valid"] is True

    def test_allowed_text_extension(self, service):
        result = service.validate_file("code.py", 1000)
        assert result["valid"] is True

    def test_allowed_document_extension(self, service):
        result = service.validate_file("doc.pdf", 1000)
        assert result["valid"] is True

    def test_rejected_extension(self, service):
        result = service.validate_file("malware.exe", 1000)
        assert result["valid"] is False
        assert "not allowed" in result["error"]

    def test_no_extension(self, service):
        result = service.validate_file("noextension", 1000)
        assert result["valid"] is False

    def test_empty_filename(self, service):
        result = service.validate_file("", 1000)
        assert result["valid"] is False

    def test_case_insensitive_extension(self, service):
        result = service.validate_file("PHOTO.PNG", 1000)
        assert result["valid"] is True

    def test_double_extension_uses_last(self, service):
        result = service.validate_file("file.tar.gz", 1000)
        assert result["valid"] is False  # .gz not in allowed


# ──────────────────────────────────────────────────────────────
# Magic bytes validation tests
# ──────────────────────────────────────────────────────────────


class TestMagicBytesValidation:
    def test_png_magic_match(self, service):
        png_header = b"\x89PNG\r\n\x1a\n" + b"\x00" * 8
        f = _make_file(png_header)
        result = service.validate_file("image.png", 16, f)
        assert result["valid"] is True

    def test_jpeg_magic_match(self, service):
        jpeg_header = b"\xff\xd8\xff" + b"\x00" * 13
        f = _make_file(jpeg_header)
        result = service.validate_file("photo.jpg", 16, f)
        assert result["valid"] is True

    def test_content_mismatch_png_ext_jpeg_content(self, service):
        # JPEG content with .png extension
        jpeg_header = b"\xff\xd8\xff" + b"\x00" * 13
        f = _make_file(jpeg_header)
        result = service.validate_file("fake.png", 16, f)
        assert result["valid"] is False
        assert "does not match" in result["error"]

    def test_text_files_skip_magic_check(self, service):
        # Text files don't undergo magic bytes validation
        f = _make_file(b"print('hello')")
        result = service.validate_file("code.py", 14, f)
        assert result["valid"] is True


# ──────────────────────────────────────────────────────────────
# File size validation tests
# ──────────────────────────────────────────────────────────────


class TestFileSizeValidation:
    def test_under_limit(self, service):
        result = service.validate_file("test.png", 1000)
        assert result["valid"] is True

    def test_at_limit(self, service):
        result = service.validate_file("test.png", 10 * 1024 * 1024)
        assert result["valid"] is True

    def test_over_limit(self, service):
        result = service.validate_file("test.png", 10 * 1024 * 1024 + 1)
        assert result["valid"] is False
        assert "too large" in result["error"].lower()


# ──────────────────────────────────────────────────────────────
# Storage quota validation tests
# ──────────────────────────────────────────────────────────────


class TestStorageQuota:
    def test_quota_exceeded(self, service):
        # Write a large file to fill quota
        big_file = service.upload_dir / "big.bin"
        big_file.write_bytes(b"\x00" * (500 * 1024 * 1024))

        result = service.validate_file("test.png", 1024)
        assert result["valid"] is False
        assert "quota" in result["error"].lower()


# ──────────────────────────────────────────────────────────────
# File save and retrieval tests
# ──────────────────────────────────────────────────────────────


class TestSaveFile:
    def test_save_returns_metadata(self, service):
        f = _make_file(b"test content", "test.txt")
        metadata = service.save_file(f, "test.txt")
        assert metadata["original_filename"] == "test.txt"
        assert metadata["stored_filename"].endswith(".txt")
        assert metadata["file_type"] == "text"
        assert metadata["file_size"] == 12
        assert metadata["serving_url"].startswith("/api/voice/uploads/")
        assert metadata["server_path"]

    def test_save_creates_file_on_disk(self, service):
        f = _make_file(b"hello world", "hello.txt")
        metadata = service.save_file(f, "hello.txt")
        stored_path = Path(metadata["server_path"])
        assert stored_path.exists()
        assert stored_path.read_bytes() == b"hello world"

    def test_unique_filenames(self, service):
        f1 = _make_file(b"a", "same.txt")
        f2 = _make_file(b"b", "same.txt")
        m1 = service.save_file(f1, "same.txt")
        m2 = service.save_file(f2, "same.txt")
        assert m1["stored_filename"] != m2["stored_filename"]

    def test_image_file_type(self, service):
        f = _make_file(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100, "photo.png")
        metadata = service.save_file(f, "photo.png")
        assert metadata["file_type"] == "image"
        assert metadata["mime_type"] == "image/png"

    def test_document_file_type(self, service):
        f = _make_file(b"%PDF-1.4" + b"\x00" * 100, "doc.pdf")
        metadata = service.save_file(f, "doc.pdf")
        assert metadata["file_type"] == "document"


# ──────────────────────────────────────────────────────────────
# URL and path helpers
# ──────────────────────────────────────────────────────────────


class TestUrlAndPath:
    def test_get_serving_url(self, service):
        url = service.get_serving_url("abc123.png")
        assert url == "/api/voice/uploads/abc123.png"

    def test_get_absolute_path(self, service):
        path = service.get_absolute_path("abc123.png")
        assert path.endswith("abc123.png")
        assert os.path.isabs(path)


# ──────────────────────────────────────────────────────────────
# Path traversal prevention
# ──────────────────────────────────────────────────────────────


class TestPathSafety:
    def test_safe_filename(self):
        assert FileUploadService.is_safe_filename("abc123.png") is True

    def test_rejects_path_separator(self):
        assert FileUploadService.is_safe_filename("../etc/passwd") is False

    def test_rejects_backslash(self):
        assert FileUploadService.is_safe_filename("..\\etc\\passwd") is False

    def test_rejects_dotdot(self):
        assert FileUploadService.is_safe_filename("..hidden") is False

    def test_rejects_null_bytes(self):
        assert FileUploadService.is_safe_filename("test\x00.png") is False

    def test_rejects_empty(self):
        assert FileUploadService.is_safe_filename("") is False


# ──────────────────────────────────────────────────────────────
# Cleanup tests
# ──────────────────────────────────────────────────────────────


class TestCleanup:
    def test_cleanup_expired_files(self, service):
        # Create a file and set its mtime to the past
        old_file = service.upload_dir / "old.txt"
        old_file.write_bytes(b"old")
        old_mtime = time.time() - (8 * 86400)  # 8 days ago
        os.utime(old_file, (old_mtime, old_mtime))

        # Create a recent file
        new_file = service.upload_dir / "new.txt"
        new_file.write_bytes(b"new")

        deleted = service.cleanup_expired()
        assert deleted == 1
        assert not old_file.exists()
        assert new_file.exists()

    def test_startup_sweep(self, service):
        # Create expired file
        old_file = service.upload_dir / "expired.txt"
        old_file.write_bytes(b"old")
        old_mtime = time.time() - (8 * 86400)
        os.utime(old_file, (old_mtime, old_mtime))

        service.startup_sweep()
        assert not old_file.exists()

    def test_cleanup_no_expired(self, service):
        new_file = service.upload_dir / "fresh.txt"
        new_file.write_bytes(b"fresh")
        deleted = service.cleanup_expired()
        assert deleted == 0
        assert new_file.exists()


# ──────────────────────────────────────────────────────────────
# Storage usage
# ──────────────────────────────────────────────────────────────


class TestStorageUsage:
    def test_empty_directory(self, service):
        assert service.get_storage_usage() == 0

    def test_with_files(self, service):
        (service.upload_dir / "a.txt").write_bytes(b"hello")  # 5 bytes
        (service.upload_dir / "b.txt").write_bytes(b"world!")  # 6 bytes
        usage = service.get_storage_usage()
        assert usage == 11
