"""Centralized path constants for brain_reboot artifacts.

Single source of truth for directory names and filenames used by
brain_reboot, progress_summary, waypoint_editor, and archive_service.
"""

import re

# Relative directory within target project repos
BRAIN_REBOOT_DIR = "docs/brain_reboot"
ARCHIVE_DIR = "docs/brain_reboot/archive"

# Artifact filenames
WAYPOINT_FILENAME = "waypoint.md"
SUMMARY_FILENAME = "progress_summary.md"

# Archive filename pattern and timestamp format
ARCHIVE_FILENAME_RE = re.compile(
    r"^(waypoint|progress_summary|brain_reboot)_(\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2})\.md$"
)
TIMESTAMP_FORMAT = "%Y-%m-%d_%H-%M-%S"

# Valid artifact types for archiving
VALID_ARTIFACT_TYPES = ("waypoint", "progress_summary", "brain_reboot")
