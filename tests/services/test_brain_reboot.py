"""Tests for the brain reboot service."""

import os
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.claude_headspace.services.brain_reboot import BrainRebootService


@pytest.fixture
def mock_app():
    app = MagicMock()
    app.config = {
        "APP_CONFIG": {
            "brain_reboot": {
                "export_filename": "brain_reboot.md",
            }
        }
    }
    return app


@pytest.fixture
def mock_archive():
    archive = MagicMock()
    archive.archive_cascade.return_value = {
        "waypoint": "archive/waypoint_2026-01-29_16-05-00.md",
        "progress_summary": "archive/progress_summary_2026-01-29_16-05-00.md",
        "brain_reboot": "archive/brain_reboot_2026-01-29_16-05-00.md",
    }
    return archive


@pytest.fixture
def service(mock_app, mock_archive):
    return BrainRebootService(app=mock_app, archive_service=mock_archive)


def _make_project(tmp_path, project_id=1, name="Test Project"):
    project = MagicMock()
    project.id = project_id
    project.name = name
    project.path = str(tmp_path)
    return project


def _write_waypoint(tmp_path, content="# Waypoint\n\n## Next Up\n\n- Task 1\n"):
    wp_dir = tmp_path / "brain_reboot"
    wp_dir.mkdir(parents=True, exist_ok=True)
    (wp_dir / "waypoint.md").write_text(content, encoding="utf-8")


def _write_summary(tmp_path, content=None):
    if content is None:
        content = "---\ngenerated_at: 2026-01-30\nscope: last_n\n---\n\nRecent work included bug fixes and feature additions."
    summary_dir = tmp_path / "brain_reboot"
    summary_dir.mkdir(parents=True, exist_ok=True)
    (summary_dir / "progress_summary.md").write_text(content, encoding="utf-8")


class TestReadWaypoint:
    def test_reads_existing_waypoint(self, service, tmp_path):
        _write_waypoint(tmp_path, "# My Waypoint\n\nContent here")
        result = service._read_waypoint(str(tmp_path))
        assert result == "# My Waypoint\n\nContent here"

    def test_returns_none_missing(self, service, tmp_path):
        result = service._read_waypoint(str(tmp_path))
        assert result is None

    def test_returns_none_empty_file(self, service, tmp_path):
        _write_waypoint(tmp_path, "")
        result = service._read_waypoint(str(tmp_path))
        assert result is None

    def test_returns_none_whitespace_only(self, service, tmp_path):
        _write_waypoint(tmp_path, "   \n  \n  ")
        result = service._read_waypoint(str(tmp_path))
        assert result is None


class TestReadProgressSummary:
    def test_reads_and_strips_frontmatter(self, service, tmp_path):
        _write_summary(tmp_path, "---\nkey: value\n---\n\nBody content here.")
        result = service._read_progress_summary(str(tmp_path))
        assert result == "Body content here."

    def test_reads_without_frontmatter(self, service, tmp_path):
        _write_summary(tmp_path, "Just plain content.")
        result = service._read_progress_summary(str(tmp_path))
        assert result == "Just plain content."

    def test_returns_none_missing(self, service, tmp_path):
        result = service._read_progress_summary(str(tmp_path))
        assert result is None

    def test_returns_none_empty(self, service, tmp_path):
        _write_summary(tmp_path, "")
        result = service._read_progress_summary(str(tmp_path))
        assert result is None


class TestStripFrontmatter:
    def test_strips_yaml_frontmatter(self, service):
        content = "---\nkey: value\n---\n\nBody"
        assert service._strip_frontmatter(content) == "Body"

    def test_no_frontmatter(self, service):
        content = "Just body content"
        assert service._strip_frontmatter(content) == "Just body content"

    def test_single_delimiter(self, service):
        content = "---\nno closing"
        assert service._strip_frontmatter(content) == "---\nno closing"

    def test_empty_frontmatter(self, service):
        content = "---\n---\n\nBody after empty"
        assert service._strip_frontmatter(content) == "Body after empty"


class TestFormatDocument:
    def test_both_artifacts(self, service):
        result = service._format_document(
            "My Project", "Waypoint content", "Summary content"
        )
        assert "# Brain Reboot: My Project" in result
        assert "Generated:" in result
        assert "## Progress Summary" in result
        assert "Summary content" in result
        assert "## Waypoint (Path Ahead)" in result
        assert "Waypoint content" in result
        assert "restore context" in result

    def test_waypoint_before_summary(self, service):
        result = service._format_document(
            "My Project", "WP", "SUM"
        )
        sum_pos = result.index("## Progress Summary")
        wp_pos = result.index("## Waypoint (Path Ahead)")
        assert wp_pos < sum_pos

    def test_waypoint_only(self, service):
        result = service._format_document(
            "My Project", "Waypoint content", None
        )
        assert "## Progress Summary" in result
        assert "not yet available" in result
        assert "Waypoint content" in result

    def test_summary_only(self, service):
        result = service._format_document(
            "My Project", None, "Summary content"
        )
        assert "Summary content" in result
        assert "## Waypoint (Path Ahead)" in result
        assert "not yet available" in result

    def test_neither_artifact(self, service):
        result = service._format_document("My Project", None, None)
        assert "## No Artifacts Available" in result
        assert "Neither a progress summary nor a waypoint" in result
        assert "Progress Summary" in result
        assert "Waypoint" in result


class TestGenerate:
    def test_both_artifacts_present(self, service, tmp_path):
        _write_waypoint(tmp_path, "# Waypoint\n\n## Next Up\n\n- Do thing")
        _write_summary(tmp_path, "---\nkey: val\n---\n\nProgress body here.")
        project = _make_project(tmp_path)

        result = service.generate(project)
        assert result["status"] == "generated"
        assert result["has_waypoint"] is True
        assert result["has_summary"] is True
        assert "Progress body here." in result["content"]
        assert "# Waypoint" in result["content"]
        assert result["metadata"]["project_name"] == "Test Project"
        assert result["metadata"]["has_waypoint"] is True
        assert result["metadata"]["has_summary"] is True

    def test_waypoint_only(self, service, tmp_path):
        _write_waypoint(tmp_path, "# Waypoint\n\nContent")
        project = _make_project(tmp_path)

        result = service.generate(project)
        assert result["has_waypoint"] is True
        assert result["has_summary"] is False
        assert "not yet available" in result["content"]

    def test_summary_only(self, service, tmp_path):
        _write_summary(tmp_path, "---\nkey: val\n---\n\nSummary body.")
        project = _make_project(tmp_path)

        result = service.generate(project)
        assert result["has_waypoint"] is False
        assert result["has_summary"] is True
        assert "Summary body." in result["content"]

    def test_neither_artifact(self, service, tmp_path):
        project = _make_project(tmp_path)

        result = service.generate(project)
        assert result["has_waypoint"] is False
        assert result["has_summary"] is False
        assert "No Artifacts Available" in result["content"]

    def test_caches_result(self, service, tmp_path):
        project = _make_project(tmp_path, project_id=42)

        service.generate(project)
        cached = service.get_last_generated(42)
        assert cached is not None
        assert cached["status"] == "generated"


class TestExport:
    def test_successful_export(self, service, tmp_path):
        project = _make_project(tmp_path)
        content = "# Brain Reboot\n\nSome content"

        result = service.export(project, content)
        assert result["success"] is True
        assert result["error"] is None

        exported = (tmp_path / "brain_reboot" / "brain_reboot.md").read_text()
        assert exported == content

    def test_creates_directory(self, service, tmp_path):
        project = _make_project(tmp_path)
        content = "# Brain Reboot"

        result = service.export(project, content)
        assert result["success"] is True
        assert (tmp_path / "brain_reboot").is_dir()

    def test_overwrites_existing(self, service, tmp_path):
        project = _make_project(tmp_path)
        br_dir = tmp_path / "brain_reboot"
        br_dir.mkdir(parents=True, exist_ok=True)
        (br_dir / "brain_reboot.md").write_text("old content")

        result = service.export(project, "new content")
        assert result["success"] is True
        exported = (br_dir / "brain_reboot.md").read_text()
        assert exported == "new content"

    def test_permission_error(self, service, tmp_path):
        project = _make_project(tmp_path)
        br_dir = tmp_path / "brain_reboot"
        br_dir.mkdir(parents=True, exist_ok=True)

        # Make directory read-only
        os.chmod(str(br_dir), 0o444)
        try:
            result = service.export(project, "content")
            assert result["success"] is False
            assert "Permission denied" in result["error"]
        finally:
            os.chmod(str(br_dir), 0o755)

    def test_export_triggers_cascade_archive(self, service, mock_archive, tmp_path):
        """Should call archive_cascade before writing."""
        project = _make_project(tmp_path)

        result = service.export(project, "# Brain Reboot")

        mock_archive.archive_cascade.assert_called_once_with(str(tmp_path))
        assert result["success"] is True
        assert result["archived"]["waypoint"] is not None
        assert result["archived"]["progress_summary"] is not None
        assert result["archived"]["brain_reboot"] is not None

    def test_export_cascade_failure_non_blocking(self, service, mock_archive, tmp_path):
        """Should continue export even if cascade archive fails."""
        project = _make_project(tmp_path)
        mock_archive.archive_cascade.side_effect = OSError("disk full")

        result = service.export(project, "# Brain Reboot")

        assert result["success"] is True
        exported = (tmp_path / "brain_reboot" / "brain_reboot.md").read_text()
        assert exported == "# Brain Reboot"

    def test_export_without_archive_service(self, mock_app, tmp_path):
        """Should work without archive service (no archiving)."""
        svc = BrainRebootService(app=mock_app)
        project = _make_project(tmp_path)

        result = svc.export(project, "content")
        assert result["success"] is True
        assert result["archived"] == {}

    def test_custom_export_filename(self, tmp_path):
        app = MagicMock()
        app.config = {
            "APP_CONFIG": {
                "brain_reboot": {
                    "export_filename": "custom_reboot.md",
                }
            }
        }
        svc = BrainRebootService(app=app)
        project = _make_project(tmp_path)

        svc.export(project, "content")
        assert (tmp_path / "brain_reboot" / "custom_reboot.md").exists()


class TestGetLastGenerated:
    def test_returns_none_not_generated(self, service):
        assert service.get_last_generated(1) is None

    def test_returns_cached_after_generate(self, service, tmp_path):
        project = _make_project(tmp_path, project_id=5)
        service.generate(project)
        cached = service.get_last_generated(5)
        assert cached is not None
        assert cached["status"] == "generated"

    def test_different_projects_independent(self, service, tmp_path):
        p1 = _make_project(tmp_path, project_id=1, name="P1")
        p2 = _make_project(tmp_path, project_id=2, name="P2")

        service.generate(p1)
        assert service.get_last_generated(1) is not None
        assert service.get_last_generated(2) is None

        service.generate(p2)
        assert service.get_last_generated(2) is not None

    def test_overwrites_previous_cache(self, service, tmp_path):
        project = _make_project(tmp_path, project_id=1)

        result1 = service.generate(project)
        result2 = service.generate(project)

        cached = service.get_last_generated(1)
        assert cached["metadata"]["generated_at"] == result2["metadata"]["generated_at"]
