"""Tests for centralized archive service."""

import os
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

from claude_headspace.services.archive_service import (
    ARCHIVE_DIR,
    BRAIN_REBOOT_DIR,
    VALID_ARTIFACT_TYPES,
    ArchiveService,
)


@pytest.fixture
def service():
    """Create an ArchiveService with default config."""
    return ArchiveService(config={
        "archive": {
            "enabled": True,
            "retention": {
                "policy": "keep_all",
                "keep_last_n": 10,
                "days": 90,
            },
        },
    })


@pytest.fixture
def project_dir(tmp_path):
    """Create a project directory with brain_reboot structure."""
    br_dir = tmp_path / BRAIN_REBOOT_DIR
    br_dir.mkdir(parents=True)
    return tmp_path


def _create_artifact(project_dir, artifact_type, content="# Content"):
    """Create a source artifact file."""
    path = Path(project_dir) / BRAIN_REBOOT_DIR / f"{artifact_type}.md"
    path.write_text(content, encoding="utf-8")
    return path


def _create_archive(project_dir, artifact_type, timestamp_str, content="archived"):
    """Create an archive file directly."""
    archive_dir = Path(project_dir) / ARCHIVE_DIR
    archive_dir.mkdir(parents=True, exist_ok=True)
    path = archive_dir / f"{artifact_type}_{timestamp_str}.md"
    path.write_text(content, encoding="utf-8")
    return path


class TestArchiveArtifact:
    """Tests for archive_artifact method."""

    def test_archives_waypoint_with_timestamp(self, service, project_dir):
        """Should create an archive file with second-precision timestamp."""
        _create_artifact(project_dir, "waypoint", "# Old Waypoint")
        ts = datetime(2026, 1, 28, 14, 30, 0, tzinfo=timezone.utc)

        result = service.archive_artifact(project_dir, "waypoint", timestamp=ts)

        assert result is not None
        assert "archive/waypoint_2026-01-28_14-30-00.md" in result
        archive_path = project_dir / ARCHIVE_DIR / "waypoint_2026-01-28_14-30-00.md"
        assert archive_path.exists()
        assert archive_path.read_text() == "# Old Waypoint"

    def test_archives_progress_summary(self, service, project_dir):
        """Should archive progress_summary artifact."""
        _create_artifact(project_dir, "progress_summary", "# Summary")
        ts = datetime(2026, 1, 29, 16, 0, 0, tzinfo=timezone.utc)

        result = service.archive_artifact(project_dir, "progress_summary", timestamp=ts)

        assert result is not None
        archive_path = project_dir / ARCHIVE_DIR / "progress_summary_2026-01-29_16-00-00.md"
        assert archive_path.exists()
        assert archive_path.read_text() == "# Summary"

    def test_archives_brain_reboot(self, service, project_dir):
        """Should archive brain_reboot artifact."""
        _create_artifact(project_dir, "brain_reboot", "# Brain Reboot")
        ts = datetime(2026, 1, 29, 16, 5, 0, tzinfo=timezone.utc)

        result = service.archive_artifact(project_dir, "brain_reboot", timestamp=ts)

        assert result is not None
        archive_path = project_dir / ARCHIVE_DIR / "brain_reboot_2026-01-29_16-05-00.md"
        assert archive_path.exists()

    def test_creates_archive_directory_if_missing(self, service, project_dir):
        """Should auto-create archive directory."""
        _create_artifact(project_dir, "waypoint", "# Content")
        archive_dir = project_dir / ARCHIVE_DIR
        assert not archive_dir.exists()

        service.archive_artifact(project_dir, "waypoint")

        assert archive_dir.exists()

    def test_returns_none_when_source_missing(self, service, project_dir):
        """Should return None if source file doesn't exist."""
        result = service.archive_artifact(project_dir, "waypoint")
        assert result is None

    def test_returns_none_for_invalid_artifact_type(self, service, project_dir):
        """Should return None for invalid artifact type."""
        result = service.archive_artifact(project_dir, "invalid_type")
        assert result is None

    def test_returns_none_when_disabled(self, project_dir):
        """Should return None when archive is disabled."""
        service = ArchiveService(config={"archive": {"enabled": False}})
        _create_artifact(project_dir, "waypoint", "# Content")

        result = service.archive_artifact(project_dir, "waypoint")
        assert result is None

    def test_uses_utc_now_as_default_timestamp(self, service, project_dir):
        """Should use current UTC time when no timestamp provided."""
        _create_artifact(project_dir, "waypoint", "# Content")

        with patch("claude_headspace.services.archive_service.datetime") as mock_dt:
            mock_dt.now.return_value = datetime(2026, 3, 15, 10, 20, 30, tzinfo=timezone.utc)
            mock_dt.strptime = datetime.strptime
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
            service.archive_artifact(project_dir, "waypoint")

        archive_path = project_dir / ARCHIVE_DIR / "waypoint_2026-03-15_10-20-30.md"
        assert archive_path.exists()

    def test_atomic_write(self, service, project_dir):
        """Should use atomic write via tempfile + os.replace."""
        _create_artifact(project_dir, "waypoint", "# Content")

        with patch("claude_headspace.services.archive_service.os.replace") as mock_replace:
            mock_replace.side_effect = lambda src, dst: Path(dst).write_text(
                Path(src).read_text()
            )
            service.archive_artifact(
                project_dir, "waypoint",
                timestamp=datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
            )
            assert mock_replace.call_count == 1

    def test_archive_failure_returns_none(self, service, project_dir):
        """Should return None on failure, not raise."""
        _create_artifact(project_dir, "waypoint", "# Content")

        with patch("claude_headspace.services.archive_service.tempfile.mkstemp") as mock:
            mock.side_effect = OSError("disk full")
            result = service.archive_artifact(project_dir, "waypoint")
            assert result is None


class TestArchiveCascade:
    """Tests for archive_cascade method."""

    def test_archives_all_three_types(self, service, project_dir):
        """Should archive waypoint, progress_summary, and brain_reboot."""
        _create_artifact(project_dir, "waypoint", "# Waypoint")
        _create_artifact(project_dir, "progress_summary", "# Summary")
        _create_artifact(project_dir, "brain_reboot", "# Brain Reboot")
        ts = datetime(2026, 2, 1, 12, 0, 0, tzinfo=timezone.utc)

        results = service.archive_cascade(project_dir, timestamp=ts)

        assert results["waypoint"] is not None
        assert results["progress_summary"] is not None
        assert results["brain_reboot"] is not None

        # All share the same timestamp
        archive_dir = project_dir / ARCHIVE_DIR
        assert (archive_dir / "waypoint_2026-02-01_12-00-00.md").exists()
        assert (archive_dir / "progress_summary_2026-02-01_12-00-00.md").exists()
        assert (archive_dir / "brain_reboot_2026-02-01_12-00-00.md").exists()

    def test_best_effort_one_failure_doesnt_block_others(self, service, project_dir):
        """Should continue archiving other artifacts if one fails."""
        _create_artifact(project_dir, "waypoint", "# Waypoint")
        # progress_summary doesn't exist — should be None, not error
        _create_artifact(project_dir, "brain_reboot", "# Brain Reboot")

        results = service.archive_cascade(project_dir)

        assert results["waypoint"] is not None
        assert results["progress_summary"] is None  # Doesn't exist, skipped
        assert results["brain_reboot"] is not None

    def test_returns_none_for_missing_artifacts(self, service, project_dir):
        """Should return None for artifacts that don't exist."""
        results = service.archive_cascade(project_dir)

        assert results["waypoint"] is None
        assert results["progress_summary"] is None
        assert results["brain_reboot"] is None


class TestEnforceRetention:
    """Tests for enforce_retention method."""

    def test_keep_all_deletes_nothing(self, service, project_dir):
        """keep_all policy should not delete any archives."""
        for i in range(15):
            ts = f"2026-01-{i+1:02d}_12-00-00"
            _create_archive(project_dir, "waypoint", ts)

        deleted = service.enforce_retention(project_dir, "waypoint")
        assert deleted == 0

        archive_dir = project_dir / ARCHIVE_DIR
        assert len(list(archive_dir.glob("waypoint_*.md"))) == 15

    def test_keep_last_n_removes_oldest(self, project_dir):
        """keep_last_n should remove archives beyond N."""
        svc = ArchiveService(config={
            "archive": {
                "enabled": True,
                "retention": {"policy": "keep_last_n", "keep_last_n": 3},
            },
        })

        for i in range(5):
            ts = f"2026-01-{i+1:02d}_12-00-00"
            _create_archive(project_dir, "waypoint", ts)

        deleted = svc.enforce_retention(project_dir, "waypoint")
        assert deleted == 2

        archive_dir = project_dir / ARCHIVE_DIR
        remaining = sorted(f.name for f in archive_dir.glob("waypoint_*.md"))
        assert len(remaining) == 3
        # Should keep the 3 newest
        assert "waypoint_2026-01-03_12-00-00.md" in remaining
        assert "waypoint_2026-01-04_12-00-00.md" in remaining
        assert "waypoint_2026-01-05_12-00-00.md" in remaining

    def test_time_based_removes_expired(self, project_dir):
        """time_based should remove archives older than N days."""
        svc = ArchiveService(config={
            "archive": {
                "enabled": True,
                "retention": {"policy": "time_based", "days": 30},
            },
        })

        now = datetime.now(timezone.utc)
        # Create one recent and one old archive
        recent_ts = now.strftime("%Y-%m-%d_%H-%M-%S")
        old_ts = (now - timedelta(days=60)).strftime("%Y-%m-%d_%H-%M-%S")

        _create_archive(project_dir, "waypoint", recent_ts, "recent")
        _create_archive(project_dir, "waypoint", old_ts, "old")

        deleted = svc.enforce_retention(project_dir, "waypoint")
        assert deleted == 1

        archive_dir = project_dir / ARCHIVE_DIR
        remaining = list(archive_dir.glob("waypoint_*.md"))
        assert len(remaining) == 1
        assert remaining[0].read_text() == "recent"

    def test_only_affects_specified_artifact_type(self, project_dir):
        """Should only clean up the specified artifact type."""
        svc = ArchiveService(config={
            "archive": {
                "enabled": True,
                "retention": {"policy": "keep_last_n", "keep_last_n": 1},
            },
        })

        for i in range(3):
            ts = f"2026-01-{i+1:02d}_12-00-00"
            _create_archive(project_dir, "waypoint", ts)
            _create_archive(project_dir, "progress_summary", ts)

        svc.enforce_retention(project_dir, "waypoint")

        archive_dir = project_dir / ARCHIVE_DIR
        assert len(list(archive_dir.glob("waypoint_*.md"))) == 1
        assert len(list(archive_dir.glob("progress_summary_*.md"))) == 3  # Untouched

    def test_returns_zero_for_empty_archive(self, service, project_dir):
        """Should return 0 when no archives exist."""
        deleted = service.enforce_retention(project_dir, "waypoint")
        assert deleted == 0


class TestListArchives:
    """Tests for list_archives method."""

    def test_returns_grouped_results(self, service, project_dir):
        """Should return archives grouped by type."""
        _create_archive(project_dir, "waypoint", "2026-01-28_14-30-00")
        _create_archive(project_dir, "waypoint", "2026-01-25_09-15-00")
        _create_archive(project_dir, "progress_summary", "2026-01-29_16-00-00")

        result = service.list_archives(project_dir)

        assert len(result["waypoint"]) == 2
        assert len(result["progress_summary"]) == 1
        assert len(result["brain_reboot"]) == 0

    def test_returns_empty_when_no_archives(self, service, project_dir):
        """Should return empty lists when no archives exist."""
        result = service.list_archives(project_dir)

        for atype in VALID_ARTIFACT_TYPES:
            assert result[atype] == []

    def test_sorted_newest_first(self, service, project_dir):
        """Should return archives sorted newest first."""
        _create_archive(project_dir, "waypoint", "2026-01-25_09-15-00")
        _create_archive(project_dir, "waypoint", "2026-01-28_14-30-00")
        _create_archive(project_dir, "waypoint", "2026-01-26_10-00-00")

        result = service.list_archives(project_dir)

        timestamps = [e["timestamp"] for e in result["waypoint"]]
        assert timestamps == [
            "2026-01-28T14:30:00Z",
            "2026-01-26T10:00:00Z",
            "2026-01-25T09:15:00Z",
        ]

    def test_filter_by_artifact_type(self, service, project_dir):
        """Should filter by artifact type when specified."""
        _create_archive(project_dir, "waypoint", "2026-01-28_14-30-00")
        _create_archive(project_dir, "progress_summary", "2026-01-29_16-00-00")

        result = service.list_archives(project_dir, artifact_type="waypoint")

        assert "waypoint" in result
        assert len(result["waypoint"]) == 1
        # Other types still present with empty lists
        assert result.get("progress_summary", []) == []

    def test_entries_have_filename_and_timestamp(self, service, project_dir):
        """Should include filename and ISO timestamp in each entry."""
        _create_archive(project_dir, "waypoint", "2026-01-28_14-30-00")

        result = service.list_archives(project_dir)
        entry = result["waypoint"][0]

        assert entry["filename"] == "waypoint_2026-01-28_14-30-00.md"
        assert entry["timestamp"] == "2026-01-28T14:30:00Z"


class TestGetArchive:
    """Tests for get_archive method."""

    def test_returns_content_for_valid_archive(self, service, project_dir):
        """Should return content for valid artifact/timestamp."""
        _create_archive(project_dir, "waypoint", "2026-01-28_14-30-00", "# Waypoint v1")

        result = service.get_archive(project_dir, "waypoint", "2026-01-28_14-30-00")

        assert result is not None
        assert result["artifact"] == "waypoint"
        assert result["timestamp"] == "2026-01-28T14:30:00Z"
        assert result["filename"] == "waypoint_2026-01-28_14-30-00.md"
        assert result["content"] == "# Waypoint v1"

    def test_returns_none_for_nonexistent(self, service, project_dir):
        """Should return None when archive doesn't exist."""
        result = service.get_archive(project_dir, "waypoint", "2026-01-01_00-00-00")
        assert result is None

    def test_returns_none_for_invalid_artifact_type(self, service, project_dir):
        """Should return None for invalid artifact type."""
        result = service.get_archive(project_dir, "invalid", "2026-01-01_00-00-00")
        assert result is None

    def test_ignores_non_matching_files(self, service, project_dir):
        """Should ignore files that don't match the expected pattern."""
        archive_dir = project_dir / ARCHIVE_DIR
        archive_dir.mkdir(parents=True, exist_ok=True)
        # Create a file with old date-only format
        (archive_dir / "waypoint_2026-01-28.md").write_text("old format")
        # Create a file with counter format
        (archive_dir / "waypoint_2026-01-28_2.md").write_text("counter format")

        result = service.list_archives(project_dir)
        assert len(result["waypoint"]) == 0  # Neither should match
