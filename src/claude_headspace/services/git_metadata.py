"""Git metadata extraction with caching.

TODO (Epic 3): Add commit-based progress tracking functionality.
The architecture mentions tracking commits for session progress measurement,
but this is deferred to Epic 3 of the roadmap.
"""

import logging
import os
import subprocess
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class GitInfo:
    """Data class representing git metadata for a project."""

    repo_url: Optional[str]
    current_branch: Optional[str]


class GitMetadata:
    """
    Extract and cache git metadata for projects.

    Caches results to avoid repeated git command execution.
    """

    def __init__(self) -> None:
        self._cache: dict[str, GitInfo] = {}

    def get_git_info(self, project_path: str) -> GitInfo:
        """
        Get git metadata for a project path, using cache if available.

        Args:
            project_path: Path to the project directory

        Returns:
            GitInfo with repo URL and current branch (may be None if not a git repo)
        """
        # Normalize path for consistent cache keys
        project_path = os.path.normpath(os.path.expanduser(project_path))

        # Check cache first
        if project_path in self._cache:
            return self._cache[project_path]

        # Extract git info
        repo_url = self._get_repo_url(project_path)
        current_branch = self._get_current_branch(project_path)

        git_info = GitInfo(repo_url=repo_url, current_branch=current_branch)

        # Cache the result
        self._cache[project_path] = git_info

        return git_info

    def invalidate_cache(self, project_path: str) -> None:
        """
        Clear cached data for a specific project.

        Args:
            project_path: Path to the project directory
        """
        project_path = os.path.normpath(os.path.expanduser(project_path))
        self._cache.pop(project_path, None)

    def clear_all_cache(self) -> None:
        """Clear entire cache."""
        self._cache.clear()

    def _get_repo_url(self, project_path: str) -> Optional[str]:
        """
        Get the git remote URL for a project.

        Args:
            project_path: Path to the project directory

        Returns:
            Remote URL, or None if not a git repo or no remote
        """
        try:
            result = subprocess.run(
                ["git", "remote", "get-url", "origin"],
                cwd=project_path,
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except subprocess.TimeoutExpired:
            logger.warning(f"Git remote URL timeout for: {project_path}")
        except FileNotFoundError:
            logger.warning("Git command not found")
        except Exception as e:
            logger.debug(f"Could not get git remote URL: {e}")

        return None

    def _get_current_branch(self, project_path: str) -> Optional[str]:
        """
        Get the current git branch for a project.

        Args:
            project_path: Path to the project directory

        Returns:
            Branch name, or None if not a git repo
        """
        try:
            result = subprocess.run(
                ["git", "branch", "--show-current"],
                cwd=project_path,
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                branch = result.stdout.strip()
                return branch if branch else None
        except subprocess.TimeoutExpired:
            logger.warning(f"Git branch timeout for: {project_path}")
        except FileNotFoundError:
            logger.warning("Git command not found")
        except Exception as e:
            logger.debug(f"Could not get git branch: {e}")

        return None
