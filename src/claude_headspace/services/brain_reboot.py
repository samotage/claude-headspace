"""Brain reboot service for generating context restoration documents."""

import logging
import os
from datetime import datetime, timezone
from pathlib import Path

from ..config import get_value
from .path_constants import BRAIN_REBOOT_DIR, SUMMARY_FILENAME, WAYPOINT_FILENAME

logger = logging.getLogger(__name__)


class BrainRebootService:
    """
    Generates brain reboot documents by combining waypoint and progress
    summary artifacts. No LLM calls — pure file composition.
    """

    def __init__(self, app=None, archive_service=None):
        """
        Initialize the brain reboot service.

        Args:
            app: Flask application instance for config access
            archive_service: Archive service for archiving artifacts on export
        """
        self._app = app
        self._archive_service = archive_service
        config = app.config.get("APP_CONFIG", {}) if app else {}
        self._export_filename = get_value(
            config, "brain_reboot", "export_filename", default="brain_reboot.md"
        )
        # In-memory cache of last generated brain reboot per project
        self._cache = {}  # project_id -> dict

    def generate(self, project) -> dict:
        """
        Generate a brain reboot document for a project.

        Reads the project's waypoint and progress summary, composes them
        into a formatted context restoration document.

        Args:
            project: Project model instance with id, name, path

        Returns:
            Dict with content, metadata, status, has_waypoint, has_summary
        """
        project_path = project.path

        waypoint_content = self._read_waypoint(project_path)
        summary_content = self._read_progress_summary(project_path)

        has_waypoint = waypoint_content is not None
        has_summary = summary_content is not None

        now = datetime.now(timezone.utc)

        content = self._format_document(
            project_name=project.name,
            waypoint_content=waypoint_content,
            summary_content=summary_content,
        )

        result = {
            "content": content,
            "metadata": {
                "generated_at": now.isoformat(),
                "project_name": project.name,
                "has_waypoint": has_waypoint,
                "has_summary": has_summary,
            },
            "status": "generated",
            "has_waypoint": has_waypoint,
            "has_summary": has_summary,
        }

        # Cache the result
        self._cache[project.id] = result

        return result

    def _read_waypoint(self, project_path: str) -> str | None:
        """
        Read waypoint content from a project's brain reboot directory.

        Args:
            project_path: Path to the project root

        Returns:
            Waypoint content string, or None if not found
        """
        path = Path(project_path) / BRAIN_REBOOT_DIR / WAYPOINT_FILENAME
        try:
            if path.exists():
                content = path.read_text(encoding="utf-8").strip()
                if content:
                    return content
            return None
        except (PermissionError, OSError) as e:
            logger.warning(f"Could not read waypoint at {path}: {e}")
            return None

    def _read_progress_summary(self, project_path: str) -> str | None:
        """
        Read progress summary content from a project's brain reboot directory.

        Strips YAML frontmatter if present (progress summaries have
        metadata headers).

        Args:
            project_path: Path to the project root

        Returns:
            Progress summary body content, or None if not found
        """
        path = Path(project_path) / BRAIN_REBOOT_DIR / SUMMARY_FILENAME
        try:
            if path.exists():
                content = path.read_text(encoding="utf-8").strip()
                if content:
                    return self._strip_frontmatter(content)
            return None
        except (PermissionError, OSError) as e:
            logger.warning(f"Could not read progress summary at {path}: {e}")
            return None

    def _strip_frontmatter(self, content: str) -> str:
        """
        Strip YAML frontmatter from content if present.

        Args:
            content: Raw file content

        Returns:
            Content without frontmatter
        """
        if content.startswith("---"):
            parts = content.split("---", 2)
            if len(parts) >= 3:
                return parts[2].strip()
        return content

    def _format_document(
        self,
        project_name: str,
        waypoint_content: str | None,
        summary_content: str | None,
    ) -> str:
        """
        Format the brain reboot document from available artifacts.

        Args:
            project_name: Name of the project
            waypoint_content: Waypoint markdown content or None
            summary_content: Progress summary content or None

        Returns:
            Formatted brain reboot markdown document
        """
        now = datetime.now(timezone.utc)
        timestamp = now.strftime("%Y-%m-%d %H:%M UTC")

        lines = [
            f"# Brain Reboot: {project_name}",
            "",
            f"Generated: {timestamp}",
            "",
        ]

        has_waypoint = waypoint_content is not None
        has_summary = summary_content is not None

        if not has_waypoint and not has_summary:
            lines.extend([
                "## No Artifacts Available",
                "",
                "Neither a progress summary nor a waypoint has been created for this project yet.",
                "",
                "**To get started:**",
                "- **Progress Summary:** Click the \"Generate Progress Summary\" button below to create one from git history",
                "- **Waypoint:** Use the waypoint editor to define your project's path ahead",
                "",
            ])
        else:
            # Waypoint first (path ahead context before progress)
            lines.append("## Waypoint (Path Ahead)")
            lines.append("")
            if has_waypoint:
                lines.append(waypoint_content)
            else:
                lines.append("*Waypoint is not yet available. Use the waypoint editor to define your project's path ahead.*")
            lines.append("")

            # Progress summary second
            lines.append("## Progress Summary")
            lines.append("")
            if has_summary:
                lines.append(summary_content)
            else:
                lines.append("*Progress summary is not yet available. Click \"Generate Progress Summary\" below to create one from git history.*")
            lines.append("")

        lines.extend([
            "---",
            "",
            "_Use this document to quickly restore context when returning to this project._",
            "",
        ])

        return "\n".join(lines)

    def export(self, project, content: str) -> dict:
        """
        Export brain reboot content to the target project's filesystem.

        Archives previous brain_reboot and cascades to archive waypoint
        and progress_summary before writing new content.

        Args:
            project: Project model instance with path
            content: Brain reboot markdown content to write

        Returns:
            Dict with success, path, error, archived
        """
        project_path = Path(project.path)
        brain_reboot_dir = project_path / BRAIN_REBOOT_DIR
        export_path = brain_reboot_dir / self._export_filename
        archived = {}

        try:
            # Create directory structure if missing
            brain_reboot_dir.mkdir(parents=True, exist_ok=True)

            # Cascading archive: archive all three artifacts before overwrite
            if self._archive_service is not None:
                try:
                    archived = self._archive_service.archive_cascade(project.path)
                except Exception as e:
                    logger.warning(f"Cascade archive failed (non-blocking): {e}")

            # Write file (overwrite if exists)
            export_path.write_text(content, encoding="utf-8")

            logger.info(f"Exported brain reboot to {export_path}")
            return {
                "success": True,
                "path": str(export_path),
                "error": None,
                "archived": archived,
            }
        except PermissionError as e:
            error_msg = f"Permission denied writing to {export_path}"
            logger.error(f"{error_msg}: {e}")
            return {
                "success": False,
                "path": str(export_path),
                "error": error_msg,
                "archived": archived,
            }
        except OSError as e:
            error_msg = f"Failed to write brain reboot: {e}"
            logger.error(error_msg)
            return {
                "success": False,
                "path": str(export_path),
                "error": error_msg,
                "archived": archived,
            }

    def get_last_generated(self, project_id: int) -> dict | None:
        """
        Return the last generated brain reboot for a project.

        Args:
            project_id: Project ID

        Returns:
            Cached result dict, or None if never generated
        """
        return self._cache.get(project_id)
