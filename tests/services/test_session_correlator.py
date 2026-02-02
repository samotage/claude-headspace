"""Tests for session correlator service."""

import os
from unittest.mock import MagicMock, patch
from uuid import UUID, uuid4

import pytest

from claude_headspace.services.session_correlator import (
    CorrelationResult,
    _is_rejected_directory,
    _resolve_project_root,
    _resolve_working_directory,
    cache_session_mapping,
    clear_session_cache,
    correlate_session,
    get_cached_agent_id,
)


@pytest.fixture(autouse=True)
def clear_cache():
    """Clear session cache before each test."""
    clear_session_cache()
    yield
    clear_session_cache()


class TestIsRejectedDirectory:
    """Tests for _is_rejected_directory."""

    def test_rejects_tmp(self):
        assert _is_rejected_directory("/tmp") is True

    def test_rejects_tmp_subdir(self):
        assert _is_rejected_directory("/tmp/claude-501/something") is True

    def test_rejects_private_tmp(self):
        assert _is_rejected_directory("/private/tmp") is True

    def test_rejects_private_tmp_subdir(self):
        assert _is_rejected_directory("/private/tmp/claude-501/scratchpad") is True

    def test_rejects_var(self):
        assert _is_rejected_directory("/var") is True

    def test_rejects_var_subdir(self):
        assert _is_rejected_directory("/var/folders/xx/something") is True

    def test_rejects_global_claude_dir(self):
        home = os.path.expanduser("~")
        assert _is_rejected_directory(f"{home}/.claude") is True

    def test_rejects_global_claude_subdir(self):
        home = os.path.expanduser("~")
        assert _is_rejected_directory(f"{home}/.claude/projects/something") is True

    def test_accepts_normal_project(self):
        assert _is_rejected_directory("/Users/dev/myproject") is False

    def test_accepts_project_with_dot_claude_subdir(self):
        """A .claude directory INSIDE a project should not be rejected outright.
        The resolve step will walk up to the project root."""
        assert _is_rejected_directory("/Users/dev/myproject/.claude") is False

    def test_accepts_home_directory(self):
        home = os.path.expanduser("~")
        assert _is_rejected_directory(home) is False


class TestResolveProjectRoot:
    """Tests for _resolve_project_root."""

    def test_returns_dir_with_git(self, tmp_path):
        """Directory with .git should be returned as project root."""
        (tmp_path / ".git").mkdir()
        result = _resolve_project_root(str(tmp_path))
        assert result == str(tmp_path)

    def test_walks_up_to_find_git(self, tmp_path):
        """Subdirectory should resolve up to parent with .git."""
        (tmp_path / ".git").mkdir()
        subdir = tmp_path / "src" / "lib"
        subdir.mkdir(parents=True)

        result = _resolve_project_root(str(subdir))
        assert result == str(tmp_path)

    def test_walks_up_from_dot_claude(self, tmp_path):
        """A .claude subdir should resolve up to the project root."""
        (tmp_path / ".git").mkdir()
        dot_claude = tmp_path / ".claude"
        dot_claude.mkdir()

        result = _resolve_project_root(str(dot_claude))
        assert result == str(tmp_path)

    def test_finds_pyproject_toml(self, tmp_path):
        (tmp_path / "pyproject.toml").touch()
        subdir = tmp_path / "src"
        subdir.mkdir()

        result = _resolve_project_root(str(subdir))
        assert result == str(tmp_path)

    def test_finds_package_json(self, tmp_path):
        (tmp_path / "package.json").touch()
        subdir = tmp_path / "node_modules" / "something"
        subdir.mkdir(parents=True)

        result = _resolve_project_root(str(subdir))
        assert result == str(tmp_path)

    def test_no_marker_returns_original(self, tmp_path):
        """Directory with no markers returns the original path."""
        subdir = tmp_path / "no" / "markers" / "here"
        subdir.mkdir(parents=True)

        result = _resolve_project_root(str(subdir))
        assert result == str(subdir)


class TestResolveWorkingDirectory:
    """Tests for _resolve_working_directory."""

    def test_none_returns_none(self):
        assert _resolve_working_directory(None) is None

    def test_empty_string_returns_none(self):
        assert _resolve_working_directory("") is None

    def test_rejects_tmp(self):
        assert _resolve_working_directory("/tmp/something") is None

    def test_rejects_global_claude(self):
        home = os.path.expanduser("~")
        assert _resolve_working_directory(f"{home}/.claude") is None

    def test_resolves_project_subdir(self, tmp_path):
        """Subdirectory of a project should resolve to project root."""
        (tmp_path / ".git").mkdir()
        subdir = tmp_path / ".claude"
        subdir.mkdir()

        result = _resolve_working_directory(str(subdir))
        assert result == str(tmp_path)

    def test_normal_project_passes_through(self, tmp_path):
        """Normal project directory with .git is returned as-is."""
        (tmp_path / ".git").mkdir()
        result = _resolve_working_directory(str(tmp_path))
        assert result == str(tmp_path)


class TestCorrelateSession:
    """Tests for correlate_session function."""

    @patch("claude_headspace.services.session_correlator.db")
    def test_correlate_by_cached_session_id(self, mock_db):
        """Test correlation by cached session ID."""
        mock_agent = MagicMock()
        mock_agent.id = 1
        mock_db.session.get.return_value = mock_agent

        cache_session_mapping("session-123", 1)

        result = correlate_session("session-123")

        assert result.agent == mock_agent
        assert result.is_new is False
        assert result.correlation_method == "session_id"

    @patch("claude_headspace.services.session_correlator.db")
    def test_cached_session_ignores_different_working_directory(self, mock_db):
        """Once a session is cached, a different working_directory is ignored."""
        mock_agent = MagicMock()
        mock_agent.id = 1
        mock_db.session.get.return_value = mock_agent

        cache_session_mapping("session-123", 1)

        result = correlate_session("session-123", "/some/other/path")

        assert result.agent == mock_agent
        assert result.is_new is False
        assert result.correlation_method == "session_id"

    @patch("claude_headspace.services.session_correlator.db")
    def test_correlate_by_db_session_id(self, mock_db):
        """Test correlation by claude_session_id in database (post-restart)."""
        mock_agent = MagicMock()
        mock_agent.id = 7
        mock_agent.claude_session_id = "db-session-456"

        # Cache miss
        mock_db.session.get.return_value = None
        # DB lookup returns the agent
        mock_db.session.query.return_value.filter.return_value.first.return_value = mock_agent

        result = correlate_session("db-session-456")

        assert result.agent == mock_agent
        assert result.is_new is False
        assert result.correlation_method == "db_session_id"

    @patch("claude_headspace.services.session_correlator.db")
    def test_correlate_by_working_directory(self, mock_db):
        """Test correlation by working directory."""
        mock_project = MagicMock()
        mock_project.id = 1

        mock_agent = MagicMock()
        mock_agent.id = 2
        mock_agent.project_id = 1

        mock_db.session.get.return_value = None
        mock_db.session.query.return_value.filter.return_value.first.return_value = (
            mock_project
        )
        mock_db.session.query.return_value.filter.return_value.order_by.return_value.first.return_value = (
            mock_agent
        )

        result = correlate_session("new-session", "/path/to/project")

        assert result is not None

    @patch("claude_headspace.services.session_correlator.db")
    @patch("claude_headspace.services.session_correlator._create_agent_for_session")
    def test_create_new_agent_when_no_match(self, mock_create, mock_db):
        """Test creating new agent when no correlation found."""
        mock_project = MagicMock()
        mock_project.id = 1
        mock_project.name = "new-project"

        mock_agent = MagicMock()
        mock_agent.id = 3

        mock_create.return_value = (mock_agent, mock_project)

        mock_db.session.get.return_value = None
        mock_db.session.query.return_value.filter.return_value.first.return_value = None

        result = correlate_session("brand-new-session", "/unknown/path")

        assert result.agent == mock_agent
        assert result.is_new is True
        assert result.correlation_method == "created"

    @patch("claude_headspace.services.session_correlator._resolve_working_directory")
    @patch("claude_headspace.services.session_correlator.db")
    def test_rejected_directory_raises_valueerror(self, mock_db, mock_resolve):
        """A rejected directory with unknown session raises ValueError."""
        mock_resolve.return_value = None  # Directory was rejected

        mock_db.session.get.return_value = None
        # DB lookup for claude_session_id also returns None
        mock_db.session.query.return_value.filter.return_value.first.return_value = None

        with pytest.raises(ValueError, match="Cannot correlate session"):
            correlate_session("brand-new-session", "/tmp/junk")

    @patch("claude_headspace.services.session_correlator._resolve_working_directory")
    @patch("claude_headspace.services.session_correlator.db")
    def test_no_working_directory_raises_valueerror(self, mock_db, mock_resolve):
        """No working directory and unknown session raises ValueError."""
        mock_resolve.return_value = None

        mock_db.session.get.return_value = None
        mock_db.session.query.return_value.filter.return_value.first.return_value = None

        with pytest.raises(ValueError, match="Cannot correlate session"):
            correlate_session("orphan-session")

    @patch("claude_headspace.services.session_correlator.db")
    def test_correlate_by_headspace_session_id(self, mock_db):
        """Test Strategy 2.5: match by headspace_session_id -> Agent.session_uuid."""
        cli_uuid = uuid4()
        mock_agent = MagicMock()
        mock_agent.id = 10
        mock_agent.session_uuid = cli_uuid
        mock_agent.claude_session_id = None

        # Cache miss (Strategy 1)
        mock_db.session.get.return_value = None

        # DB lookup by claude_session_id returns None (Strategy 2)
        # DB lookup by session_uuid returns the agent (Strategy 2.5)
        def query_filter_side_effect(*args, **kwargs):
            result = MagicMock()
            # Inspect the filter argument to distinguish queries
            for arg in args:
                arg_str = str(arg)
                if "claude_session_id" in arg_str:
                    result.first.return_value = None
                    return result
                if "session_uuid" in arg_str:
                    result.first.return_value = mock_agent
                    return result
            result.first.return_value = None
            return result

        mock_query = MagicMock()
        mock_query.filter.side_effect = query_filter_side_effect
        mock_db.session.query.return_value = mock_query

        result = correlate_session(
            "claude-internal-id",
            headspace_session_id=str(cli_uuid),
        )

        assert result.agent == mock_agent
        assert result.is_new is False
        assert result.correlation_method == "headspace_session_id"
        # Should have set claude_session_id on the agent
        assert mock_agent.claude_session_id == "claude-internal-id"

    @patch("claude_headspace.services.session_correlator.db")
    def test_headspace_session_id_invalid_uuid_falls_through(self, mock_db):
        """Invalid headspace_session_id should be logged and skipped."""
        mock_db.session.get.return_value = None
        mock_db.session.query.return_value.filter.return_value.first.return_value = None

        # Should fall through to Strategy 3/4 and raise ValueError (no working dir)
        with pytest.raises(ValueError, match="Cannot correlate session"):
            correlate_session(
                "some-session",
                headspace_session_id="not-a-valid-uuid",
            )

    @patch("claude_headspace.services.session_correlator.db")
    def test_headspace_session_id_caches_mapping(self, mock_db):
        """After Strategy 2.5 match, claude_session_id should be cached."""
        cli_uuid = uuid4()
        mock_agent = MagicMock()
        mock_agent.id = 20
        mock_agent.session_uuid = cli_uuid
        mock_agent.claude_session_id = None

        mock_db.session.get.return_value = None

        def query_filter_side_effect(*args, **kwargs):
            result = MagicMock()
            for arg in args:
                arg_str = str(arg)
                if "claude_session_id" in arg_str:
                    result.first.return_value = None
                    return result
                if "session_uuid" in arg_str:
                    result.first.return_value = mock_agent
                    return result
            result.first.return_value = None
            return result

        mock_query = MagicMock()
        mock_query.filter.side_effect = query_filter_side_effect
        mock_db.session.query.return_value = mock_query

        correlate_session(
            "claude-id-abc",
            headspace_session_id=str(cli_uuid),
        )

        # Now the session should be in cache
        assert get_cached_agent_id("claude-id-abc") == 20


class TestStrategy3Safety:
    """Tests for Strategy 3 filtering out ended/claimed agents."""

    @patch("claude_headspace.services.session_correlator._resolve_working_directory")
    @patch("claude_headspace.services.session_correlator.db")
    def test_strategy3_excludes_ended_and_claimed_agents(self, mock_db, mock_resolve):
        """Strategy 3 should only match active, unclaimed agents."""
        mock_resolve.return_value = "/path/to/project"

        mock_project = MagicMock()
        mock_project.id = 1

        # No agent matches the stricter filter (all are claimed or ended)
        mock_db.session.get.return_value = None

        # Set up the query chain to return project but no agent
        call_count = [0]

        def query_side_effect(model):
            q = MagicMock()
            call_count[0] += 1
            if call_count[0] <= 2:
                # First two queries: Strategy 2 (claude_session_id) and Strategy 2.5
                q.filter.return_value.first.return_value = None
            elif call_count[0] == 3:
                # Strategy 3: Project lookup succeeds
                q.filter.return_value.first.return_value = mock_project
            elif call_count[0] == 4:
                # Strategy 3: Agent lookup with safety filters returns None
                q.filter.return_value.order_by.return_value.first.return_value = None
            return q

        mock_db.session.query.side_effect = query_side_effect

        # Should fall through to Strategy 4 and create a new agent
        mock_new_agent = MagicMock()
        mock_new_agent.id = 99
        mock_new_project = MagicMock()
        mock_new_project.name = "project"

        with patch(
            "claude_headspace.services.session_correlator._create_agent_for_session",
            return_value=(mock_new_agent, mock_new_project),
        ):
            result = correlate_session("new-session", "/path/to/project")

        assert result.is_new is True
        assert result.correlation_method == "created"


class TestSessionCache:
    """Tests for session cache functions."""

    def test_cache_session_mapping(self):
        """Test caching a session mapping."""
        cache_session_mapping("session-abc", 42)
        assert get_cached_agent_id("session-abc") == 42

    def test_get_cached_agent_id_not_found(self):
        """Test getting uncached session returns None."""
        assert get_cached_agent_id("nonexistent") is None

    def test_clear_session_cache(self):
        """Test clearing the session cache."""
        cache_session_mapping("session-1", 1)
        cache_session_mapping("session-2", 2)

        clear_session_cache()

        assert get_cached_agent_id("session-1") is None
        assert get_cached_agent_id("session-2") is None


class TestCorrelationResult:
    """Tests for CorrelationResult named tuple."""

    def test_correlation_result_fields(self):
        """Test CorrelationResult has expected fields."""
        agent = MagicMock()
        result = CorrelationResult(
            agent=agent,
            is_new=True,
            correlation_method="created",
        )

        assert result.agent == agent
        assert result.is_new is True
        assert result.correlation_method == "created"
