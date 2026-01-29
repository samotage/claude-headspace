"""Waypoint editor service for loading, saving, and archiving waypoints."""

import logging
import os
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

# Default waypoint template
DEFAULT_TEMPLATE = """# Waypoint

## Next Up

<!-- Immediate next steps -->

## Upcoming

<!-- Coming soon -->

## Later

<!-- Future work -->

## Not Now

<!-- Parked/deprioritised -->
"""


@dataclass
class WaypointResult:
    """Result of loading a waypoint."""

    content: str
    exists: bool
    template: bool
    path: str
    last_modified: datetime | None = None


@dataclass
class SaveResult:
    """Result of saving a waypoint."""

    success: bool
    archived: bool
    archive_path: str | None
    last_modified: datetime | None
    error: str | None = None


def get_waypoint_path(project_path: str | Path) -> Path:
    """
    Get the waypoint file path for a project.

    Args:
        project_path: Path to the project root

    Returns:
        Path to the waypoint file
    """
    return Path(project_path) / "docs" / "brain_reboot" / "waypoint.md"


def get_archive_dir(project_path: str | Path) -> Path:
    """
    Get the archive directory path for a project.

    Args:
        project_path: Path to the project root

    Returns:
        Path to the archive directory
    """
    return Path(project_path) / "docs" / "brain_reboot" / "archive"


def load_waypoint(project_path: str | Path) -> WaypointResult:
    """
    Load waypoint content from a project.

    Args:
        project_path: Path to the project root

    Returns:
        WaypointResult with content, exists flag, and metadata
    """
    path = get_waypoint_path(project_path)

    if not path.exists():
        return WaypointResult(
            content=DEFAULT_TEMPLATE,
            exists=False,
            template=True,
            path=str(path),
            last_modified=None,
        )

    try:
        content = path.read_text(encoding="utf-8")
        stat = path.stat()
        mtime = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)

        return WaypointResult(
            content=content,
            exists=True,
            template=False,
            path=str(path),
            last_modified=mtime,
        )
    except PermissionError:
        logger.error(f"Permission denied reading waypoint: {path}")
        raise
    except Exception as e:
        logger.error(f"Error reading waypoint: {path} - {e}")
        raise


def get_archive_filename(archive_dir: Path, date: datetime) -> str:
    """
    Get a unique archive filename with date and optional counter.

    Args:
        archive_dir: Path to the archive directory
        date: Date for the archive

    Returns:
        Unique filename for the archive
    """
    date_str = date.strftime("%Y-%m-%d")
    base_name = f"waypoint_{date_str}"

    # Check if base filename exists
    if not (archive_dir / f"{base_name}.md").exists():
        return f"{base_name}.md"

    # Find next available counter
    counter = 2
    while (archive_dir / f"{base_name}_{counter}.md").exists():
        counter += 1

    return f"{base_name}_{counter}.md"


def save_waypoint(
    project_path: str | Path,
    content: str,
    expected_mtime: datetime | None = None,
) -> SaveResult:
    """
    Save waypoint content to a project with automatic archiving.

    Performs atomic write (temp file then rename) and archives existing waypoint.

    Args:
        project_path: Path to the project root
        content: New waypoint content
        expected_mtime: Expected modification time for conflict detection

    Returns:
        SaveResult with success flag, archive info, and any errors
    """
    path = get_waypoint_path(project_path)
    archive_dir = get_archive_dir(project_path)
    archived = False
    archive_path = None

    try:
        # Conflict detection
        if expected_mtime is not None and path.exists():
            current_mtime = datetime.fromtimestamp(
                path.stat().st_mtime, tz=timezone.utc
            )
            # Compare with 1 second tolerance for filesystem precision
            time_diff = abs((current_mtime - expected_mtime).total_seconds())
            if time_diff > 1:
                return SaveResult(
                    success=False,
                    archived=False,
                    archive_path=None,
                    last_modified=current_mtime,
                    error="conflict",
                )

        # Create directory structure if missing
        path.parent.mkdir(parents=True, exist_ok=True)
        archive_dir.mkdir(parents=True, exist_ok=True)

        # Archive existing waypoint
        if path.exists():
            now = datetime.now(timezone.utc)
            archive_filename = get_archive_filename(archive_dir, now)
            archive_file = archive_dir / archive_filename

            # Atomic copy to archive
            existing_content = path.read_text(encoding="utf-8")
            fd, temp_archive = tempfile.mkstemp(
                suffix=".md",
                prefix="waypoint_archive_",
                dir=archive_dir,
            )
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    f.write(existing_content)
                os.replace(temp_archive, archive_file)
                archived = True
                archive_path = str(archive_file.relative_to(path.parent))
                logger.info(f"Archived waypoint to {archive_file}")
            except Exception:
                if os.path.exists(temp_archive):
                    os.unlink(temp_archive)
                raise

        # Atomic write new content
        fd, temp_path = tempfile.mkstemp(
            suffix=".md",
            prefix="waypoint_",
            dir=path.parent,
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(content)
            os.replace(temp_path, path)
            logger.info(f"Saved waypoint to {path}")
        except Exception:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
            raise

        # Get new modification time
        new_mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)

        return SaveResult(
            success=True,
            archived=archived,
            archive_path=archive_path,
            last_modified=new_mtime,
        )

    except PermissionError as e:
        error_msg = f"Permission denied: {path}"
        logger.error(error_msg)
        return SaveResult(
            success=False,
            archived=archived,
            archive_path=archive_path,
            last_modified=None,
            error=error_msg,
        )
    except Exception as e:
        error_msg = f"Failed to save waypoint: {type(e).__name__}"
        logger.error(f"{error_msg} - {e}")
        return SaveResult(
            success=False,
            archived=archived,
            archive_path=archive_path,
            last_modified=None,
            error=error_msg,
        )


def validate_project_path(project_path: str | Path) -> tuple[bool, str | None]:
    """
    Validate that a project path exists and is accessible.

    Args:
        project_path: Path to the project root

    Returns:
        Tuple of (valid, error_message)
    """
    path = Path(project_path)

    if not path.exists():
        return False, f"Project path does not exist: {path}"

    if not path.is_dir():
        return False, f"Project path is not a directory: {path}"

    # Check if we can read the directory
    try:
        list(path.iterdir())
    except PermissionError:
        return False, f"Permission denied accessing project: {path}"

    return True, None
