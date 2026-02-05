"""Git analyzer for extracting structured commit history from target project repositories."""

import logging
import re
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

# Delimiter for structured git log parsing
COMMIT_DELIMITER = "---COMMIT_DELIMITER---"
FIELD_DELIMITER = "---FIELD---"

# git log format: hash, message, author, timestamp, files changed
GIT_LOG_FORMAT = FIELD_DELIMITER.join(["%H", "%s", "%an", "%aI"]) + COMMIT_DELIMITER


@dataclass
class CommitInfo:
    """Structured representation of a single git commit."""

    hash: str
    message: str
    author: str
    timestamp: datetime
    files_changed: list[str] = field(default_factory=list)


@dataclass
class GitAnalysisResult:
    """Result of analyzing git history for a project."""

    commits: list[CommitInfo] = field(default_factory=list)
    unique_files_changed: list[str] = field(default_factory=list)
    unique_authors: list[str] = field(default_factory=list)
    date_range_start: datetime | None = None
    date_range_end: datetime | None = None
    total_commit_count: int = 0
    scope_used: str = ""
    truncated: bool = False


class GitAnalyzerError(Exception):
    """Error during git analysis."""

    pass


class GitAnalyzer:
    """Extracts structured commit history from git repositories.

    This is a standalone utility class with no Flask dependencies.
    Uses subprocess.run with git log for read-only commit extraction.
    """

    def __init__(self, config: dict | None = None):
        from ..config import get_value

        self._config = config or {}
        self._max_commits = get_value(
            self._config, "progress_summary", "max_commits", default=200
        )
        self._last_n_count = get_value(
            self._config, "progress_summary", "last_n_count", default=50
        )
        self._time_based_days = get_value(
            self._config, "progress_summary", "time_based_days", default=7
        )

    def analyze(
        self,
        repo_path: str | Path,
        scope: str = "since_last",
        since_timestamp: datetime | None = None,
        last_n: int | None = None,
        days: int | None = None,
    ) -> GitAnalysisResult:
        """Analyze git history for a repository.

        Args:
            repo_path: Path to the git repository
            scope: One of 'since_last', 'last_n', 'time_based'
            since_timestamp: For 'since_last' scope, the timestamp to start from
            last_n: Override for number of commits in 'last_n' scope
            days: Override for number of days in 'time_based' scope

        Returns:
            GitAnalysisResult with structured commit data

        Raises:
            GitAnalyzerError: If the path is not a git repository or git fails
        """
        repo_path = Path(repo_path)

        if not repo_path.exists():
            raise GitAnalyzerError(f"Repository path does not exist: {repo_path}")

        # Verify it's a git repository
        if not self._is_git_repo(repo_path):
            raise GitAnalyzerError(f"Not a git repository: {repo_path}")

        if scope == "since_last":
            if since_timestamp:
                commits = self._get_commits_since(repo_path, since_timestamp)
                scope_used = "since_last"
            else:
                # Fall back to last_n
                n = last_n or self._last_n_count
                commits = self._get_commits_last_n(repo_path, n)
                scope_used = "last_n"
        elif scope == "last_n":
            n = last_n or self._last_n_count
            commits = self._get_commits_last_n(repo_path, n)
            scope_used = "last_n"
        elif scope == "time_based":
            d = days or self._time_based_days
            commits = self._get_commits_time_based(repo_path, d)
            scope_used = "time_based"
        else:
            raise GitAnalyzerError(f"Unknown scope: {scope}")

        # Enforce maximum commit cap
        truncated = False
        if len(commits) > self._max_commits:
            commits = commits[: self._max_commits]
            truncated = True

        # Get files changed for all commits in a single subprocess call
        if commits:
            files_map = self._get_files_changed_batch(
                repo_path, [c.hash for c in commits]
            )
            for commit in commits:
                commit.files_changed = files_map.get(commit.hash, [])

        # Build result
        all_files = set()
        all_authors = set()
        for c in commits:
            all_files.update(c.files_changed)
            all_authors.add(c.author)

        return GitAnalysisResult(
            commits=commits,
            unique_files_changed=sorted(all_files),
            unique_authors=sorted(all_authors),
            date_range_start=commits[-1].timestamp if commits else None,
            date_range_end=commits[0].timestamp if commits else None,
            total_commit_count=len(commits),
            scope_used=scope_used,
            truncated=truncated,
        )

    def _is_git_repo(self, repo_path: Path) -> bool:
        """Check if the path is a valid git repository."""
        try:
            result = self._run_git(
                repo_path, ["rev-parse", "--is-inside-work-tree"]
            )
            return result.strip() == "true"
        except GitAnalyzerError:
            return False

    def _run_git(self, repo_path: Path, args: list[str]) -> str:
        """Run a git command and return stdout.

        Args:
            repo_path: Working directory for git command
            args: Git command arguments (without 'git' prefix)

        Returns:
            Command stdout as string

        Raises:
            GitAnalyzerError: If git command fails
        """
        cmd = ["git"] + args
        try:
            result = subprocess.run(
                cmd,
                cwd=str(repo_path),
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode != 0:
                stderr = result.stderr.strip()
                raise GitAnalyzerError(f"Git command failed: {stderr}")
            return result.stdout
        except subprocess.TimeoutExpired:
            raise GitAnalyzerError("Git command timed out after 30 seconds")
        except FileNotFoundError:
            raise GitAnalyzerError("Git is not installed or not in PATH")
        except PermissionError:
            raise GitAnalyzerError(f"Permission denied accessing: {repo_path}")
        except OSError as e:
            raise GitAnalyzerError(f"OS error running git: {e}")

    def _parse_git_log(self, raw_output: str) -> list[CommitInfo]:
        """Parse structured git log output into CommitInfo objects.

        Args:
            raw_output: Raw output from git log with custom format

        Returns:
            List of CommitInfo objects (most recent first)
        """
        commits = []
        if not raw_output.strip():
            return commits

        entries = raw_output.strip().split(COMMIT_DELIMITER)
        for entry in entries:
            entry = entry.strip()
            if not entry:
                continue

            fields = entry.split(FIELD_DELIMITER)
            if len(fields) < 4:
                logger.warning(f"Skipping malformed commit entry: {entry[:100]}")
                continue

            commit_hash = fields[0].strip()
            message = fields[1].strip()
            author = fields[2].strip()
            timestamp_str = fields[3].strip()

            try:
                timestamp = datetime.fromisoformat(timestamp_str)
                # Ensure timezone-aware
                if timestamp.tzinfo is None:
                    timestamp = timestamp.replace(tzinfo=timezone.utc)
            except (ValueError, TypeError):
                logger.warning(f"Skipping commit with invalid timestamp: {timestamp_str}")
                continue

            commits.append(
                CommitInfo(
                    hash=commit_hash,
                    message=message,
                    author=author,
                    timestamp=timestamp,
                )
            )

        return commits

    def _get_commits_since(
        self, repo_path: Path, since: datetime
    ) -> list[CommitInfo]:
        """Get commits since a specific timestamp."""
        since_str = since.isoformat()
        output = self._run_git(
            repo_path,
            ["log", f"--format={GIT_LOG_FORMAT}", f"--since={since_str}"],
        )
        return self._parse_git_log(output)

    def _get_commits_last_n(self, repo_path: Path, n: int) -> list[CommitInfo]:
        """Get the most recent N commits."""
        output = self._run_git(
            repo_path,
            ["log", f"--format={GIT_LOG_FORMAT}", f"-{n}"],
        )
        return self._parse_git_log(output)

    def _get_commits_time_based(
        self, repo_path: Path, days: int
    ) -> list[CommitInfo]:
        """Get commits within the last N days."""
        output = self._run_git(
            repo_path,
            ["log", f"--format={GIT_LOG_FORMAT}", f"--since={days}.days.ago"],
        )
        return self._parse_git_log(output)

    def _get_files_changed_batch(
        self, repo_path: Path, commit_hashes: list[str]
    ) -> dict[str, list[str]]:
        """Get files changed for multiple commits in a single subprocess call.

        Uses `git log --name-only --format=%H` with explicit commit list to
        retrieve all file listings at once, replacing N subprocess calls with 1.

        Args:
            repo_path: Path to the git repository
            commit_hashes: List of commit hashes to get files for

        Returns:
            Dict mapping commit_hash -> list of changed file paths
        """
        if not commit_hashes:
            return {}

        try:
            # Use --stdin to pass commit hashes, --name-only for file lists,
            # --format=%H to identify which commit the files belong to,
            # --no-walk to avoid traversing parents.
            output = self._run_git(
                repo_path,
                ["log", "--no-walk", "--name-only", "--format=%H"] + commit_hashes,
            )
        except GitAnalyzerError:
            logger.warning("Failed to batch-fetch files changed; falling back to empty")
            return {}

        result: dict[str, list[str]] = {}
        current_hash = None

        for line in output.split("\n"):
            line = line.strip()
            if not line:
                continue
            # A 40-char hex string is a commit hash
            if len(line) == 40 and all(c in "0123456789abcdef" for c in line):
                current_hash = line
                if current_hash not in result:
                    result[current_hash] = []
            elif current_hash:
                result[current_hash].append(line)

        return result

    def _get_files_changed(self, repo_path: Path, commit_hash: str) -> list[str]:
        """Get list of files changed in a specific commit."""
        try:
            output = self._run_git(
                repo_path,
                ["diff-tree", "--no-commit-id", "--name-only", "-r", commit_hash],
            )
            return [f.strip() for f in output.strip().split("\n") if f.strip()]
        except GitAnalyzerError:
            logger.warning(f"Failed to get files for commit {commit_hash[:8]}")
            return []
