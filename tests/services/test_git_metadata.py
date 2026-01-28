"""Tests for git metadata extraction."""

import os
import subprocess
import tempfile

import pytest

from claude_headspace.services.git_metadata import GitInfo, GitMetadata


class TestGitInfo:
    """Test GitInfo dataclass."""

    def test_create_git_info(self):
        """Test creating GitInfo with values."""
        info = GitInfo(
            repo_url="https://github.com/user/repo.git",
            current_branch="main",
        )
        assert info.repo_url == "https://github.com/user/repo.git"
        assert info.current_branch == "main"

    def test_create_git_info_none_values(self):
        """Test creating GitInfo with None values."""
        info = GitInfo(repo_url=None, current_branch=None)
        assert info.repo_url is None
        assert info.current_branch is None


class TestGitMetadata:
    """Test GitMetadata class."""

    @pytest.fixture
    def git_repo(self):
        """Create a temporary git repository."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Initialize git repo
            subprocess.run(
                ["git", "init"], cwd=tmpdir, capture_output=True, check=True
            )
            subprocess.run(
                ["git", "config", "user.email", "test@example.com"],
                cwd=tmpdir, capture_output=True, check=True
            )
            subprocess.run(
                ["git", "config", "user.name", "Test User"],
                cwd=tmpdir, capture_output=True, check=True
            )
            # Create initial commit
            test_file = os.path.join(tmpdir, "test.txt")
            with open(test_file, "w") as f:
                f.write("test")
            subprocess.run(
                ["git", "add", "."], cwd=tmpdir, capture_output=True, check=True
            )
            subprocess.run(
                ["git", "commit", "-m", "Initial commit"],
                cwd=tmpdir, capture_output=True, check=True
            )
            # Add remote
            subprocess.run(
                ["git", "remote", "add", "origin", "https://github.com/test/repo.git"],
                cwd=tmpdir, capture_output=True, check=True
            )
            yield tmpdir

    @pytest.fixture
    def non_git_dir(self):
        """Create a temporary non-git directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    @pytest.fixture
    def metadata(self):
        """Create GitMetadata instance."""
        return GitMetadata()

    def test_get_git_info_for_repo(self, metadata, git_repo):
        """Test getting git info for a repository."""
        info = metadata.get_git_info(git_repo)
        assert info.repo_url == "https://github.com/test/repo.git"
        assert info.current_branch is not None

    def test_get_git_info_for_non_git(self, metadata, non_git_dir):
        """Test getting git info for non-git directory."""
        info = metadata.get_git_info(non_git_dir)
        assert info.repo_url is None
        assert info.current_branch is None

    def test_caching(self, metadata, git_repo):
        """Test that results are cached."""
        # First call
        info1 = metadata.get_git_info(git_repo)

        # Second call should return cached result
        info2 = metadata.get_git_info(git_repo)

        assert info1 is info2  # Same object

    def test_invalidate_cache(self, metadata, git_repo):
        """Test cache invalidation."""
        info1 = metadata.get_git_info(git_repo)

        metadata.invalidate_cache(git_repo)

        info2 = metadata.get_git_info(git_repo)
        assert info1 is not info2  # Different objects

    def test_clear_all_cache(self, metadata, git_repo, non_git_dir):
        """Test clearing entire cache."""
        metadata.get_git_info(git_repo)
        metadata.get_git_info(non_git_dir)

        metadata.clear_all_cache()

        # Cache should be empty - new calls create new objects
        info1 = metadata.get_git_info(git_repo)
        info2 = metadata.get_git_info(git_repo)
        assert info1 is info2  # Re-cached

    def test_path_normalization(self, metadata, git_repo):
        """Test that path is normalized for caching."""
        # Same path with different representations
        info1 = metadata.get_git_info(git_repo)
        info2 = metadata.get_git_info(git_repo + "/")
        info3 = metadata.get_git_info(os.path.join(git_repo, "."))

        # All should return same cached result
        assert info1 is info2
        assert info1 is info3

    def test_branch_name(self, metadata, git_repo):
        """Test getting branch name."""
        # Create and checkout a branch
        subprocess.run(
            ["git", "checkout", "-b", "test-branch"],
            cwd=git_repo, capture_output=True, check=True
        )

        metadata.invalidate_cache(git_repo)
        info = metadata.get_git_info(git_repo)
        assert info.current_branch == "test-branch"
