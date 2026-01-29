"""Tests for waypoint editor service."""

import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

from claude_headspace.services.waypoint_editor import (
    DEFAULT_TEMPLATE,
    SaveResult,
    WaypointResult,
    get_archive_dir,
    get_archive_filename,
    get_waypoint_path,
    load_waypoint,
    save_waypoint,
    validate_project_path,
)


class TestGetWaypointPath:
    """Tests for get_waypoint_path function."""

    def test_returns_correct_path(self):
        """Should return path to waypoint.md."""
        path = get_waypoint_path("/projects/myapp")
        assert path == Path("/projects/myapp/docs/brain_reboot/waypoint.md")

    def test_handles_path_object(self):
        """Should handle Path objects."""
        path = get_waypoint_path(Path("/projects/myapp"))
        assert path == Path("/projects/myapp/docs/brain_reboot/waypoint.md")


class TestGetArchiveDir:
    """Tests for get_archive_dir function."""

    def test_returns_correct_path(self):
        """Should return path to archive directory."""
        path = get_archive_dir("/projects/myapp")
        assert path == Path("/projects/myapp/docs/brain_reboot/archive")


class TestLoadWaypoint:
    """Tests for load_waypoint function."""

    def test_returns_template_when_file_missing(self):
        """Should return default template when waypoint doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = load_waypoint(tmpdir)

            assert isinstance(result, WaypointResult)
            assert result.exists is False
            assert result.template is True
            assert result.content == DEFAULT_TEMPLATE
            assert result.last_modified is None

    def test_returns_content_when_file_exists(self):
        """Should return file content when waypoint exists."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create waypoint file
            waypoint_dir = Path(tmpdir) / "docs" / "brain_reboot"
            waypoint_dir.mkdir(parents=True)
            waypoint_file = waypoint_dir / "waypoint.md"
            waypoint_file.write_text("# My Waypoint")

            result = load_waypoint(tmpdir)

            assert result.exists is True
            assert result.template is False
            assert result.content == "# My Waypoint"
            assert result.last_modified is not None

    def test_includes_modification_time(self):
        """Should include last modification time."""
        with tempfile.TemporaryDirectory() as tmpdir:
            waypoint_dir = Path(tmpdir) / "docs" / "brain_reboot"
            waypoint_dir.mkdir(parents=True)
            waypoint_file = waypoint_dir / "waypoint.md"
            waypoint_file.write_text("# Test")

            result = load_waypoint(tmpdir)

            assert result.last_modified is not None
            assert isinstance(result.last_modified, datetime)
            assert result.last_modified.tzinfo is not None

    def test_includes_file_path(self):
        """Should include the waypoint file path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = load_waypoint(tmpdir)

            assert "waypoint.md" in result.path
            assert "brain_reboot" in result.path


class TestGetArchiveFilename:
    """Tests for get_archive_filename function."""

    def test_returns_date_based_filename(self):
        """Should return filename with date."""
        with tempfile.TemporaryDirectory() as tmpdir:
            archive_dir = Path(tmpdir)
            date = datetime(2026, 1, 29, tzinfo=timezone.utc)

            filename = get_archive_filename(archive_dir, date)

            assert filename == "waypoint_2026-01-29.md"

    def test_adds_counter_when_file_exists(self):
        """Should add counter when file already exists."""
        with tempfile.TemporaryDirectory() as tmpdir:
            archive_dir = Path(tmpdir)
            (archive_dir / "waypoint_2026-01-29.md").write_text("old")
            date = datetime(2026, 1, 29, tzinfo=timezone.utc)

            filename = get_archive_filename(archive_dir, date)

            assert filename == "waypoint_2026-01-29_2.md"

    def test_increments_counter(self):
        """Should increment counter for multiple files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            archive_dir = Path(tmpdir)
            (archive_dir / "waypoint_2026-01-29.md").write_text("old1")
            (archive_dir / "waypoint_2026-01-29_2.md").write_text("old2")
            date = datetime(2026, 1, 29, tzinfo=timezone.utc)

            filename = get_archive_filename(archive_dir, date)

            assert filename == "waypoint_2026-01-29_3.md"


class TestSaveWaypoint:
    """Tests for save_waypoint function."""

    def test_saves_new_waypoint(self):
        """Should save waypoint when none exists."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = save_waypoint(tmpdir, "# New Waypoint")

            assert result.success is True
            assert result.archived is False  # No archive for new file
            assert result.error is None

            # Verify file was created
            waypoint_path = get_waypoint_path(tmpdir)
            assert waypoint_path.exists()
            assert waypoint_path.read_text() == "# New Waypoint"

    def test_archives_existing_waypoint(self):
        """Should archive existing waypoint before save."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create existing waypoint
            waypoint_dir = Path(tmpdir) / "docs" / "brain_reboot"
            waypoint_dir.mkdir(parents=True)
            waypoint_file = waypoint_dir / "waypoint.md"
            waypoint_file.write_text("# Old Content")

            result = save_waypoint(tmpdir, "# New Content")

            assert result.success is True
            assert result.archived is True
            assert result.archive_path is not None
            assert "archive" in result.archive_path

            # Verify archive was created
            archive_dir = get_archive_dir(tmpdir)
            archive_files = list(archive_dir.glob("waypoint_*.md"))
            assert len(archive_files) == 1
            assert archive_files[0].read_text() == "# Old Content"

            # Verify new content was saved
            assert waypoint_file.read_text() == "# New Content"

    def test_creates_directory_structure(self):
        """Should create directories if missing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = save_waypoint(tmpdir, "# Waypoint")

            assert result.success is True

            # Verify directories were created
            waypoint_path = get_waypoint_path(tmpdir)
            assert waypoint_path.parent.exists()

            archive_dir = get_archive_dir(tmpdir)
            assert archive_dir.exists()

    def test_returns_last_modified(self):
        """Should return last modification time after save."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = save_waypoint(tmpdir, "# Waypoint")

            assert result.last_modified is not None
            assert isinstance(result.last_modified, datetime)

    def test_conflict_detection(self):
        """Should detect conflict when mtime doesn't match."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create existing waypoint
            waypoint_dir = Path(tmpdir) / "docs" / "brain_reboot"
            waypoint_dir.mkdir(parents=True)
            waypoint_file = waypoint_dir / "waypoint.md"
            waypoint_file.write_text("# Original")

            # Get current mtime
            current_mtime = datetime.fromtimestamp(
                waypoint_file.stat().st_mtime, tz=timezone.utc
            )

            # Use an older expected mtime to simulate external modification
            old_mtime = datetime(2020, 1, 1, tzinfo=timezone.utc)

            result = save_waypoint(tmpdir, "# New Content", expected_mtime=old_mtime)

            assert result.success is False
            assert result.error == "conflict"

            # Verify file was NOT modified
            assert waypoint_file.read_text() == "# Original"

    def test_no_conflict_when_mtime_matches(self):
        """Should save when mtime matches expected."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create existing waypoint
            waypoint_dir = Path(tmpdir) / "docs" / "brain_reboot"
            waypoint_dir.mkdir(parents=True)
            waypoint_file = waypoint_dir / "waypoint.md"
            waypoint_file.write_text("# Original")

            # Get current mtime
            current_mtime = datetime.fromtimestamp(
                waypoint_file.stat().st_mtime, tz=timezone.utc
            )

            result = save_waypoint(tmpdir, "# New Content", expected_mtime=current_mtime)

            assert result.success is True
            assert waypoint_file.read_text() == "# New Content"

    def test_returns_error_on_permission_denied(self):
        """Should return error on permission denied."""
        # Use a path that definitely can't be written
        result = save_waypoint("/root/definitely_not_writable", "# Content")

        assert result.success is False
        assert result.error is not None


class TestValidateProjectPath:
    """Tests for validate_project_path function."""

    def test_valid_path_returns_true(self):
        """Should return True for valid path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            valid, error = validate_project_path(tmpdir)

            assert valid is True
            assert error is None

    def test_nonexistent_path_returns_false(self):
        """Should return False for nonexistent path."""
        valid, error = validate_project_path("/nonexistent/path/12345")

        assert valid is False
        assert "does not exist" in error

    def test_file_path_returns_false(self):
        """Should return False for file instead of directory."""
        with tempfile.NamedTemporaryFile() as f:
            valid, error = validate_project_path(f.name)

            assert valid is False
            assert "not a directory" in error


class TestDefaultTemplate:
    """Tests for default waypoint template."""

    def test_template_has_required_sections(self):
        """Should have all required sections."""
        assert "# Waypoint" in DEFAULT_TEMPLATE
        assert "## Next Up" in DEFAULT_TEMPLATE
        assert "## Upcoming" in DEFAULT_TEMPLATE
        assert "## Later" in DEFAULT_TEMPLATE
        assert "## Not Now" in DEFAULT_TEMPLATE

    def test_template_has_placeholders(self):
        """Should have placeholder comments."""
        assert "<!-- Immediate next steps -->" in DEFAULT_TEMPLATE
        assert "<!-- Coming soon -->" in DEFAULT_TEMPLATE
        assert "<!-- Future work -->" in DEFAULT_TEMPLATE
        assert "<!-- Parked/deprioritised -->" in DEFAULT_TEMPLATE


class TestAtomicWrite:
    """Tests for atomic write behavior."""

    def test_write_is_atomic(self):
        """Should use atomic write (temp file then rename)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create initial waypoint
            waypoint_dir = Path(tmpdir) / "docs" / "brain_reboot"
            waypoint_dir.mkdir(parents=True)
            waypoint_file = waypoint_dir / "waypoint.md"
            waypoint_file.write_text("# Original")

            # Patch os.replace to verify it's called
            with patch("claude_headspace.services.waypoint_editor.os.replace") as mock_replace:
                mock_replace.side_effect = lambda src, dst: Path(dst).write_text(Path(src).read_text())

                save_waypoint(tmpdir, "# New Content")

                # os.replace should be called for atomic operation
                assert mock_replace.call_count >= 1
