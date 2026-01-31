"""Unit tests for progress summary service."""

from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

from src.claude_headspace.services.git_analyzer import (
    CommitInfo,
    GitAnalysisResult,
    GitAnalyzerError,
)
from src.claude_headspace.services.openrouter_client import InferenceResult
from src.claude_headspace.services.progress_summary import (
    ARCHIVE_DIR,
    SUMMARY_DIR,
    SUMMARY_FILENAME,
    ProgressSummaryService,
)


@pytest.fixture
def mock_inference():
    service = MagicMock()
    service.is_available = True
    return service


@pytest.fixture
def mock_app(mock_inference):
    app = MagicMock()
    app.config = {
        "APP_CONFIG": {
            "progress_summary": {
                "default_scope": "since_last",
                "last_n_count": 50,
                "time_based_days": 7,
                "max_commits": 200,
            }
        }
    }
    return app


@pytest.fixture
def service(mock_inference, mock_app):
    return ProgressSummaryService(
        inference_service=mock_inference,
        app=mock_app,
    )


@pytest.fixture
def mock_project(tmp_path):
    project = MagicMock()
    project.id = 1
    project.name = "test-project"
    project.path = str(tmp_path)
    return project


@pytest.fixture
def sample_analysis():
    return GitAnalysisResult(
        commits=[
            CommitInfo(
                hash="abc123def456",
                message="Add login feature",
                author="Alice",
                timestamp=datetime(2026, 1, 30, 10, 0, 0, tzinfo=timezone.utc),
                files_changed=["src/auth.py", "tests/test_auth.py"],
            ),
            CommitInfo(
                hash="def789ghi012",
                message="Fix database connection",
                author="Bob",
                timestamp=datetime(2026, 1, 29, 15, 0, 0, tzinfo=timezone.utc),
                files_changed=["src/db.py"],
            ),
        ],
        unique_files_changed=["src/auth.py", "src/db.py", "tests/test_auth.py"],
        unique_authors=["Alice", "Bob"],
        date_range_start=datetime(2026, 1, 29, 15, 0, 0, tzinfo=timezone.utc),
        date_range_end=datetime(2026, 1, 30, 10, 0, 0, tzinfo=timezone.utc),
        total_commit_count=2,
        scope_used="last_n",
        truncated=False,
    )


class TestBuildPrompt:

    def test_prompt_includes_project_name(self, service, sample_analysis):
        prompt = service._build_prompt("my-project", sample_analysis)
        assert "my-project" in prompt

    def test_prompt_includes_date_range(self, service, sample_analysis):
        prompt = service._build_prompt("proj", sample_analysis)
        assert "2026-01-29" in prompt
        assert "2026-01-30" in prompt

    def test_prompt_includes_commit_details(self, service, sample_analysis):
        prompt = service._build_prompt("proj", sample_analysis)
        assert "Add login feature" in prompt
        assert "Fix database connection" in prompt
        assert "Alice" in prompt
        assert "Bob" in prompt

    def test_prompt_includes_files_changed(self, service, sample_analysis):
        prompt = service._build_prompt("proj", sample_analysis)
        assert "src/auth.py" in prompt

    def test_prompt_requests_narrative_format(self, service, sample_analysis):
        prompt = service._build_prompt("proj", sample_analysis)
        assert "3-5 paragraph" in prompt
        assert "past tense" in prompt

    def test_prompt_handles_no_date_range(self, service):
        analysis = GitAnalysisResult(
            commits=[],
            total_commit_count=0,
            scope_used="last_n",
        )
        prompt = service._build_prompt("proj", analysis)
        assert "N/A" in prompt


class TestWriteSummary:

    def test_writes_file_with_frontmatter(self, service, tmp_path):
        metadata = {
            "generated_at": "2026-01-31T10:00:00+00:00",
            "scope": "last_n",
            "commit_count": 5,
        }

        service._write_summary(str(tmp_path), "Summary content here.", metadata)

        summary_path = tmp_path / SUMMARY_DIR / SUMMARY_FILENAME
        assert summary_path.exists()
        content = summary_path.read_text()
        assert "---" in content
        assert "generated_at: 2026-01-31T10:00:00+00:00" in content
        assert "Summary content here." in content

    def test_creates_directories(self, service, tmp_path):
        service._write_summary(str(tmp_path), "Content", {"scope": "last_n"})

        assert (tmp_path / SUMMARY_DIR).is_dir()
        assert (tmp_path / SUMMARY_DIR / ARCHIVE_DIR).is_dir()

    def test_archives_existing_before_overwrite(self, service, tmp_path):
        base_dir = tmp_path / SUMMARY_DIR
        base_dir.mkdir(parents=True)
        (base_dir / ARCHIVE_DIR).mkdir()

        # Write initial summary
        initial = "---\ngenerated_at: old\n---\n\nOld content"
        (base_dir / SUMMARY_FILENAME).write_text(initial)

        # Write new summary
        service._write_summary(str(tmp_path), "New content", {"scope": "last_n"})

        # Verify archive exists
        archive_files = list((base_dir / ARCHIVE_DIR).glob("progress_summary_*.md"))
        assert len(archive_files) == 1
        assert "Old content" in archive_files[0].read_text()

        # Verify new summary
        assert "New content" in (base_dir / SUMMARY_FILENAME).read_text()


class TestArchiveExisting:

    def test_basic_archive(self, service, tmp_path):
        base_dir = tmp_path / SUMMARY_DIR
        base_dir.mkdir(parents=True)
        archive_dir = base_dir / ARCHIVE_DIR
        archive_dir.mkdir()

        summary_path = base_dir / SUMMARY_FILENAME
        summary_path.write_text("Original content")

        service._archive_existing(base_dir, summary_path)

        archive_files = list(archive_dir.glob("progress_summary_*.md"))
        assert len(archive_files) == 1
        assert "Original content" in archive_files[0].read_text()

    def test_same_day_suffix(self, service, tmp_path):
        base_dir = tmp_path / SUMMARY_DIR
        base_dir.mkdir(parents=True)
        archive_dir = base_dir / ARCHIVE_DIR
        archive_dir.mkdir()

        summary_path = base_dir / SUMMARY_FILENAME

        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        # Create existing archive for today
        (archive_dir / f"progress_summary_{today}.md").write_text("First archive")

        # Archive again
        summary_path.write_text("Second version")
        service._archive_existing(base_dir, summary_path)

        archive_2 = archive_dir / f"progress_summary_{today}_2.md"
        assert archive_2.exists()
        assert "Second version" in archive_2.read_text()

    def test_multiple_same_day_suffixes(self, service, tmp_path):
        base_dir = tmp_path / SUMMARY_DIR
        base_dir.mkdir(parents=True)
        archive_dir = base_dir / ARCHIVE_DIR
        archive_dir.mkdir()

        summary_path = base_dir / SUMMARY_FILENAME
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        # Create first two archives
        (archive_dir / f"progress_summary_{today}.md").write_text("v1")
        (archive_dir / f"progress_summary_{today}_2.md").write_text("v2")

        # Archive third
        summary_path.write_text("v3")
        service._archive_existing(base_dir, summary_path)

        archive_3 = archive_dir / f"progress_summary_{today}_3.md"
        assert archive_3.exists()


class TestGetCurrentSummary:

    def test_returns_content_when_exists(self, service, mock_project, tmp_path):
        base_dir = tmp_path / SUMMARY_DIR
        base_dir.mkdir(parents=True)
        summary_path = base_dir / SUMMARY_FILENAME
        summary_path.write_text(
            "---\ngenerated_at: 2026-01-31T10:00:00+00:00\nscope: last_n\n---\n\nSummary text here."
        )

        result = service.get_current_summary(mock_project)

        assert result["status"] == "found"
        assert "Summary text here." in result["summary"]
        assert result["metadata"]["generated_at"] == "2026-01-31T10:00:00+00:00"

    def test_returns_not_found_when_missing(self, service, mock_project):
        result = service.get_current_summary(mock_project)
        assert result["status"] == "not_found"

    def test_returns_error_for_no_path(self, service):
        project = MagicMock()
        project.path = None
        result = service.get_current_summary(project)
        assert result["status"] == "error"


class TestConcurrentGuard:

    def test_guard_prevents_duplicate(self, service, mock_project):
        # Manually set in_progress
        with service._lock:
            service._in_progress.add(mock_project.id)

        result = service.generate(mock_project)

        assert result["status"] == "in_progress"
        assert "already in progress" in result["error"]

    def test_guard_cleared_on_success(self, service, mock_project, mock_inference):
        with patch.object(service._git_analyzer, "analyze") as mock_analyze:
            mock_analyze.return_value = GitAnalysisResult(
                commits=[], total_commit_count=0, scope_used="last_n"
            )
            service.generate(mock_project)

        assert mock_project.id not in service._in_progress

    def test_guard_cleared_on_error(self, service, mock_project):
        with patch.object(service._git_analyzer, "analyze") as mock_analyze:
            mock_analyze.side_effect = GitAnalyzerError("test error")
            service.generate(mock_project)

        assert mock_project.id not in service._in_progress

    def test_is_generating_check(self, service):
        assert service.is_generating(1) is False
        with service._lock:
            service._in_progress.add(1)
        assert service.is_generating(1) is True


class TestGenerate:

    def test_empty_scope_returns_message(self, service, mock_project):
        with patch.object(service._git_analyzer, "analyze") as mock_analyze:
            mock_analyze.return_value = GitAnalysisResult(
                commits=[], total_commit_count=0, scope_used="last_n"
            )

            result = service.generate(mock_project)

        assert result["status"] == "empty"
        assert "No commits found" in result["message"]
        # Should not call inference
        service._inference.infer.assert_not_called()

    def test_successful_generation(self, service, mock_project, mock_inference, sample_analysis):
        mock_inference.infer.return_value = InferenceResult(
            text="The team made great progress this week.",
            input_tokens=500,
            output_tokens=100,
            model="anthropic/claude-3-5-sonnet-20241022",
            latency_ms=2000,
        )

        with patch.object(service._git_analyzer, "analyze", return_value=sample_analysis):
            result = service.generate(mock_project)

        assert result["status"] == "success"
        assert "great progress" in result["summary"]
        assert result["metadata"]["commit_count"] == 2
        mock_inference.infer.assert_called_once()

        # Verify file was written
        summary_path = Path(mock_project.path) / SUMMARY_DIR / SUMMARY_FILENAME
        assert summary_path.exists()

    def test_git_error_returns_error(self, service, mock_project):
        with patch.object(service._git_analyzer, "analyze") as mock_analyze:
            mock_analyze.side_effect = GitAnalyzerError("Not a git repository")

            result = service.generate(mock_project)

        assert result["status"] == "error"
        assert "Not a git repository" in result["error"]

    def test_inference_error_returns_error(self, service, mock_project, mock_inference, sample_analysis):
        mock_inference.infer.side_effect = InferenceServiceError("API key not configured")

        with patch.object(service._git_analyzer, "analyze", return_value=sample_analysis):
            result = service.generate(mock_project)

        assert result["status"] == "error"
        assert "Inference failed" in result["error"]

    def test_no_path_returns_error(self, service):
        project = MagicMock()
        project.id = 99
        project.path = None
        result = service.generate(project)
        assert result["status"] == "error"

    def test_scope_override(self, service, mock_project, mock_inference, sample_analysis):
        mock_inference.infer.return_value = InferenceResult(
            text="Summary.", input_tokens=100, output_tokens=50,
            model="test", latency_ms=100,
        )

        with patch.object(service._git_analyzer, "analyze", return_value=sample_analysis) as mock_analyze:
            service.generate(mock_project, scope="time_based")

        mock_analyze.assert_called_once()
        call_kwargs = mock_analyze.call_args
        assert call_kwargs.kwargs.get("scope") == "time_based" or call_kwargs[1].get("scope") == "time_based"

    def test_file_write_error_returns_summary(self, service, mock_project, mock_inference, sample_analysis):
        mock_inference.infer.return_value = InferenceResult(
            text="Summary text.", input_tokens=100, output_tokens=50,
            model="test", latency_ms=100,
        )

        with patch.object(service._git_analyzer, "analyze", return_value=sample_analysis):
            with patch.object(service, "_write_summary", side_effect=PermissionError("denied")):
                result = service.generate(mock_project)

        assert result["status"] == "error"
        assert "File write failed" in result["error"]
        # Summary should still be returned even though file write failed
        assert result["summary"] == "Summary text."


class TestFrontmatter:

    def test_build_frontmatter(self):
        metadata = {
            "generated_at": "2026-01-31T10:00:00+00:00",
            "scope": "last_n",
            "commit_count": 5,
            "truncated": False,
            "date_range_start": None,
        }
        result = ProgressSummaryService._build_frontmatter(metadata)
        assert result.startswith("---")
        assert result.endswith("---")
        assert "generated_at: 2026-01-31T10:00:00+00:00" in result
        assert "truncated: false" in result
        assert "date_range_start: null" in result

    def test_parse_metadata(self):
        content = "---\ngenerated_at: 2026-01-31T10:00:00+00:00\nscope: last_n\ntruncated: true\n---\n\nBody"
        metadata = ProgressSummaryService._parse_metadata(content)
        assert metadata["generated_at"] == "2026-01-31T10:00:00+00:00"
        assert metadata["scope"] == "last_n"
        assert metadata["truncated"] is True

    def test_parse_metadata_no_frontmatter(self):
        content = "Just plain text without frontmatter"
        metadata = ProgressSummaryService._parse_metadata(content)
        assert metadata == {}

    def test_strip_frontmatter(self):
        content = "---\nkey: value\n---\n\nBody text"
        result = ProgressSummaryService._strip_frontmatter(content)
        assert result == "Body text"

    def test_strip_frontmatter_no_frontmatter(self):
        content = "Just plain text"
        result = ProgressSummaryService._strip_frontmatter(content)
        assert result == "Just plain text"


class TestGetLastGenerationTimestamp:

    def test_returns_timestamp_from_existing(self, service, tmp_path):
        base_dir = tmp_path / SUMMARY_DIR
        base_dir.mkdir(parents=True)
        (base_dir / SUMMARY_FILENAME).write_text(
            "---\ngenerated_at: 2026-01-30T10:00:00+00:00\n---\n\nContent"
        )

        result = service._get_last_generation_timestamp(str(tmp_path))

        assert result is not None
        assert result.day == 30

    def test_returns_none_when_no_file(self, service, tmp_path):
        result = service._get_last_generation_timestamp(str(tmp_path))
        assert result is None

    def test_returns_none_on_invalid_timestamp(self, service, tmp_path):
        base_dir = tmp_path / SUMMARY_DIR
        base_dir.mkdir(parents=True)
        (base_dir / SUMMARY_FILENAME).write_text(
            "---\ngenerated_at: not-a-date\n---\n\nContent"
        )

        result = service._get_last_generation_timestamp(str(tmp_path))
        assert result is None


# Import for side_effect in test
from src.claude_headspace.services.inference_service import InferenceServiceError
