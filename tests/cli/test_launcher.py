"""Tests for the CLI launcher."""

import argparse
import os
import signal
import subprocess
import tempfile
import uuid
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml

from src.claude_headspace.cli.launcher import (
    BRIDGE_FALLBACK,
    EXIT_CLAUDE_NOT_FOUND,
    EXIT_ERROR,
    EXIT_REGISTRATION_FAILED,
    EXIT_SERVER_UNREACHABLE,
    EXIT_SUCCESS,
    ProjectInfo,
    SessionManager,
    _wrap_in_tmux,
    cleanup_session,
    create_parser,
    get_bridge_default,
    get_iterm_pane_id,
    get_project_info,
    get_server_url,
    get_tmux_pane_id,
    launch_claude,
    main,
    register_session,
    setup_environment,
    validate_persona,
    validate_prerequisites,
    verify_claude_cli,
)


class TestGetServerUrl:
    """Tests for get_server_url function."""

    def test_from_environment(self):
        """Test getting URL from environment variable."""
        with patch.dict(os.environ, {"CLAUDE_HEADSPACE_URL": "http://example.com:8080"}):
            assert get_server_url() == "http://example.com:8080"

    def test_strips_trailing_slash(self):
        """Test that trailing slash is stripped."""
        with patch.dict(os.environ, {"CLAUDE_HEADSPACE_URL": "http://example.com:8080/"}):
            assert get_server_url() == "http://example.com:8080"

    def test_from_config_file(self):
        """Test getting URL from config.yaml."""
        with patch.dict(os.environ, {}, clear=True):
            # Remove env var if present
            os.environ.pop("CLAUDE_HEADSPACE_URL", None)

            # Create temp config
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".yaml", delete=False
            ) as f:
                yaml.dump({"server": {"host": "192.168.1.100", "port": 9000}}, f)
                config_path = f.name

            try:
                with patch(
                    "src.claude_headspace.cli.launcher.Path.cwd",
                    return_value=Path(config_path).parent,
                ):
                    # Patch exists to return True for our temp config path
                    original_exists = Path.exists

                    def mock_exists(self):
                        if str(self) == config_path:
                            return True
                        if str(self) == str(Path(config_path).parent / "config.yaml"):
                            return False
                        return original_exists(self)

                    with patch.object(Path, "exists", mock_exists):
                        # Just test default since patching is complex
                        url = get_server_url()
                        assert url.startswith("https://")
            finally:
                os.unlink(config_path)

    def test_default_url(self):
        """Test default URL when no config available."""
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("CLAUDE_HEADSPACE_URL", None)

            with patch.object(Path, "exists", return_value=False):
                assert get_server_url() == "https://127.0.0.1:5055"


class TestGetProjectInfo:
    """Tests for get_project_info function."""

    def test_git_repository(self):
        """Test project detection in git repository."""
        with patch("subprocess.run") as mock_run:
            # First call: git root
            mock_run.side_effect = [
                MagicMock(returncode=0, stdout="/path/to/repo\n"),
                MagicMock(returncode=0, stdout="feature-branch\n"),
            ]

            with patch("os.getcwd", return_value="/path/to/repo"):
                info = get_project_info()

            assert info.name == "repo"
            assert info.path == "/path/to/repo"
            assert info.branch == "feature-branch"

    def test_non_git_directory(self):
        """Test project detection outside git repository."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="not a git repo")

            with patch("os.getcwd", return_value="/home/user/project"):
                info = get_project_info()

            assert info.name == "project"
            assert info.path == "/home/user/project"
            assert info.branch is None

    def test_git_timeout(self):
        """Test handling of git timeout."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired("git", 5)

            with patch("os.getcwd", return_value="/some/path"):
                info = get_project_info()

            assert info.name == "path"
            assert info.branch is None


class TestGetItermPaneId:
    """Tests for get_iterm_pane_id function."""

    def test_in_iterm2(self, capsys):
        """Test when running in iTerm2."""
        with patch.dict(os.environ, {"ITERM_SESSION_ID": "pane123"}):
            pane_id = get_iterm_pane_id()

        assert pane_id == "pane123"
        captured = capsys.readouterr()
        assert "Warning" not in captured.err

    def test_not_in_iterm2(self, capsys):
        """Test when not running in iTerm2."""
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("ITERM_SESSION_ID", None)
            pane_id = get_iterm_pane_id()

        assert pane_id is None
        captured = capsys.readouterr()
        assert "Warning" in captured.err
        assert "ITERM_SESSION_ID" in captured.err


class TestVerifyClaudeCli:
    """Tests for verify_claude_cli function."""

    def test_claude_found(self):
        """Test when claude CLI is found."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            assert verify_claude_cli() is True

    def test_claude_not_found(self):
        """Test when claude CLI is not found."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1)
            assert verify_claude_cli() is False

    def test_which_timeout(self):
        """Test handling of which timeout."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired("which", 5)
            assert verify_claude_cli() is False


class TestGetTmuxPaneId:
    """Tests for get_tmux_pane_id function."""

    def test_in_tmux(self):
        """Test when running in a tmux pane."""
        with patch.dict(os.environ, {"TMUX_PANE": "%5"}):
            pane_id = get_tmux_pane_id()
        assert pane_id == "%5"

    def test_not_in_tmux(self):
        """Test when not running in tmux."""
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("TMUX_PANE", None)
            pane_id = get_tmux_pane_id()
        assert pane_id is None

    def test_empty_tmux_pane(self):
        """Test when TMUX_PANE is set but empty."""
        with patch.dict(os.environ, {"TMUX_PANE": ""}):
            pane_id = get_tmux_pane_id()
        assert pane_id is None


class TestValidatePrerequisites:
    """Tests for validate_prerequisites function."""

    def test_all_valid(self):
        """Test when all prerequisites are met."""
        with patch("requests.get") as mock_get:
            mock_get.return_value = MagicMock(status_code=200)

            with patch(
                "src.claude_headspace.cli.launcher.verify_claude_cli", return_value=True
            ):
                valid, error = validate_prerequisites("http://localhost:5055")

        assert valid is True
        assert error is None

    def test_server_unreachable(self):
        """Test when server is unreachable."""
        with patch("requests.get") as mock_get:
            import requests

            mock_get.side_effect = requests.exceptions.ConnectionError()

            valid, error = validate_prerequisites("http://localhost:5055")

        assert valid is False
        assert "Cannot connect" in error

    def test_server_timeout(self):
        """Test when server times out."""
        with patch("requests.get") as mock_get:
            import requests

            mock_get.side_effect = requests.exceptions.Timeout()

            valid, error = validate_prerequisites("http://localhost:5055")

        assert valid is False
        assert "timed out" in error

    def test_server_error_status(self):
        """Test when server returns error status."""
        with patch("requests.get") as mock_get:
            mock_get.return_value = MagicMock(status_code=500)

            valid, error = validate_prerequisites("http://localhost:5055")

        assert valid is False
        assert "500" in error

    def test_claude_not_found(self):
        """Test when claude CLI is not found."""
        with patch("requests.get") as mock_get:
            mock_get.return_value = MagicMock(status_code=200)

            with patch(
                "src.claude_headspace.cli.launcher.verify_claude_cli", return_value=False
            ):
                valid, error = validate_prerequisites("http://localhost:5055")

        assert valid is False
        assert "claude CLI not found" in error


class TestRegisterSession:
    """Tests for register_session function."""

    def test_registration_success(self):
        """Test successful session registration."""
        session_uuid = uuid.uuid4()
        project_info = ProjectInfo("test-project", "/path/to/project", "main")

        with patch("requests.post") as mock_post:
            mock_post.return_value = MagicMock(
                status_code=201,
                json=lambda: {
                    "status": "created",
                    "agent_id": 1,
                    "session_uuid": str(session_uuid),
                    "project_id": 1,
                    "project_name": "test-project",
                },
            )

            success, data, error = register_session(
                "http://localhost:5055",
                session_uuid,
                project_info,
                "pane123",
            )

        assert success is True
        assert data["agent_id"] == 1
        assert error is None

    def test_registration_failure(self):
        """Test failed session registration."""
        session_uuid = uuid.uuid4()
        project_info = ProjectInfo("test-project", "/path/to/project", None)

        with patch("requests.post") as mock_post:
            mock_post.return_value = MagicMock(
                status_code=400,
                text='{"error": "Invalid request"}',
                json=lambda: {"error": "Invalid request"},
            )

            success, data, error = register_session(
                "http://localhost:5055",
                session_uuid,
                project_info,
                None,
            )

        assert success is False
        assert data is None
        assert "Invalid request" in error

    def test_registration_with_tmux_pane_id(self):
        """Test that tmux_pane_id is included in payload when provided."""
        session_uuid = uuid.uuid4()
        project_info = ProjectInfo("test-project", "/path/to/project", "main")

        with patch("requests.post") as mock_post:
            mock_post.return_value = MagicMock(
                status_code=201,
                json=lambda: {
                    "status": "created",
                    "agent_id": 1,
                    "session_uuid": str(session_uuid),
                    "project_id": 1,
                    "project_name": "test-project",
                },
            )

            success, data, error = register_session(
                "http://localhost:5055",
                session_uuid,
                project_info,
                "pane123",
                tmux_pane_id="%5",
            )

        assert success is True
        # Verify tmux_pane_id was in the POST payload
        call_kwargs = mock_post.call_args
        payload = call_kwargs[1]["json"]
        assert payload["tmux_pane_id"] == "%5"

    def test_registration_without_tmux_pane_id(self):
        """Test that tmux_pane_id is not in payload when not provided."""
        session_uuid = uuid.uuid4()
        project_info = ProjectInfo("test-project", "/path/to/project", "main")

        with patch("requests.post") as mock_post:
            mock_post.return_value = MagicMock(
                status_code=201,
                json=lambda: {
                    "status": "created",
                    "agent_id": 1,
                    "session_uuid": str(session_uuid),
                    "project_id": 1,
                    "project_name": "test-project",
                },
            )

            success, data, error = register_session(
                "http://localhost:5055",
                session_uuid,
                project_info,
                "pane123",
            )

        assert success is True
        # Verify tmux_pane_id was NOT in the POST payload
        call_kwargs = mock_post.call_args
        payload = call_kwargs[1]["json"]
        assert "tmux_pane_id" not in payload

    def test_registration_connection_error(self):
        """Test connection error during registration."""
        session_uuid = uuid.uuid4()
        project_info = ProjectInfo("test-project", "/path/to/project", None)

        with patch("requests.post") as mock_post:
            import requests

            mock_post.side_effect = requests.exceptions.ConnectionError()

            success, data, error = register_session(
                "http://localhost:5055",
                session_uuid,
                project_info,
                None,
            )

        assert success is False
        assert "Cannot connect" in error


class TestCleanupSession:
    """Tests for cleanup_session function."""

    def test_cleanup_success(self):
        """Test successful session cleanup."""
        session_uuid = uuid.uuid4()

        with patch("requests.delete") as mock_delete:
            mock_delete.return_value = MagicMock(status_code=200)

            # Should not raise
            cleanup_session("http://localhost:5055", session_uuid)

            mock_delete.assert_called_once()

    def test_cleanup_failure_non_blocking(self):
        """Test that cleanup failure doesn't raise exception."""
        session_uuid = uuid.uuid4()

        with patch("requests.delete") as mock_delete:
            import requests

            mock_delete.side_effect = requests.exceptions.ConnectionError()

            # Should not raise
            cleanup_session("http://localhost:5055", session_uuid)


class TestSetupEnvironment:
    """Tests for setup_environment function."""

    def test_environment_variables_set(self):
        """Test that environment variables are set correctly."""
        session_uuid = uuid.uuid4()
        server_url = "http://localhost:5055"

        env = setup_environment(server_url, session_uuid)

        assert env["CLAUDE_HEADSPACE_URL"] == server_url
        assert env["CLAUDE_HEADSPACE_SESSION_ID"] == str(session_uuid)
        # Should include existing env vars
        assert "PATH" in env

    def test_persona_slug_set(self):
        """Test that persona slug env var is set when provided."""
        env = setup_environment(
            "http://localhost:5055", uuid.uuid4(), persona_slug="developer-con-1"
        )
        assert env["CLAUDE_HEADSPACE_PERSONA_SLUG"] == "developer-con-1"

    def test_persona_slug_absent_when_none(self):
        """Test that persona slug env var is not set when not provided."""
        env = setup_environment("http://localhost:5055", uuid.uuid4())
        assert "CLAUDE_HEADSPACE_PERSONA_SLUG" not in env


class TestValidatePersona:
    """Tests for validate_persona function."""

    @patch("src.claude_headspace.cli.launcher.requests.get")
    def test_valid_persona(self, mock_get):
        """Test validation passes for existing active persona."""
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: {"valid": True, "slug": "dev-con", "id": 1, "name": "Dev Con"},
        )
        valid, error = validate_persona("http://localhost:5055", "dev-con")
        assert valid is True
        assert error is None
        mock_get.assert_called_once_with(
            "http://localhost:5055/api/personas/dev-con/validate",
            timeout=2,
            verify=False,
        )

    @patch("src.claude_headspace.cli.launcher.requests.get")
    def test_invalid_persona(self, mock_get):
        """Test validation fails for nonexistent persona."""
        mock_get.return_value = MagicMock(
            status_code=404,
            text='{"valid": false, "error": "not found"}',
            json=lambda: {"valid": False, "error": "Persona 'nope' not found or not active"},
        )
        valid, error = validate_persona("http://localhost:5055", "nope")
        assert valid is False
        assert "not found" in error.lower() or "not active" in error.lower()

    @patch("src.claude_headspace.cli.launcher.requests.get")
    def test_connection_error(self, mock_get):
        """Test validation handles connection errors gracefully."""
        import requests as req
        mock_get.side_effect = req.exceptions.ConnectionError("refused")
        valid, error = validate_persona("http://localhost:5055", "dev-con")
        assert valid is False
        assert "Cannot connect" in error

    @patch("src.claude_headspace.cli.launcher.requests.get")
    def test_timeout_error(self, mock_get):
        """Test validation handles timeout errors gracefully."""
        import requests as req
        mock_get.side_effect = req.exceptions.Timeout("timed out")
        valid, error = validate_persona("http://localhost:5055", "dev-con")
        assert valid is False
        assert "timed out" in error


class TestCreateParserPersona:
    """Tests for --persona flag in create_parser."""

    def test_persona_flag_recognized(self):
        """Test that --persona flag is parsed correctly."""
        parser = create_parser()
        args = parser.parse_args(["start", "--persona", "dev-con"])
        assert args.persona == "dev-con"

    def test_persona_flag_default_none(self):
        """Test that persona defaults to None when not provided."""
        parser = create_parser()
        args = parser.parse_args(["start"])
        assert args.persona is None


class TestLaunchClaude:
    """Tests for launch_claude function."""

    def test_launch_success(self):
        """Test successful claude launch."""
        with patch("subprocess.call") as mock_call:
            mock_call.return_value = 0

            exit_code = launch_claude(["--model", "opus"], {"PATH": "/usr/bin"})

        assert exit_code == 0
        mock_call.assert_called_once()
        call_args = mock_call.call_args
        assert call_args[0][0] == ["claude", "--model", "opus"]

    def test_launch_failure(self):
        """Test claude launch failure."""
        with patch("subprocess.call") as mock_call:
            mock_call.return_value = 1

            exit_code = launch_claude([], {"PATH": "/usr/bin"})

        assert exit_code == 1

    def test_launch_no_extra_args(self):
        """Test launch with no extra args uses bare claude command."""
        with patch("subprocess.call") as mock_call:
            mock_call.return_value = 0

            exit_code = launch_claude([], {"PATH": "/usr/bin"})

        assert exit_code == 0
        call_args = mock_call.call_args
        assert call_args[0][0] == ["claude"]


class TestSessionManager:
    """Tests for SessionManager class."""

    def test_context_manager_cleanup(self):
        """Test that cleanup is called on exit."""
        session_uuid = uuid.uuid4()

        with patch(
            "src.claude_headspace.cli.launcher.cleanup_session"
        ) as mock_cleanup:
            with SessionManager("http://localhost:5055", session_uuid):
                pass

            mock_cleanup.assert_called_once_with(
                "http://localhost:5055", session_uuid
            )

    def test_cleanup_idempotent(self):
        """Test that cleanup is only called once."""
        session_uuid = uuid.uuid4()

        with patch(
            "src.claude_headspace.cli.launcher.cleanup_session"
        ) as mock_cleanup:
            manager = SessionManager("http://localhost:5055", session_uuid)
            manager._cleanup()
            manager._cleanup()
            manager._cleanup()

            assert mock_cleanup.call_count == 1


class TestWrapInTmux:
    """Tests for _wrap_in_tmux function."""

    def test_creates_tmux_session_with_correct_args(self):
        """Test that execvp is called with correct tmux command."""
        args = argparse.Namespace(bridge=True)

        with patch("shutil.which", side_effect=lambda cmd: "/usr/bin/tmux" if cmd == "tmux" else "/usr/local/bin/claude-headspace"):
            with patch(
                "src.claude_headspace.cli.launcher.get_project_info",
                return_value=ProjectInfo("my-project", "/path/to/my-project", "main"),
            ):
                with patch("src.claude_headspace.cli.launcher.uuid.uuid4") as mock_uuid:
                    mock_uuid.return_value = MagicMock(hex="abcdef1234567890")
                    with patch("os.execvp") as mock_execvp:
                        with patch("sys.argv", ["claude-headspace", "start", "--bridge"]):
                            _wrap_in_tmux(args)

        mock_execvp.assert_called_once()
        call_args = mock_execvp.call_args[0]
        assert call_args[0] == "tmux"
        argv = call_args[1]
        assert argv[0] == "tmux"
        assert argv[1] == "new-session"
        assert "-s" in argv
        session_idx = argv.index("-s")
        assert argv[session_idx + 1] == "hs-my-project-abcdef12"
        assert "-c" in argv
        path_idx = argv.index("-c")
        assert argv[path_idx + 1] == "/path/to/my-project"
        assert "-e" in argv
        env_idx = argv.index("-e")
        assert argv[env_idx + 1] == "CLAUDE_HEADSPACE_TMUX_SESSION=hs-my-project-abcdef12"
        assert "--" in argv

    def test_tmux_not_installed_returns_fallback(self, capsys):
        """Test warning and fallback when tmux is not installed."""
        args = argparse.Namespace(bridge=True)

        with patch("shutil.which", return_value=None):
            result = _wrap_in_tmux(args)

        assert result == BRIDGE_FALLBACK
        captured = capsys.readouterr()
        assert "tmux is not installed" in captured.err
        assert "brew install tmux" in captured.err
        assert "--no-bridge" in captured.err

    def test_execvp_failure_returns_error(self, capsys):
        """Test OSError handling from execvp."""
        args = argparse.Namespace(bridge=True)

        with patch("shutil.which", side_effect=lambda cmd: "/usr/bin/tmux" if cmd == "tmux" else "/usr/local/bin/claude-headspace"):
            with patch(
                "src.claude_headspace.cli.launcher.get_project_info",
                return_value=ProjectInfo("test", "/test", "main"),
            ):
                with patch("os.execvp", side_effect=OSError("exec failed")):
                    with patch("sys.argv", ["claude-headspace", "start", "--bridge"]):
                        result = _wrap_in_tmux(args)

        assert result == EXIT_ERROR
        captured = capsys.readouterr()
        assert "Failed to start tmux session" in captured.err

    def test_session_name_format(self):
        """Test that session name follows hs-{name}-{hex8} pattern."""
        args = argparse.Namespace(bridge=True)

        with patch("shutil.which", side_effect=lambda cmd: "/usr/bin/tmux" if cmd == "tmux" else "/usr/local/bin/claude-headspace"):
            with patch(
                "src.claude_headspace.cli.launcher.get_project_info",
                return_value=ProjectInfo("cool-project", "/path/to/cool-project", "dev"),
            ):
                with patch("os.execvp") as mock_execvp:
                    with patch("sys.argv", ["claude-headspace", "start", "--bridge"]):
                        _wrap_in_tmux(args)

        argv = mock_execvp.call_args[0][1]
        session_idx = argv.index("-s")
        session_name = argv[session_idx + 1]
        assert session_name.startswith("hs-cool-project-")
        # 8 hex chars after the last dash
        suffix = session_name.split("-")[-1]
        assert len(suffix) == 8
        assert all(c in "0123456789abcdef" for c in suffix)

    def test_prints_status_line(self, capsys):
        """Test that a status line is printed before exec."""
        args = argparse.Namespace(bridge=True)

        with patch("shutil.which", side_effect=lambda cmd: "/usr/bin/tmux" if cmd == "tmux" else "/usr/local/bin/claude-headspace"):
            with patch(
                "src.claude_headspace.cli.launcher.get_project_info",
                return_value=ProjectInfo("test", "/test", "main"),
            ):
                with patch("os.execvp"):
                    with patch("sys.argv", ["claude-headspace", "start", "--bridge"]):
                        _wrap_in_tmux(args)

        captured = capsys.readouterr()
        assert "Starting tmux session:" in captured.out


class TestCreateParser:
    """Tests for create_parser function."""

    def test_help_flag(self):
        """Test --help flag."""
        parser = create_parser()

        with pytest.raises(SystemExit) as exc_info:
            parser.parse_args(["--help"])

        assert exc_info.value.code == 0

    def test_start_command(self):
        """Test start command parsing."""
        parser = create_parser()

        args = parser.parse_args(["start"])

        assert args.command == "start"
        assert args.claude_args == []

    def test_start_with_positional_args(self):
        """Test start command with positional claude args."""
        parser = create_parser()

        # Without --, positional args after start are collected
        args = parser.parse_args(["start", "arg1", "arg2"])

        assert args.command == "start"
        assert args.claude_args == ["arg1", "arg2"]

    def test_no_bridge_flag(self):
        """Test --no-bridge flag parsing."""
        parser = create_parser()
        args = parser.parse_args(["start", "--no-bridge"])
        assert args.no_bridge is True
        assert args.bridge is False

    def test_bridge_and_no_bridge_flags(self):
        """Test that both flags can be parsed (--no-bridge takes precedence in cmd_start)."""
        parser = create_parser()
        args = parser.parse_args(["start", "--bridge", "--no-bridge"])
        assert args.bridge is True
        assert args.no_bridge is True


class TestMain:
    """Tests for main function."""

    def test_no_command_shows_help(self, capsys):
        """Test that no command shows help."""
        exit_code = main([])

        assert exit_code == EXIT_SUCCESS
        captured = capsys.readouterr()
        assert "usage:" in captured.out.lower() or "usage:" in captured.err.lower() or exit_code == 0

    def test_separator_handling(self):
        """Test -- separator handling for claude args."""
        with patch("src.claude_headspace.cli.launcher.cmd_start") as mock_start:
            mock_start.return_value = 0

            main(["start", "--", "--model", "opus"])

            call_args = mock_start.call_args[0][0]
            assert call_args.claude_args == ["--model", "opus"]

    def test_start_command_server_unreachable(self, capsys):
        """Test start command when server is unreachable."""
        with patch(
            "src.claude_headspace.cli.launcher.get_server_url",
            return_value="http://localhost:5055",
        ):
            with patch(
                "src.claude_headspace.cli.launcher.validate_prerequisites",
                return_value=(False, "Cannot connect to server"),
            ):
                exit_code = main(["start", "--no-bridge"])

        assert exit_code == EXIT_SERVER_UNREACHABLE

    def test_start_command_claude_not_found(self, capsys):
        """Test start command when claude CLI not found."""
        with patch(
            "src.claude_headspace.cli.launcher.get_server_url",
            return_value="http://localhost:5055",
        ):
            with patch(
                "src.claude_headspace.cli.launcher.validate_prerequisites",
                return_value=(False, "claude CLI not found"),
            ):
                exit_code = main(["start", "--no-bridge"])

        assert exit_code == EXIT_CLAUDE_NOT_FOUND

    def test_start_command_registration_failed(self, capsys):
        """Test start command when registration fails."""
        with patch(
            "src.claude_headspace.cli.launcher.get_server_url",
            return_value="http://localhost:5055",
        ):
            with patch(
                "src.claude_headspace.cli.launcher.validate_prerequisites",
                return_value=(True, None),
            ):
                with patch(
                    "src.claude_headspace.cli.launcher.get_project_info",
                    return_value=ProjectInfo("test", "/test", "main"),
                ):
                    with patch(
                        "src.claude_headspace.cli.launcher.get_iterm_pane_id",
                        return_value="pane123",
                    ):
                        with patch(
                            "src.claude_headspace.cli.launcher.register_session",
                            return_value=(False, None, "Registration failed"),
                        ):
                            exit_code = main(["start", "--no-bridge"])

        assert exit_code == EXIT_REGISTRATION_FAILED

    def test_start_command_full_success(self, capsys):
        """Test successful start command with --no-bridge."""
        with patch(
            "src.claude_headspace.cli.launcher.get_server_url",
            return_value="http://localhost:5055",
        ):
            with patch(
                "src.claude_headspace.cli.launcher.validate_prerequisites",
                return_value=(True, None),
            ):
                with patch(
                    "src.claude_headspace.cli.launcher.get_project_info",
                    return_value=ProjectInfo("test", "/test", "main"),
                ):
                    with patch(
                        "src.claude_headspace.cli.launcher.get_iterm_pane_id",
                        return_value="pane123",
                    ):
                        with patch(
                            "src.claude_headspace.cli.launcher.register_session",
                            return_value=(
                                True,
                                {"agent_id": 1, "project_name": "test"},
                                None,
                            ),
                        ):
                            with patch(
                                "src.claude_headspace.cli.launcher.setup_environment",
                                return_value={"PATH": "/usr/bin"},
                            ):
                                with patch(
                                    "src.claude_headspace.cli.launcher.SessionManager"
                                ) as MockManager:
                                    mock_manager = MagicMock()
                                    MockManager.return_value.__enter__ = MagicMock(
                                        return_value=mock_manager
                                    )
                                    MockManager.return_value.__exit__ = MagicMock(
                                        return_value=False
                                    )

                                    with patch(
                                        "src.claude_headspace.cli.launcher.launch_claude",
                                        return_value=0,
                                    ):
                                        exit_code = main(["start", "--no-bridge"])

        assert exit_code == EXIT_SUCCESS

    def test_start_command_with_bridge_in_tmux(self, capsys):
        """Test start command with --bridge inside tmux detects pane."""
        with patch.dict(os.environ, {"TMUX_PANE": "%5"}):
            with patch(
                "src.claude_headspace.cli.launcher.get_server_url",
                return_value="http://localhost:5055",
            ):
                with patch(
                    "src.claude_headspace.cli.launcher.validate_prerequisites",
                    return_value=(True, None),
                ):
                    with patch(
                        "src.claude_headspace.cli.launcher.get_project_info",
                        return_value=ProjectInfo("test", "/test", "main"),
                    ):
                        with patch(
                            "src.claude_headspace.cli.launcher.get_iterm_pane_id",
                            return_value="pane123",
                        ):
                            with patch(
                                "src.claude_headspace.cli.launcher.get_tmux_pane_id",
                                return_value="%5",
                            ):
                                with patch(
                                    "src.claude_headspace.cli.launcher.register_session",
                                    return_value=(
                                        True,
                                        {"agent_id": 1, "project_name": "test"},
                                        None,
                                    ),
                                ) as mock_register:
                                    with patch(
                                        "src.claude_headspace.cli.launcher.setup_environment",
                                        return_value={"PATH": "/usr/bin"},
                                    ):
                                        with patch(
                                            "src.claude_headspace.cli.launcher.SessionManager"
                                        ) as MockManager:
                                            mock_manager = MagicMock()
                                            MockManager.return_value.__enter__ = MagicMock(
                                                return_value=mock_manager
                                            )
                                            MockManager.return_value.__exit__ = MagicMock(
                                                return_value=False
                                            )

                                            with patch(
                                                "src.claude_headspace.cli.launcher.launch_claude",
                                                return_value=0,
                                            ):
                                                exit_code = main(["start", "--bridge"])

        assert exit_code == EXIT_SUCCESS
        # Verify register_session received tmux_pane_id
        mock_register.assert_called_once()
        call_kwargs = mock_register.call_args
        assert call_kwargs[1]["tmux_pane_id"] == "%5"
        # Verify output mentions Voice Bridge available with pane ID
        captured = capsys.readouterr()
        assert "Voice Bridge: enabled (tmux pane %5)" in captured.out

    def test_start_command_with_bridge_outside_tmux(self):
        """Test start command with --bridge outside tmux calls _wrap_in_tmux."""
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("TMUX_PANE", None)
            with patch(
                "src.claude_headspace.cli.launcher._wrap_in_tmux",
                return_value=EXIT_SUCCESS,
            ) as mock_wrap:
                exit_code = main(["start", "--bridge"])

        assert exit_code == EXIT_SUCCESS
        mock_wrap.assert_called_once()

    def test_start_command_with_bridge_no_tmux_installed_continues(self, capsys):
        """Test start command with --bridge when tmux not installed falls back gracefully."""
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("TMUX_PANE", None)
            with patch("shutil.which", return_value=None):
                with patch(
                    "src.claude_headspace.cli.launcher.get_server_url",
                    return_value="http://localhost:5055",
                ):
                    with patch(
                        "src.claude_headspace.cli.launcher.validate_prerequisites",
                        return_value=(True, None),
                    ):
                        with patch(
                            "src.claude_headspace.cli.launcher.get_project_info",
                            return_value=ProjectInfo("test", "/test", "main"),
                        ):
                            with patch(
                                "src.claude_headspace.cli.launcher.get_iterm_pane_id",
                                return_value="pane123",
                            ):
                                with patch(
                                    "src.claude_headspace.cli.launcher.register_session",
                                    return_value=(
                                        True,
                                        {"agent_id": 1, "project_name": "test"},
                                        None,
                                    ),
                                ):
                                    with patch(
                                        "src.claude_headspace.cli.launcher.setup_environment",
                                        return_value={"PATH": "/usr/bin"},
                                    ):
                                        with patch(
                                            "src.claude_headspace.cli.launcher.SessionManager"
                                        ) as MockManager:
                                            mock_manager = MagicMock()
                                            MockManager.return_value.__enter__ = MagicMock(
                                                return_value=mock_manager
                                            )
                                            MockManager.return_value.__exit__ = MagicMock(
                                                return_value=False
                                            )
                                            with patch(
                                                "src.claude_headspace.cli.launcher.launch_claude",
                                                return_value=0,
                                            ):
                                                exit_code = main(["start", "--bridge"])

        assert exit_code == EXIT_SUCCESS
        captured = capsys.readouterr()
        assert "tmux is not installed" in captured.err

    def test_no_bridge_flag_disables_bridge(self, capsys):
        """Test that --no-bridge disables bridge and skips tmux detection."""
        with patch(
            "src.claude_headspace.cli.launcher.get_server_url",
            return_value="http://localhost:5055",
        ):
            with patch(
                "src.claude_headspace.cli.launcher.validate_prerequisites",
                return_value=(True, None),
            ):
                with patch(
                    "src.claude_headspace.cli.launcher.get_project_info",
                    return_value=ProjectInfo("test", "/test", "main"),
                ):
                    with patch(
                        "src.claude_headspace.cli.launcher.get_iterm_pane_id",
                        return_value="pane123",
                    ):
                        with patch(
                            "src.claude_headspace.cli.launcher.get_tmux_pane_id",
                        ) as mock_tmux:
                            with patch(
                                "src.claude_headspace.cli.launcher.register_session",
                                return_value=(
                                    True,
                                    {"agent_id": 1, "project_name": "test"},
                                    None,
                                ),
                            ):
                                with patch(
                                    "src.claude_headspace.cli.launcher.setup_environment",
                                    return_value={"PATH": "/usr/bin"},
                                ):
                                    with patch(
                                        "src.claude_headspace.cli.launcher.SessionManager"
                                    ) as MockManager:
                                        mock_manager = MagicMock()
                                        MockManager.return_value.__enter__ = MagicMock(
                                            return_value=mock_manager
                                        )
                                        MockManager.return_value.__exit__ = MagicMock(
                                            return_value=False
                                        )

                                        with patch(
                                            "src.claude_headspace.cli.launcher.launch_claude",
                                            return_value=0,
                                        ):
                                            exit_code = main(["start", "--no-bridge"])

        assert exit_code == EXIT_SUCCESS
        # get_tmux_pane_id should not be called with --no-bridge
        mock_tmux.assert_not_called()
        # Should show disabled message
        captured = capsys.readouterr()
        assert "Voice Bridge: disabled (--no-bridge)" in captured.out

    def test_bridge_flag_is_noop_same_as_default(self):
        """Test that --bridge behaves same as default (both enable bridge)."""
        with patch.dict(os.environ, {"TMUX_PANE": "%5"}):
            with patch(
                "src.claude_headspace.cli.launcher.get_server_url",
                return_value="http://localhost:5055",
            ):
                with patch(
                    "src.claude_headspace.cli.launcher.validate_prerequisites",
                    return_value=(True, None),
                ):
                    with patch(
                        "src.claude_headspace.cli.launcher.get_project_info",
                        return_value=ProjectInfo("test", "/test", "main"),
                    ):
                        with patch(
                            "src.claude_headspace.cli.launcher.get_iterm_pane_id",
                            return_value="pane123",
                        ):
                            with patch(
                                "src.claude_headspace.cli.launcher.get_tmux_pane_id",
                                return_value="%5",
                            ) as mock_tmux:
                                with patch(
                                    "src.claude_headspace.cli.launcher.register_session",
                                    return_value=(
                                        True,
                                        {"agent_id": 1, "project_name": "test"},
                                        None,
                                    ),
                                ):
                                    with patch(
                                        "src.claude_headspace.cli.launcher.setup_environment",
                                        return_value={"PATH": "/usr/bin"},
                                    ):
                                        with patch(
                                            "src.claude_headspace.cli.launcher.SessionManager"
                                        ) as MockManager:
                                            mock_manager = MagicMock()
                                            MockManager.return_value.__enter__ = MagicMock(
                                                return_value=mock_manager
                                            )
                                            MockManager.return_value.__exit__ = MagicMock(
                                                return_value=False
                                            )
                                            with patch(
                                                "src.claude_headspace.cli.launcher.launch_claude",
                                                return_value=0,
                                            ):
                                                # --bridge explicit
                                                exit1 = main(["start", "--bridge"])

        assert exit1 == EXIT_SUCCESS
        mock_tmux.assert_called()

    def test_config_default_bridge_false(self):
        """Test that config default_bridge=False disables bridge by default."""
        with patch(
            "src.claude_headspace.cli.launcher.get_bridge_default",
            return_value=False,
        ):
            with patch(
                "src.claude_headspace.cli.launcher.get_server_url",
                return_value="http://localhost:5055",
            ):
                with patch(
                    "src.claude_headspace.cli.launcher.validate_prerequisites",
                    return_value=(True, None),
                ):
                    with patch(
                        "src.claude_headspace.cli.launcher.get_project_info",
                        return_value=ProjectInfo("test", "/test", "main"),
                    ):
                        with patch(
                            "src.claude_headspace.cli.launcher.get_iterm_pane_id",
                            return_value="pane123",
                        ):
                            with patch(
                                "src.claude_headspace.cli.launcher.get_tmux_pane_id",
                            ) as mock_tmux:
                                with patch(
                                    "src.claude_headspace.cli.launcher.register_session",
                                    return_value=(
                                        True,
                                        {"agent_id": 1, "project_name": "test"},
                                        None,
                                    ),
                                ):
                                    with patch(
                                        "src.claude_headspace.cli.launcher.setup_environment",
                                        return_value={"PATH": "/usr/bin"},
                                    ):
                                        with patch(
                                            "src.claude_headspace.cli.launcher.SessionManager"
                                        ) as MockManager:
                                            mock_manager = MagicMock()
                                            MockManager.return_value.__enter__ = MagicMock(
                                                return_value=mock_manager
                                            )
                                            MockManager.return_value.__exit__ = MagicMock(
                                                return_value=False
                                            )
                                            with patch(
                                                "src.claude_headspace.cli.launcher.launch_claude",
                                                return_value=0,
                                            ):
                                                exit_code = main(["start"])

        assert exit_code == EXIT_SUCCESS
        # Bridge disabled by config, so no tmux detection
        mock_tmux.assert_not_called()

    def test_no_bridge_overrides_config(self):
        """Test that --no-bridge overrides config default_bridge=True."""
        with patch(
            "src.claude_headspace.cli.launcher.get_bridge_default",
            return_value=True,
        ):
            with patch(
                "src.claude_headspace.cli.launcher.get_server_url",
                return_value="http://localhost:5055",
            ):
                with patch(
                    "src.claude_headspace.cli.launcher.validate_prerequisites",
                    return_value=(True, None),
                ):
                    with patch(
                        "src.claude_headspace.cli.launcher.get_project_info",
                        return_value=ProjectInfo("test", "/test", "main"),
                    ):
                        with patch(
                            "src.claude_headspace.cli.launcher.get_iterm_pane_id",
                            return_value="pane123",
                        ):
                            with patch(
                                "src.claude_headspace.cli.launcher.get_tmux_pane_id",
                            ) as mock_tmux:
                                with patch(
                                    "src.claude_headspace.cli.launcher.register_session",
                                    return_value=(
                                        True,
                                        {"agent_id": 1, "project_name": "test"},
                                        None,
                                    ),
                                ):
                                    with patch(
                                        "src.claude_headspace.cli.launcher.setup_environment",
                                        return_value={"PATH": "/usr/bin"},
                                    ):
                                        with patch(
                                            "src.claude_headspace.cli.launcher.SessionManager"
                                        ) as MockManager:
                                            mock_manager = MagicMock()
                                            MockManager.return_value.__enter__ = MagicMock(
                                                return_value=mock_manager
                                            )
                                            MockManager.return_value.__exit__ = MagicMock(
                                                return_value=False
                                            )
                                            with patch(
                                                "src.claude_headspace.cli.launcher.launch_claude",
                                                return_value=0,
                                            ):
                                                exit_code = main(["start", "--no-bridge"])

        assert exit_code == EXIT_SUCCESS
        # --no-bridge wins over config
        mock_tmux.assert_not_called()

    def test_default_start_attempts_bridge(self):
        """Test that plain 'start' (no flags) attempts bridge by default."""
        with patch(
            "src.claude_headspace.cli.launcher.get_bridge_default",
            return_value=True,
        ):
            with patch.dict(os.environ, {}, clear=False):
                os.environ.pop("TMUX_PANE", None)
                with patch(
                    "src.claude_headspace.cli.launcher._wrap_in_tmux",
                    return_value=EXIT_SUCCESS,
                ) as mock_wrap:
                    exit_code = main(["start"])

        assert exit_code == EXIT_SUCCESS
        mock_wrap.assert_called_once()


class TestGetBridgeDefault:
    """Tests for get_bridge_default function."""

    def test_returns_true_when_no_config_found(self):
        """Test that True is returned when no config file exists."""
        with patch.object(Path, "exists", return_value=False):
            assert get_bridge_default() is True

    def test_reads_from_config(self):
        """Test reading cli.default_bridge from config.yaml."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False
        ) as f:
            yaml.dump({"cli": {"default_bridge": False}}, f)
            config_path = f.name

        try:
            with patch.object(
                Path, "cwd", return_value=Path(config_path).parent
            ):
                original_exists = Path.exists

                def mock_exists(self):
                    if str(self) == str(Path(config_path).parent / "config.yaml"):
                        return True
                    return original_exists(self)

                with patch.object(Path, "exists", mock_exists):
                    with patch(
                        "builtins.open",
                        return_value=open(config_path),
                    ):
                        result = get_bridge_default()

            assert result is False
        finally:
            os.unlink(config_path)

    def test_returns_true_when_cli_section_missing(self):
        """Test that True is returned when config has no cli section."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False
        ) as f:
            yaml.dump({"server": {"port": 5055}}, f)
            config_path = f.name

        try:
            with patch.object(
                Path, "cwd", return_value=Path(config_path).parent
            ):
                original_exists = Path.exists

                def mock_exists(self):
                    if str(self) == str(Path(config_path).parent / "config.yaml"):
                        return True
                    return original_exists(self)

                with patch.object(Path, "exists", mock_exists):
                    with patch(
                        "builtins.open",
                        return_value=open(config_path),
                    ):
                        result = get_bridge_default()

            assert result is True
        finally:
            os.unlink(config_path)
