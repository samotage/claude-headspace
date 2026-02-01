"""Progress summary service for generating LLM-powered narrative summaries from git history."""

import logging
import re
import threading
from datetime import datetime, timezone
from pathlib import Path

from ..config import get_value
from .git_analyzer import GitAnalyzer, GitAnalysisResult, GitAnalyzerError
from .inference_service import InferenceService, InferenceServiceError
from .prompt_registry import build_prompt

logger = logging.getLogger(__name__)

SUMMARY_DIR = "docs/brain_reboot"
SUMMARY_FILENAME = "progress_summary.md"
ARCHIVE_DIR = "archive"


class ProgressSummaryService:
    """Generates narrative progress summaries from git commit history via LLM inference.

    Orchestrates GitAnalyzer + InferenceService + file I/O.
    Writes progress_summary.md to target project's docs/brain_reboot/ directory.
    """

    def __init__(self, inference_service: InferenceService, app=None):
        self._inference = inference_service
        self._app = app
        self._config = app.config.get("APP_CONFIG", {}) if app else {}
        self._git_analyzer = GitAnalyzer(config=self._config)

        # Concurrent generation guard
        self._lock = threading.Lock()
        self._in_progress: set[int] = set()

    def generate(self, project, scope: str | None = None) -> dict:
        """Generate a progress summary for a project.

        Args:
            project: Project model instance (must have .id, .name, .path)
            scope: Override scope ('since_last', 'last_n', 'time_based')

        Returns:
            Dict with summary content, metadata, and status
        """
        project_id = project.id
        project_name = project.name
        project_path = project.path

        if not project_path:
            return {"error": "Project has no filesystem path", "status": "error"}

        # Check concurrent guard
        with self._lock:
            if project_id in self._in_progress:
                return {"error": "Generation already in progress", "status": "in_progress"}
            self._in_progress.add(project_id)

        try:
            return self._do_generate(project_id, project_name, project_path, scope)
        finally:
            with self._lock:
                self._in_progress.discard(project_id)

    def _do_generate(
        self, project_id: int, project_name: str, project_path: str, scope: str | None
    ) -> dict:
        """Internal generation logic."""
        effective_scope = scope or get_value(
            self._config, "progress_summary", "default_scope", default="since_last"
        )

        # Parse since_timestamp from existing summary if using since_last
        since_timestamp = None
        if effective_scope == "since_last":
            since_timestamp = self._get_last_generation_timestamp(project_path)

        # Run git analysis
        try:
            analysis = self._git_analyzer.analyze(
                repo_path=project_path,
                scope=effective_scope,
                since_timestamp=since_timestamp,
            )
        except GitAnalyzerError as e:
            logger.error(f"Git analysis failed for {project_name}: {e}")
            return {"error": str(e), "status": "error"}

        # Handle empty scope
        if analysis.total_commit_count == 0:
            return {
                "message": "No commits found in configured scope",
                "status": "empty",
                "scope_used": analysis.scope_used,
            }

        # Build prompt and call inference
        prompt = self._build_prompt(project_name, analysis)

        try:
            result = self._inference.infer(
                level="project",
                purpose="progress_summary",
                input_text=prompt,
                project_id=project_id,
            )
        except (InferenceServiceError, Exception) as e:
            logger.error(f"Inference failed for progress summary ({project_name}): {e}")
            return {"error": f"Inference failed: {e}", "status": "error"}

        # Build metadata
        now = datetime.now(timezone.utc)
        metadata = {
            "generated_at": now.isoformat(),
            "scope": analysis.scope_used,
            "date_range_start": analysis.date_range_start.isoformat() if analysis.date_range_start else None,
            "date_range_end": analysis.date_range_end.isoformat() if analysis.date_range_end else None,
            "commit_count": analysis.total_commit_count,
            "truncated": analysis.truncated,
        }

        # Write to file
        try:
            self._write_summary(project_path, result.text, metadata)
        except (PermissionError, OSError) as e:
            logger.error(f"Failed to write progress summary for {project_name}: {e}")
            return {
                "error": f"File write failed: {e}",
                "status": "error",
                "summary": result.text,
                "metadata": metadata,
            }

        return {
            "summary": result.text,
            "metadata": metadata,
            "status": "success",
        }

    def get_current_summary(self, project) -> dict:
        """Read the current progress summary for a project.

        Args:
            project: Project model instance

        Returns:
            Dict with summary content and metadata, or error
        """
        project_path = project.path
        if not project_path:
            return {"error": "Project has no filesystem path", "status": "error"}

        summary_path = Path(project_path) / SUMMARY_DIR / SUMMARY_FILENAME
        if not summary_path.exists():
            return {"status": "not_found"}

        try:
            content = summary_path.read_text(encoding="utf-8")
        except (PermissionError, OSError) as e:
            return {"error": f"Failed to read summary: {e}", "status": "error"}

        # Parse metadata from frontmatter
        metadata = self._parse_metadata(content)
        # Strip frontmatter from content for display
        body = self._strip_frontmatter(content)

        return {
            "summary": body,
            "metadata": metadata,
            "status": "found",
        }

    def is_generating(self, project_id: int) -> bool:
        """Check if generation is in progress for a project."""
        with self._lock:
            return project_id in self._in_progress

    def _build_prompt(self, project_name: str, analysis: GitAnalysisResult) -> str:
        """Build the inference prompt from git analysis results."""
        date_range = "N/A"
        if analysis.date_range_start and analysis.date_range_end:
            date_range = (
                f"{analysis.date_range_start.strftime('%Y-%m-%d')} to "
                f"{analysis.date_range_end.strftime('%Y-%m-%d')}"
            )

        commit_details = []
        for c in analysis.commits[:100]:  # Limit to first 100 for prompt size
            files_str = ", ".join(c.files_changed[:10])
            if len(c.files_changed) > 10:
                files_str += f" (+{len(c.files_changed) - 10} more)"
            commit_details.append(
                f"- [{c.hash[:8]}] {c.message} (by {c.author}, {c.timestamp.strftime('%Y-%m-%d')})"
                f"\n  Files: {files_str}"
            )

        commits_text = "\n".join(commit_details)
        files_text = "\n".join(f"- {f}" for f in analysis.unique_files_changed[:50])

        analysis_text = (
            f"Date range: {date_range}\n"
            f"Total commits: {analysis.total_commit_count}\n"
            f"Authors: {', '.join(analysis.unique_authors)}\n\n"
            f"Commit history:\n{commits_text}\n\n"
            f"Key files changed:\n{files_text}"
        )

        return build_prompt(
            "progress_summary",
            project_name=project_name,
            analysis_text=analysis_text,
        )

    def _write_summary(self, project_path: str, content: str, metadata: dict) -> None:
        """Write progress summary to the target project filesystem.

        Archives existing summary before overwriting.
        """
        base_dir = Path(project_path) / SUMMARY_DIR
        summary_path = base_dir / SUMMARY_FILENAME

        # Ensure directories exist
        self._ensure_directory(base_dir)
        self._ensure_directory(base_dir / ARCHIVE_DIR)

        # Archive existing before overwriting
        if summary_path.exists():
            self._archive_existing(base_dir, summary_path)

        # Build file content with metadata header
        frontmatter = self._build_frontmatter(metadata)
        full_content = f"{frontmatter}\n{content}\n"

        summary_path.write_text(full_content, encoding="utf-8")
        logger.info(f"Progress summary written to {summary_path}")

    def _archive_existing(self, base_dir: Path, summary_path: Path) -> None:
        """Archive the current progress summary with date-stamped filename."""
        archive_dir = base_dir / ARCHIVE_DIR
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        # Base archive name
        archive_name = f"progress_summary_{today}.md"
        archive_path = archive_dir / archive_name

        # Handle same-day suffix
        if archive_path.exists():
            suffix = 2
            while True:
                archive_name = f"progress_summary_{today}_{suffix}.md"
                archive_path = archive_dir / archive_name
                if not archive_path.exists():
                    break
                suffix += 1

        # Copy current to archive (not move, to preserve original on write failure)
        existing_content = summary_path.read_text(encoding="utf-8")
        archive_path.write_text(existing_content, encoding="utf-8")
        logger.info(f"Archived previous summary to {archive_path}")

    @staticmethod
    def _ensure_directory(path: Path) -> None:
        """Create directory if it doesn't exist."""
        path.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _build_frontmatter(metadata: dict) -> str:
        """Build YAML frontmatter string from metadata dict."""
        lines = ["---"]
        for key, value in metadata.items():
            if value is None:
                lines.append(f"{key}: null")
            elif isinstance(value, bool):
                lines.append(f"{key}: {'true' if value else 'false'}")
            else:
                lines.append(f"{key}: {value}")
        lines.append("---")
        return "\n".join(lines)

    @staticmethod
    def _parse_metadata(content: str) -> dict:
        """Parse YAML frontmatter from summary content."""
        match = re.match(r"^---\s*\n(.*?)\n---\s*\n", content, re.DOTALL)
        if not match:
            return {}

        metadata = {}
        for line in match.group(1).strip().split("\n"):
            if ":" in line:
                key, _, value = line.partition(":")
                value = value.strip()
                if value == "null":
                    value = None
                elif value == "true":
                    value = True
                elif value == "false":
                    value = False
                metadata[key.strip()] = value
        return metadata

    @staticmethod
    def _strip_frontmatter(content: str) -> str:
        """Remove YAML frontmatter from content."""
        match = re.match(r"^---\s*\n.*?\n---\s*\n", content, re.DOTALL)
        if match:
            return content[match.end():].strip()
        return content.strip()

    def _get_last_generation_timestamp(self, project_path: str) -> datetime | None:
        """Extract the generation timestamp from existing progress_summary.md."""
        summary_path = Path(project_path) / SUMMARY_DIR / SUMMARY_FILENAME
        if not summary_path.exists():
            return None

        try:
            content = summary_path.read_text(encoding="utf-8")
            metadata = self._parse_metadata(content)
            generated_at = metadata.get("generated_at")
            if generated_at and isinstance(generated_at, str):
                return datetime.fromisoformat(generated_at)
        except Exception as e:
            logger.warning(f"Failed to parse generation timestamp: {e}")

        return None
