"""
Claude Headspace CLI launcher.

Launches Claude Code sessions with monitoring integration.
Registers sessions with the Flask server and sets up environment
variables for hooks integration.
"""

import argparse
import logging
import os
import shutil
import signal
import subprocess
import sys
import uuid
from pathlib import Path
from typing import NamedTuple

import requests
import yaml

# Exit codes
EXIT_SUCCESS = 0
EXIT_ERROR = 1
EXIT_SERVER_UNREACHABLE = 2
EXIT_CLAUDE_NOT_FOUND = 3
EXIT_REGISTRATION_FAILED = 4

# HTTP timeout for API calls (seconds)
HTTP_TIMEOUT = 2

logger = logging.getLogger(__name__)


class ProjectInfo(NamedTuple):
    """Information about the current project."""

    name: str
    path: str
    branch: str | None


def get_server_url() -> str:
    """
    Get the Flask server URL from config or environment.

    Returns:
        Server URL (e.g., "http://127.0.0.1:5055")
    """
    # Check environment first
    env_url = os.environ.get("CLAUDE_HEADSPACE_URL")
    if env_url:
        return env_url.rstrip("/")

    # Try to load from config.yaml
    config_paths = [
        Path.cwd() / "config.yaml",
        Path(__file__).parent.parent.parent.parent.parent / "config.yaml",
        Path.home() / ".claude-headspace" / "config.yaml",
    ]

    for config_path in config_paths:
        if config_path.exists():
            try:
                with open(config_path) as f:
                    config = yaml.safe_load(f)
                    host = config.get("server", {}).get("host", "127.0.0.1")
                    port = config.get("server", {}).get("port", 5055)
                    return f"http://{host}:{port}"
            except Exception:
                continue

    # Default
    return "http://127.0.0.1:5055"


def get_project_info() -> ProjectInfo:
    """
    Detect project information from the current working directory.

    Attempts to get project name and branch from git. Falls back to
    directory name if not in a git repository.

    Returns:
        ProjectInfo with name, path, and optional branch
    """
    cwd = Path.cwd()
    project_path = str(cwd.absolute())
    project_name = cwd.name
    branch = None

    # Try to get info from git
    try:
        # Get the git root directory
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            git_root = Path(result.stdout.strip())
            project_name = git_root.name
            project_path = str(git_root.absolute())

            # Get current branch
            result = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                branch = result.stdout.strip()

    except (subprocess.TimeoutExpired, FileNotFoundError):
        # Git not available or timed out, use directory name
        pass

    return ProjectInfo(name=project_name, path=project_path, branch=branch)


def get_iterm_pane_id() -> str | None:
    """
    Get the iTerm2 pane identifier from environment.

    Returns:
        iTerm pane ID if running in iTerm2, None otherwise
    """
    pane_id = os.environ.get("ITERM_SESSION_ID")

    if not pane_id:
        print(
            "Warning: Not running in iTerm2 (ITERM_SESSION_ID not set). "
            "Click-to-focus will not work.",
            file=sys.stderr,
        )

    return pane_id


def verify_claude_cli() -> bool:
    """
    Verify that the claude CLI is available.

    Returns:
        True if claude command is found, False otherwise
    """
    try:
        result = subprocess.run(
            ["which", "claude"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def detect_claudec() -> str | None:
    """
    Detect whether claudec (claude-commander) is available in PATH.

    Returns:
        Full path to claudec binary, or None if not found
    """
    return shutil.which("claudec")


def validate_prerequisites(server_url: str) -> tuple[bool, str | None]:
    """
    Validate that all prerequisites are met.

    Args:
        server_url: URL of the Flask server

    Returns:
        Tuple of (success, error_message)
    """
    # Check Flask server is reachable
    try:
        response = requests.get(f"{server_url}/health", timeout=HTTP_TIMEOUT)
        if response.status_code != 200:
            return False, f"Server returned status {response.status_code}"
    except requests.exceptions.ConnectionError:
        return False, f"Cannot connect to server at {server_url}"
    except requests.exceptions.Timeout:
        return False, f"Server at {server_url} timed out"
    except Exception as e:
        return False, f"Error checking server: {e}"

    # Check claude CLI
    if not verify_claude_cli():
        return False, "claude CLI not found. Install Claude Code first."

    return True, None


def register_session(
    server_url: str,
    session_uuid: uuid.UUID,
    project_info: ProjectInfo,
    iterm_pane_id: str | None,
) -> tuple[bool, dict | None, str | None]:
    """
    Register a session with the Flask server.

    Args:
        server_url: URL of the Flask server
        session_uuid: UUID for this session
        project_info: Project information
        iterm_pane_id: Optional iTerm pane ID

    Returns:
        Tuple of (success, response_data, error_message)
    """
    payload = {
        "session_uuid": str(session_uuid),
        "project_path": project_info.path,
        "working_directory": str(Path.cwd().absolute()),
        "project_name": project_info.name,
        "current_branch": project_info.branch,
    }

    if iterm_pane_id:
        payload["iterm_pane_id"] = iterm_pane_id

    try:
        response = requests.post(
            f"{server_url}/api/sessions",
            json=payload,
            timeout=HTTP_TIMEOUT,
        )

        if response.status_code == 201:
            return True, response.json(), None
        else:
            error_data = response.json() if response.text else {}
            error_msg = error_data.get("error", f"Status {response.status_code}")
            return False, None, error_msg

    except requests.exceptions.ConnectionError:
        return False, None, f"Cannot connect to server at {server_url}"
    except requests.exceptions.Timeout:
        return False, None, "Server timed out"
    except Exception as e:
        return False, None, str(e)


def cleanup_session(server_url: str, session_uuid: uuid.UUID) -> None:
    """
    Clean up session when exiting.

    Args:
        server_url: URL of the Flask server
        session_uuid: UUID of the session to clean up
    """
    try:
        response = requests.delete(
            f"{server_url}/api/sessions/{session_uuid}",
            timeout=HTTP_TIMEOUT,
        )
        if response.status_code == 200:
            logger.info(f"Session {session_uuid} cleaned up successfully")
        else:
            logger.warning(f"Cleanup returned status {response.status_code}")
    except Exception as e:
        # Non-blocking - log warning but don't crash
        logger.warning(f"Failed to clean up session: {e}")


def setup_environment(server_url: str, session_uuid: uuid.UUID) -> dict:
    """
    Set up environment variables for Claude Code.

    Args:
        server_url: URL of the Flask server
        session_uuid: UUID for this session

    Returns:
        Dictionary of environment variables to set
    """
    env = os.environ.copy()
    env["CLAUDE_HEADSPACE_URL"] = server_url
    env["CLAUDE_HEADSPACE_SESSION_ID"] = str(session_uuid)
    return env


def launch_claude(
    claude_args: list[str], env: dict, claudec_path: str | None = None
) -> int:
    """
    Launch Claude Code as a child process.

    If claudec_path is provided, wraps claude with claudec for Input Bridge
    support (PTY + commander socket).

    Args:
        claude_args: Additional arguments to pass to claude
        env: Environment variables
        claudec_path: Path to claudec binary, or None to launch claude directly

    Returns:
        Exit code from claude process
    """
    if claudec_path:
        cmd = [claudec_path, "claude"] + claude_args
    else:
        cmd = ["claude"] + claude_args
    logger.info(f"Launching: {' '.join(cmd)}")

    try:
        # Use subprocess.call to wait for process and get exit code
        return subprocess.call(cmd, env=env)
    except KeyboardInterrupt:
        # Will be handled by signal handler
        return 130  # Standard exit code for SIGINT
    except Exception as e:
        logger.error(f"Error launching claude: {e}")
        return EXIT_ERROR


class SessionManager:
    """Manages session lifecycle with cleanup on exit."""

    def __init__(self, server_url: str, session_uuid: uuid.UUID):
        self.server_url = server_url
        self.session_uuid = session_uuid
        self._original_sigint = None
        self._original_sigterm = None
        self._cleaned_up = False

    def __enter__(self):
        """Set up signal handlers."""
        self._original_sigint = signal.signal(signal.SIGINT, self._handle_signal)
        self._original_sigterm = signal.signal(signal.SIGTERM, self._handle_signal)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Restore signal handlers and clean up."""
        # Restore original handlers
        if self._original_sigint:
            signal.signal(signal.SIGINT, self._original_sigint)
        if self._original_sigterm:
            signal.signal(signal.SIGTERM, self._original_sigterm)

        # Clean up session
        self._cleanup()
        return False

    def _handle_signal(self, signum, frame):
        """Handle SIGINT and SIGTERM."""
        self._cleanup()
        # Re-raise the signal to allow normal termination
        if signum == signal.SIGINT:
            sys.exit(130)
        else:
            sys.exit(143)

    def _cleanup(self):
        """Clean up the session (idempotent)."""
        if not self._cleaned_up:
            self._cleaned_up = True
            cleanup_session(self.server_url, self.session_uuid)


def cmd_start(args: argparse.Namespace) -> int:
    """
    Handle the 'start' command.

    Args:
        args: Parsed command line arguments

    Returns:
        Exit code
    """
    # Get server URL
    server_url = get_server_url()
    print(f"Server: {server_url}")

    # Validate prerequisites
    valid, error = validate_prerequisites(server_url)
    if not valid:
        print(f"Error: {error}", file=sys.stderr)
        if "Cannot connect" in (error or "") or "timed out" in (error or ""):
            return EXIT_SERVER_UNREACHABLE
        if "claude CLI not found" in (error or ""):
            return EXIT_CLAUDE_NOT_FOUND
        return EXIT_ERROR

    # Get project info
    project_info = get_project_info()
    print(f"Project: {project_info.name}")
    if project_info.branch:
        print(f"Branch: {project_info.branch}")

    # Get iTerm pane ID
    iterm_pane_id = get_iterm_pane_id()

    # Generate session UUID
    session_uuid = uuid.uuid4()
    print(f"Session: {session_uuid}")

    # Register session
    success, response_data, error = register_session(
        server_url, session_uuid, project_info, iterm_pane_id
    )

    if not success:
        print(f"Error: Failed to register session: {error}", file=sys.stderr)
        return EXIT_REGISTRATION_FAILED

    print(f"Registered agent #{response_data['agent_id']}")

    # Detect claudec for Input Bridge
    claudec_path = detect_claudec()
    if claudec_path:
        print(f"Input Bridge: enabled (claudec detected)")
    else:
        print(f"Input Bridge: unavailable (claudec not found)")

    # Set up environment
    env = setup_environment(server_url, session_uuid)

    # Launch claude with session management
    with SessionManager(server_url, session_uuid):
        exit_code = launch_claude(args.claude_args, env, claudec_path=claudec_path)

    print(f"Session ended (exit code: {exit_code})")
    return EXIT_SUCCESS if exit_code == 0 else exit_code


def create_parser() -> argparse.ArgumentParser:
    """Create the argument parser."""
    parser = argparse.ArgumentParser(
        prog="claude-headspace",
        description="Launch Claude Code sessions with monitoring integration.",
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # 'start' command
    start_parser = subparsers.add_parser(
        "start",
        help="Start a monitored Claude Code session",
    )
    start_parser.add_argument(
        "claude_args",
        nargs="*",
        default=[],
        help="Additional arguments to pass to claude (use -- to separate)",
    )

    return parser


def main(args: list[str] | None = None) -> int:
    """
    Main entry point for the CLI.

    Args:
        args: Command line arguments (defaults to sys.argv[1:])

    Returns:
        Exit code
    """
    # Set up basic logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(message)s",
    )

    parser = create_parser()

    # Handle -- separator for claude args
    if args is None:
        args = sys.argv[1:]

    # Split on -- if present
    if "--" in args:
        idx = args.index("--")
        our_args = args[:idx]
        claude_args = args[idx + 1 :]
    else:
        our_args = args
        claude_args = []

    parsed = parser.parse_args(our_args)

    # Add claude_args if we have them
    if claude_args:
        parsed.claude_args = claude_args
    elif not hasattr(parsed, "claude_args"):
        parsed.claude_args = []

    if parsed.command == "start":
        return cmd_start(parsed)
    elif parsed.command is None:
        parser.print_help()
        return EXIT_SUCCESS
    else:
        parser.print_help()
        return EXIT_ERROR


if __name__ == "__main__":
    sys.exit(main())
