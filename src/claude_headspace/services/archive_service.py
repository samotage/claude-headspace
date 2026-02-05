"""Centralized archive service for brain_reboot artifacts."""

import logging
import os
import re
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

from ..config import get_value

logger = logging.getLogger(__name__)

ARCHIVE_DIR = "docs/brain_reboot/archive"
BRAIN_REBOOT_DIR = "docs/brain_reboot"

VALID_ARTIFACT_TYPES = ("waypoint", "progress_summary", "brain_reboot")

# Regex to parse archive filenames: {artifact}_{YYYY-MM-DD_HH-MM-SS}.md
ARCHIVE_FILENAME_RE = re.compile(
    r"^(waypoint|progress_summary|brain_reboot)_(\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2})\.md$"
)

TIMESTAMP_FORMAT = "%Y-%m-%d_%H-%M-%S"


class ArchiveService:
    """Centralized archive service for waypoint, progress_summary, and brain_reboot artifacts.

    Provides atomic archiving with second-precision UTC timestamps,
    configurable retention policies, and archive listing/retrieval.
    """

    def __init__(self, config: dict | None = None):
        config = config or {}
        self._enabled = get_value(config, "archive", "enabled", default=True)
        self._retention_policy = get_value(
            config, "archive", "retention", "policy", default="keep_all"
        )
        self._keep_last_n = get_value(
            config, "archive", "retention", "keep_last_n", default=10
        )
        self._retention_days = get_value(
            config, "archive", "retention", "days", default=90
        )

    def archive_artifact(
        self,
        project_path: str | Path,
        artifact_type: str,
        *,
        timestamp: datetime | None = None,
    ) -> str | None:
        """Archive a single artifact with second-precision UTC timestamp.

        Args:
            project_path: Path to the project root
            artifact_type: One of 'waypoint', 'progress_summary', 'brain_reboot'
            timestamp: Optional UTC timestamp (defaults to now)

        Returns:
            Relative archive path on success, None on failure or if source doesn't exist
        """
        if not self._enabled:
            return None

        if artifact_type not in VALID_ARTIFACT_TYPES:
            logger.error(f"Invalid artifact type: {artifact_type}")
            return None

        project_path = Path(project_path)
        source_path = project_path / BRAIN_REBOOT_DIR / f"{artifact_type}.md"

        if not source_path.exists():
            logger.debug(f"Source file does not exist, skipping archive: {source_path}")
            return None

        archive_dir = project_path / ARCHIVE_DIR
        archive_dir.mkdir(parents=True, exist_ok=True)

        ts = timestamp or datetime.now(timezone.utc)
        ts_str = ts.strftime(TIMESTAMP_FORMAT)
        archive_filename = f"{artifact_type}_{ts_str}.md"
        archive_file = archive_dir / archive_filename

        try:
            existing_content = source_path.read_text(encoding="utf-8")

            # Atomic write via tempfile + os.replace
            fd, temp_path = tempfile.mkstemp(
                suffix=".md",
                prefix=f"{artifact_type}_archive_",
                dir=archive_dir,
            )
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    f.write(existing_content)
                os.replace(temp_path, archive_file)
                logger.info(f"Archived {artifact_type} to {archive_file}")
            except Exception:
                if os.path.exists(temp_path):
                    os.unlink(temp_path)
                raise

            # Enforce retention policy after archiving
            try:
                self.enforce_retention(project_path, artifact_type)
            except Exception as e:
                logger.warning(f"Retention enforcement failed for {artifact_type}: {e}")

            # Return path relative to brain_reboot dir
            brain_reboot_dir = project_path / BRAIN_REBOOT_DIR
            return str(archive_file.relative_to(brain_reboot_dir))

        except Exception as e:
            logger.error(f"Failed to archive {artifact_type}: {e}")
            return None

    def archive_cascade(
        self,
        project_path: str | Path,
        *,
        timestamp: datetime | None = None,
    ) -> dict[str, str | None]:
        """Archive all three artifact types with a shared timestamp.

        Used during brain_reboot export to capture a point-in-time snapshot.
        Best-effort: failure to archive one artifact does not block others.

        Args:
            project_path: Path to the project root
            timestamp: Optional shared UTC timestamp (defaults to now)

        Returns:
            Dict mapping artifact_type to archive path (or None if failed/skipped)
        """
        ts = timestamp or datetime.now(timezone.utc)
        results = {}

        for artifact_type in VALID_ARTIFACT_TYPES:
            try:
                results[artifact_type] = self.archive_artifact(
                    project_path, artifact_type, timestamp=ts
                )
            except Exception as e:
                logger.error(f"Cascade archive failed for {artifact_type}: {e}")
                results[artifact_type] = None

        return results

    def enforce_retention(
        self,
        project_path: str | Path,
        artifact_type: str,
    ) -> int:
        """Apply configured retention policy for a specific artifact type.

        Args:
            project_path: Path to the project root
            artifact_type: One of 'waypoint', 'progress_summary', 'brain_reboot'

        Returns:
            Number of files deleted
        """
        if self._retention_policy == "keep_all":
            return 0

        archive_dir = Path(project_path) / ARCHIVE_DIR
        if not archive_dir.exists():
            return 0

        # List archives for this artifact type, sorted newest first
        archives = self._list_archives_for_type(archive_dir, artifact_type)
        if not archives:
            return 0

        to_delete = []

        if self._retention_policy == "keep_last_n":
            if len(archives) > self._keep_last_n:
                to_delete = archives[self._keep_last_n:]

        elif self._retention_policy == "time_based":
            cutoff = datetime.now(timezone.utc) - timedelta(days=self._retention_days)
            for entry in archives:
                if entry["timestamp"] < cutoff:
                    to_delete.append(entry)

        deleted = 0
        for entry in to_delete:
            try:
                entry["path"].unlink()
                deleted += 1
                logger.info(f"Retention cleanup: deleted {entry['path'].name}")
            except Exception as e:
                logger.warning(f"Failed to delete {entry['path'].name}: {e}")

        return deleted

    def list_archives(
        self,
        project_path: str | Path,
        artifact_type: str | None = None,
    ) -> dict[str, list[dict]]:
        """List archived versions grouped by artifact type.

        Args:
            project_path: Path to the project root
            artifact_type: Optional filter for a specific artifact type

        Returns:
            Dict mapping artifact_type to list of {filename, timestamp} dicts
        """
        archive_dir = Path(project_path) / ARCHIVE_DIR
        if not archive_dir.exists():
            return {t: [] for t in VALID_ARTIFACT_TYPES}

        types_to_list = [artifact_type] if artifact_type else list(VALID_ARTIFACT_TYPES)
        result = {}

        for atype in types_to_list:
            archives = self._list_archives_for_type(archive_dir, atype)
            result[atype] = [
                {
                    "filename": entry["path"].name,
                    "timestamp": entry["timestamp"].strftime("%Y-%m-%dT%H:%M:%SZ"),
                }
                for entry in archives
            ]

        # Fill missing types with empty lists
        for t in VALID_ARTIFACT_TYPES:
            if t not in result:
                result[t] = []

        return result

    def get_archive(
        self,
        project_path: str | Path,
        artifact_type: str,
        timestamp_str: str,
    ) -> dict | None:
        """Retrieve a specific archived version's content.

        Args:
            project_path: Path to the project root
            artifact_type: One of 'waypoint', 'progress_summary', 'brain_reboot'
            timestamp_str: Timestamp in YYYY-MM-DD_HH-MM-SS format

        Returns:
            Dict with artifact, timestamp, filename, content — or None if not found
        """
        if artifact_type not in VALID_ARTIFACT_TYPES:
            return None

        # Validate timestamp format to prevent path traversal
        expected_filename = f"{artifact_type}_{timestamp_str}.md"
        if not ARCHIVE_FILENAME_RE.match(expected_filename):
            logger.warning(f"Invalid archive timestamp format: {timestamp_str}")
            return None

        archive_dir = Path(project_path) / ARCHIVE_DIR
        archive_path = archive_dir / expected_filename

        # Ensure resolved path stays within archive_dir
        try:
            archive_path.resolve().relative_to(archive_dir.resolve())
        except ValueError:
            logger.warning(f"Path traversal attempt blocked: {timestamp_str}")
            return None

        if not archive_path.exists():
            return None

        try:
            content = archive_path.read_text(encoding="utf-8")
            # Parse timestamp
            ts = datetime.strptime(timestamp_str, TIMESTAMP_FORMAT).replace(
                tzinfo=timezone.utc
            )
            return {
                "artifact": artifact_type,
                "timestamp": ts.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "filename": expected_filename,
                "content": content,
            }
        except Exception as e:
            logger.error(f"Failed to read archive {archive_path}: {e}")
            return None

    def _list_archives_for_type(
        self, archive_dir: Path, artifact_type: str
    ) -> list[dict]:
        """List archive files for a specific artifact type, sorted newest first.

        Returns list of dicts with 'path' (Path) and 'timestamp' (datetime).
        """
        archives = []
        prefix = f"{artifact_type}_"

        for f in archive_dir.iterdir():
            if not f.is_file() or not f.name.startswith(prefix):
                continue
            match = ARCHIVE_FILENAME_RE.match(f.name)
            if match and match.group(1) == artifact_type:
                ts = datetime.strptime(match.group(2), TIMESTAMP_FORMAT).replace(
                    tzinfo=timezone.utc
                )
                archives.append({"path": f, "timestamp": ts})

        archives.sort(key=lambda x: x["timestamp"], reverse=True)
        return archives
