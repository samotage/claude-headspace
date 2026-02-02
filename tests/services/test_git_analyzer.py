"""Unit tests for git analyzer service."""

import subprocess
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.claude_headspace.services.git_analyzer import (
    COMMIT_DELIMITER,
    FIELD_DELIMITER,
    GIT_LOG_FORMAT,
    CommitInfo,
    GitAnalysisResult,
    GitAnalyzer,
    GitAnalyzerError,
)


@pytest.fixture
def config():
    return {
        "progress_summary": {
            "default_scope": "since_last",
            "last_n_count": 50,
            "time_based_days": 7,
            "max_commits": 200,
        }
    }


@pytest.fixture
def analyzer(config):
    return GitAnalyzer(config=config)


@pytest.fixture
def small_cap_analyzer():
    return GitAnalyzer(config={
        "progress_summary": {
            "max_commits": 3,
            "last_n_count": 10,
            "time_based_days": 7,
        }
    })


def _make_log_entry(hash: str, message: str, author: str, timestamp: str) -> str:
    """Build a single git log entry in the expected format."""
    return FIELD_DELIMITER.join([hash, message, author, timestamp]) + COMMIT_DELIMITER


def _make_log_output(*entries: str) -> str:
    """Combine multiple log entries."""
    return "\n".join(entries)


class TestIsGitRepo:

    @patch("subprocess.run")
    def test_valid_git_repo(self, mock_run, analyzer, tmp_path):
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="true\n", stderr=""
        )
        assert analyzer._is_git_repo(tmp_path) is True

    @patch("subprocess.run")
    def test_not_a_git_repo(self, mock_run, analyzer, tmp_path):
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=128, stdout="", stderr="fatal: not a git repository"
        )
        assert analyzer._is_git_repo(tmp_path) is False

    @patch("subprocess.run")
    def test_git_not_installed(self, mock_run, analyzer, tmp_path):
        mock_run.side_effect = FileNotFoundError()
        assert analyzer._is_git_repo(tmp_path) is False


class TestRunGit:

    @patch("subprocess.run")
    def test_successful_command(self, mock_run, analyzer, tmp_path):
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="output\n", stderr=""
        )
        result = analyzer._run_git(tmp_path, ["log", "--oneline"])
        assert result == "output\n"
        mock_run.assert_called_once()

    @patch("subprocess.run")
    def test_failed_command_raises(self, mock_run, analyzer, tmp_path):
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=1, stdout="", stderr="error message"
        )
        with pytest.raises(GitAnalyzerError, match="error message"):
            analyzer._run_git(tmp_path, ["log"])

    @patch("subprocess.run")
    def test_timeout_raises(self, mock_run, analyzer, tmp_path):
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="git", timeout=30)
        with pytest.raises(GitAnalyzerError, match="timed out"):
            analyzer._run_git(tmp_path, ["log"])

    @patch("subprocess.run")
    def test_git_not_found_raises(self, mock_run, analyzer, tmp_path):
        mock_run.side_effect = FileNotFoundError()
        with pytest.raises(GitAnalyzerError, match="not installed"):
            analyzer._run_git(tmp_path, ["log"])

    @patch("subprocess.run")
    def test_permission_error_raises(self, mock_run, analyzer, tmp_path):
        mock_run.side_effect = PermissionError("denied")
        with pytest.raises(GitAnalyzerError, match="Permission denied"):
            analyzer._run_git(tmp_path, ["log"])

    @patch("subprocess.run")
    def test_os_error_raises(self, mock_run, analyzer, tmp_path):
        mock_run.side_effect = OSError("disk failure")
        with pytest.raises(GitAnalyzerError, match="OS error"):
            analyzer._run_git(tmp_path, ["log"])


class TestParseGitLog:

    def test_parse_single_commit(self, analyzer):
        raw = _make_log_entry(
            "abc123def456", "Fix login bug", "Alice", "2026-01-30T10:00:00+00:00"
        )
        commits = analyzer._parse_git_log(raw)

        assert len(commits) == 1
        assert commits[0].hash == "abc123def456"
        assert commits[0].message == "Fix login bug"
        assert commits[0].author == "Alice"
        assert commits[0].timestamp.year == 2026

    def test_parse_multiple_commits(self, analyzer):
        raw = _make_log_output(
            _make_log_entry("aaa111", "First commit", "Alice", "2026-01-30T10:00:00+00:00"),
            _make_log_entry("bbb222", "Second commit", "Bob", "2026-01-29T09:00:00+00:00"),
        )
        commits = analyzer._parse_git_log(raw)
        assert len(commits) == 2
        assert commits[0].hash == "aaa111"
        assert commits[1].hash == "bbb222"

    def test_parse_empty_output(self, analyzer):
        commits = analyzer._parse_git_log("")
        assert commits == []

    def test_parse_whitespace_only(self, analyzer):
        commits = analyzer._parse_git_log("   \n  \n  ")
        assert commits == []

    def test_malformed_entry_skipped(self, analyzer):
        raw = _make_log_output(
            _make_log_entry("aaa111", "Good commit", "Alice", "2026-01-30T10:00:00+00:00"),
            "malformed data without delimiters" + COMMIT_DELIMITER,
        )
        commits = analyzer._parse_git_log(raw)
        assert len(commits) == 1
        assert commits[0].hash == "aaa111"

    def test_invalid_timestamp_skipped(self, analyzer):
        raw = _make_log_entry("aaa111", "Bad time", "Alice", "not-a-date")
        commits = analyzer._parse_git_log(raw)
        assert commits == []

    def test_naive_timestamp_gets_utc(self, analyzer):
        raw = _make_log_entry("aaa111", "Naive", "Alice", "2026-01-30T10:00:00")
        commits = analyzer._parse_git_log(raw)
        assert len(commits) == 1
        assert commits[0].timestamp.tzinfo == timezone.utc


class TestAnalyzeScopeLastN:

    @patch("subprocess.run")
    def test_last_n_scope(self, mock_run, analyzer, tmp_path):
        # First call: is_git_repo
        # Second call: git log
        # Third call: diff-tree (per commit)
        mock_run.side_effect = [
            subprocess.CompletedProcess(args=[], returncode=0, stdout="true\n", stderr=""),
            subprocess.CompletedProcess(
                args=[], returncode=0,
                stdout=_make_log_entry("abc123", "Add feature", "Alice", "2026-01-30T10:00:00+00:00"),
                stderr="",
            ),
            subprocess.CompletedProcess(
                args=[], returncode=0, stdout="src/app.py\nREADME.md\n", stderr=""
            ),
        ]

        result = analyzer.analyze(tmp_path, scope="last_n", last_n=5)

        assert result.total_commit_count == 1
        assert result.scope_used == "last_n"
        assert result.commits[0].hash == "abc123"
        assert "src/app.py" in result.unique_files_changed
        assert "Alice" in result.unique_authors

    @patch("subprocess.run")
    def test_last_n_uses_config_default(self, mock_run, analyzer, tmp_path):
        mock_run.side_effect = [
            subprocess.CompletedProcess(args=[], returncode=0, stdout="true\n", stderr=""),
            subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr=""),
        ]

        analyzer.analyze(tmp_path, scope="last_n")

        # Verify the git log command used -50 (from config)
        log_call = mock_run.call_args_list[1]
        assert "-50" in log_call.args[0]


class TestAnalyzeScopeSinceLast:

    @patch("subprocess.run")
    def test_since_last_with_timestamp(self, mock_run, analyzer, tmp_path):
        since = datetime(2026, 1, 28, 0, 0, 0, tzinfo=timezone.utc)
        mock_run.side_effect = [
            subprocess.CompletedProcess(args=[], returncode=0, stdout="true\n", stderr=""),
            subprocess.CompletedProcess(
                args=[], returncode=0,
                stdout=_make_log_entry("abc123", "Recent commit", "Alice", "2026-01-30T10:00:00+00:00"),
                stderr="",
            ),
            subprocess.CompletedProcess(args=[], returncode=0, stdout="file.py\n", stderr=""),
        ]

        result = analyzer.analyze(tmp_path, scope="since_last", since_timestamp=since)

        assert result.scope_used == "since_last"
        assert result.total_commit_count == 1

    @patch("subprocess.run")
    def test_since_last_falls_back_to_last_n(self, mock_run, analyzer, tmp_path):
        mock_run.side_effect = [
            subprocess.CompletedProcess(args=[], returncode=0, stdout="true\n", stderr=""),
            subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr=""),
        ]

        result = analyzer.analyze(tmp_path, scope="since_last")  # No timestamp

        assert result.scope_used == "last_n"


class TestAnalyzeScopeTimeBased:

    @patch("subprocess.run")
    def test_time_based_scope(self, mock_run, analyzer, tmp_path):
        mock_run.side_effect = [
            subprocess.CompletedProcess(args=[], returncode=0, stdout="true\n", stderr=""),
            subprocess.CompletedProcess(
                args=[], returncode=0,
                stdout=_make_log_entry("abc123", "Recent", "Alice", "2026-01-30T10:00:00+00:00"),
                stderr="",
            ),
            subprocess.CompletedProcess(args=[], returncode=0, stdout="file.py\n", stderr=""),
        ]

        result = analyzer.analyze(tmp_path, scope="time_based", days=14)

        assert result.scope_used == "time_based"
        # Verify --since=14.days.ago was used
        log_call = mock_run.call_args_list[1]
        assert "--since=14.days.ago" in log_call.args[0]


class TestMaxCommitCap:

    @patch("subprocess.run")
    def test_truncation_when_over_cap(self, mock_run, small_cap_analyzer, tmp_path):
        entries = _make_log_output(*[
            _make_log_entry(f"hash{i}", f"Commit {i}", "Alice", f"2026-01-{30-i:02d}T10:00:00+00:00")
            for i in range(5)
        ])

        mock_run.side_effect = [
            subprocess.CompletedProcess(args=[], returncode=0, stdout="true\n", stderr=""),
            subprocess.CompletedProcess(args=[], returncode=0, stdout=entries, stderr=""),
            # 3 diff-tree calls (cap=3)
            subprocess.CompletedProcess(args=[], returncode=0, stdout="a.py\n", stderr=""),
            subprocess.CompletedProcess(args=[], returncode=0, stdout="b.py\n", stderr=""),
            subprocess.CompletedProcess(args=[], returncode=0, stdout="c.py\n", stderr=""),
        ]

        result = small_cap_analyzer.analyze(tmp_path, scope="last_n", last_n=10)

        assert result.total_commit_count == 3
        assert result.truncated is True

    @patch("subprocess.run")
    def test_no_truncation_under_cap(self, mock_run, analyzer, tmp_path):
        entries = _make_log_entry("hash1", "Single", "Alice", "2026-01-30T10:00:00+00:00")

        mock_run.side_effect = [
            subprocess.CompletedProcess(args=[], returncode=0, stdout="true\n", stderr=""),
            subprocess.CompletedProcess(args=[], returncode=0, stdout=entries, stderr=""),
            subprocess.CompletedProcess(args=[], returncode=0, stdout="file.py\n", stderr=""),
        ]

        result = analyzer.analyze(tmp_path, scope="last_n", last_n=5)

        assert result.total_commit_count == 1
        assert result.truncated is False


class TestEdgeCases:

    def test_nonexistent_path_raises(self, analyzer):
        with pytest.raises(GitAnalyzerError, match="does not exist"):
            analyzer.analyze("/nonexistent/path/that/does/not/exist")

    @patch("subprocess.run")
    def test_not_git_repo_raises(self, mock_run, analyzer, tmp_path):
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=128, stdout="", stderr="fatal: not a git repo"
        )
        with pytest.raises(GitAnalyzerError, match="Not a git repository"):
            analyzer.analyze(tmp_path)

    def test_unknown_scope_raises(self, analyzer, tmp_path):
        with pytest.raises(GitAnalyzerError, match="Unknown scope"):
            # Need to mock _is_git_repo to get past the check
            with patch.object(analyzer, "_is_git_repo", return_value=True):
                analyzer.analyze(tmp_path, scope="invalid_scope")

    @patch("subprocess.run")
    def test_empty_repo_returns_empty_result(self, mock_run, analyzer, tmp_path):
        mock_run.side_effect = [
            subprocess.CompletedProcess(args=[], returncode=0, stdout="true\n", stderr=""),
            subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr=""),
        ]

        result = analyzer.analyze(tmp_path, scope="last_n")

        assert result.total_commit_count == 0
        assert result.commits == []
        assert result.unique_files_changed == []
        assert result.unique_authors == []
        assert result.date_range_start is None
        assert result.date_range_end is None

    @patch("subprocess.run")
    def test_files_changed_failure_returns_empty_list(self, mock_run, analyzer, tmp_path):
        mock_run.side_effect = [
            subprocess.CompletedProcess(args=[], returncode=0, stdout="true\n", stderr=""),
            subprocess.CompletedProcess(
                args=[], returncode=0,
                stdout=_make_log_entry("abc123", "Commit", "Alice", "2026-01-30T10:00:00+00:00"),
                stderr="",
            ),
            subprocess.CompletedProcess(
                args=[], returncode=1, stdout="", stderr="error getting diff"
            ),
        ]

        result = analyzer.analyze(tmp_path, scope="last_n")

        assert result.total_commit_count == 1
        assert result.commits[0].files_changed == []


class TestDateRange:

    @patch("subprocess.run")
    def test_date_range_set_correctly(self, mock_run, analyzer, tmp_path):
        entries = _make_log_output(
            _make_log_entry("aaa", "Newest", "Alice", "2026-01-31T10:00:00+00:00"),
            _make_log_entry("bbb", "Oldest", "Bob", "2026-01-25T08:00:00+00:00"),
        )

        mock_run.side_effect = [
            subprocess.CompletedProcess(args=[], returncode=0, stdout="true\n", stderr=""),
            subprocess.CompletedProcess(args=[], returncode=0, stdout=entries, stderr=""),
            subprocess.CompletedProcess(args=[], returncode=0, stdout="a.py\n", stderr=""),
            subprocess.CompletedProcess(args=[], returncode=0, stdout="b.py\n", stderr=""),
        ]

        result = analyzer.analyze(tmp_path, scope="last_n")

        assert result.date_range_end.day == 31  # Most recent (first commit)
        assert result.date_range_start.day == 25  # Oldest (last commit)


class TestUniqueAggregation:

    @patch("subprocess.run")
    def test_unique_files_and_authors(self, mock_run, analyzer, tmp_path):
        entries = _make_log_output(
            _make_log_entry("aaa", "Commit 1", "Alice", "2026-01-31T10:00:00+00:00"),
            _make_log_entry("bbb", "Commit 2", "Alice", "2026-01-30T10:00:00+00:00"),
            _make_log_entry("ccc", "Commit 3", "Bob", "2026-01-29T10:00:00+00:00"),
        )

        mock_run.side_effect = [
            subprocess.CompletedProcess(args=[], returncode=0, stdout="true\n", stderr=""),
            subprocess.CompletedProcess(args=[], returncode=0, stdout=entries, stderr=""),
            subprocess.CompletedProcess(args=[], returncode=0, stdout="shared.py\na.py\n", stderr=""),
            subprocess.CompletedProcess(args=[], returncode=0, stdout="shared.py\nb.py\n", stderr=""),
            subprocess.CompletedProcess(args=[], returncode=0, stdout="shared.py\nc.py\n", stderr=""),
        ]

        result = analyzer.analyze(tmp_path, scope="last_n")

        assert len(result.unique_authors) == 2
        assert "Alice" in result.unique_authors
        assert "Bob" in result.unique_authors
        assert len(result.unique_files_changed) == 4  # shared.py, a.py, b.py, c.py


class TestDefaultConfig:

    def test_default_config_values(self):
        analyzer = GitAnalyzer(config={})
        assert analyzer._max_commits == 200
        assert analyzer._last_n_count == 50
        assert analyzer._time_based_days == 7

    def test_none_config(self):
        analyzer = GitAnalyzer(config=None)
        assert analyzer._max_commits == 200
