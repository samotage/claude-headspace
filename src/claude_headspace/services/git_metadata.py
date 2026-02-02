"""Git metadata extraction with caching.

TODO (Epic 3): Add commit-based progress tracking functionality.
The architecture mentions tracking commits for session progress measurement,
but this is deferred to Epic 3 of the roadmap.
"""

import logging
import os
import re
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

    @staticmethod
    def parse_owner_repo(raw_url: Optional[str]) -> Optional[str]:
        """Parse a git remote URL into owner/repo format.

        Supports:
            - git@github.com:owner/repo.git
            - https://github.com/owner/repo.git
            - ssh://git@github.com/owner/repo.git
            - URLs with or without .git suffix

        Returns:
            "owner/repo" string, or None if parsing fails.
        """
        if not raw_url or not raw_url.strip():
            return None

        raw_url = raw_url.strip()

        # SSH format: git@github.com:owner/repo.git
        ssh_match = re.match(r"^[\w.-]+@[\w.-]+:(.*)", raw_url)
        if ssh_match:
            path = ssh_match.group(1)
        else:
            # HTTPS or ssh:// format
            try:
                # Strip protocol and host
                # e.g. https://github.com/owner/repo.git → /owner/repo.git
                parts = raw_url.split("://", 1)
                if len(parts) == 2:
                    after_proto = parts[1]
                else:
                    return None
                # Remove host portion
                slash_idx = after_proto.find("/")
                if slash_idx < 0:
                    return None
                path = after_proto[slash_idx + 1:]
            except Exception:
                return None

        # Strip .git suffix and leading/trailing slashes
        path = path.rstrip("/")
        if path.endswith(".git"):
            path = path[:-4]

        # Validate owner/repo format (at least two non-empty segments)
        segments = [s for s in path.split("/") if s]
        if len(segments) < 2:
            return None

        # Return first two segments (owner/repo)
        return f"{segments[0]}/{segments[1]}"

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
