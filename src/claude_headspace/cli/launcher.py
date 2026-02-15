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
import urllib3
import yaml

# Suppress InsecureRequestWarning for localhost TLS connections
# (cert is for Tailscale hostname, not localhost)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Exit codes
EXIT_SUCCESS = 0
EXIT_ERROR = 1
EXIT_SERVER_UNREACHABLE = 2
EXIT_CLAUDE_NOT_FOUND = 3
EXIT_REGISTRATION_FAILED = 4

# Sentinel for bridge fallback (tmux not installed but bridge was requested)
BRIDGE_FALLBACK = -1

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
        Server URL (e.g., "https://127.0.0.1:5055")
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
                    # Prefer hooks.endpoint_url (the internal API endpoint)
                    endpoint_url = config.get("hooks", {}).get("endpoint_url")
                    if endpoint_url:
                        return endpoint_url.rstrip("/")
                    host = config.get("server", {}).get("host", "127.0.0.1")
                    port = config.get("server", {}).get("port", 5055)
                    return f"https://{host}:{port}"
            except Exception as e:
                logging.debug(f"Config parse failed for {config_path}: {e}")
                continue

    # Default
    return "https://127.0.0.1:5055"


def get_bridge_default() -> bool:
    """
    Get the default bridge mode from config.

    Reads ``cli.default_bridge`` from config.yaml using the same
    3-path search as ``get_server_url()``.

    Returns:
        True if bridge should be enabled by default (also the fallback
        when no config is found).
    """
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
                    return config.get("cli", {}).get("default_bridge", True)
            except Exception as e:
                logging.debug(f"Config parse failed for {config_path}: {e}")
                continue

    return True


def get_bridge_default() -> bool:
    """
    Get the default bridge mode from config.

    Reads ``cli.default_bridge`` from config.yaml using the same
    3-path search as ``get_server_url()``.

    Returns:
        True if bridge should be enabled by default (also the fallback
        when no config is found).
    """
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
                    return config.get("cli", {}).get("default_bridge", True)
            except Exception as e:
                logging.debug(f"Config parse failed for {config_path}: {e}")
                continue

    return True


def get_project_info() -> ProjectInfo:
    """
    Detect project information from the current working directory.

    Attempts to get project name and branch from git. Falls back to
    directory name if not in a git repository.

    Returns:
        ProjectInfo with name, path, and optional branch
    """
    cwd = Path(os.getcwd())  # os.getcwd() preserves symlinks; Path.cwd().absolute() resolves them
    project_path = str(cwd)
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


def get_tmux_pane_id() -> str | None:
    """
    Get the tmux pane ID from environment.

    Returns:
        tmux pane ID (e.g., "%0", "%5") if running in tmux, None otherwise
    """
    pane_id = os.environ.get("TMUX_PANE")
    return pane_id if pane_id else None


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
        response = requests.get(f"{server_url}/health", timeout=HTTP_TIMEOUT, verify=False)
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
    *,
    tmux_pane_id: str | None = None,
) -> tuple[bool, dict | None, str | None]:
    """
    Register a session with the Flask server.

    Args:
        server_url: URL of the Flask server
        session_uuid: UUID for this session
        project_info: Project information
        iterm_pane_id: Optional iTerm pane ID
        tmux_pane_id: Optional tmux pane ID for input bridge

    Returns:
        Tuple of (success, response_data, error_message)
    """
    payload = {
        "session_uuid": str(session_uuid),
        "project_path": project_info.path,
        "working_directory": os.getcwd(),
        "project_name": project_info.name,
        "current_branch": project_info.branch,
    }

    if iterm_pane_id:
        payload["iterm_pane_id"] = iterm_pane_id

    if tmux_pane_id:
        payload["tmux_pane_id"] = tmux_pane_id

    try:
        response = requests.post(
            f"{server_url}/api/sessions",
            json=payload,
            timeout=HTTP_TIMEOUT,
            verify=False,
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
            verify=False,
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


def launch_claude(claude_args: list[str], env: dict) -> int:
    """
    Launch Claude Code as a child process.

    Args:
        claude_args: Additional arguments to pass to claude
        env: Environment variables

    Returns:
        Exit code from claude process
    """
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


def _wrap_in_tmux(args: argparse.Namespace) -> int:
    """
    Re-execute the CLI inside a new tmux session.

    Called when --bridge is requested but $TMUX_PANE is not set.
    Uses os.execvp to replace the current process with tmux,
    which runs the same CLI command inside a new session.

    Args:
        args: Parsed command line arguments (unused, kept for signature consistency)

    Returns:
        EXIT_ERROR if tmux is not installed (execvp does not return on success)
    """
    if not shutil.which("tmux"):
        print(
            "\n"
            "╔══════════════════════════════════════════════════════════════╗\n"
            "║  WARNING: tmux is not installed                             ║\n"
            "║                                                             ║\n"
            "║  The Input Bridge (respond from dashboard) is disabled.     ║\n"
            "║  Install tmux for the full experience:                      ║\n"
            "║                                                             ║\n"
            "║    brew install tmux                                        ║\n"
            "║                                                             ║\n"
            "║  Or use --no-bridge to suppress this warning.               ║\n"
            "╚══════════════════════════════════════════════════════════════╝\n",
            file=sys.stderr,
        )
        return BRIDGE_FALLBACK

    project_info = get_project_info()
    session_name = f"hs-{project_info.name}-{uuid.uuid4().hex[:8]}"

    # Resolve the CLI entry point for re-execution
    cli_path = shutil.which("claude-headspace") or sys.argv[0]

    print(f"Starting tmux session: {session_name}")

    try:
        os.execvp(
            "tmux",
            [
                "tmux", "new-session",
                "-s", session_name,
                "-c", project_info.path,
                "-e", f"CLAUDE_HEADSPACE_TMUX_SESSION={session_name}",
                "--",
            ]
            + [cli_path]
            + sys.argv[1:],
        )
    except OSError as e:
        print(f"Error: Failed to start tmux session: {e}", file=sys.stderr)
        return EXIT_ERROR

    # execvp does not return on success; this is unreachable
    return EXIT_ERROR  # pragma: no cover


def cmd_start(args: argparse.Namespace) -> int:
    """
    Handle the 'start' command.

    Args:
        args: Parsed command line arguments

    Returns:
        Exit code
    """
    # Resolve bridge mode: --no-bridge > --bridge > config > default (True)
    no_bridge = getattr(args, "no_bridge", False)
    explicit_bridge = getattr(args, "bridge", False)

    if no_bridge:
        bridge_enabled = False
    elif explicit_bridge:
        bridge_enabled = True
    else:
        bridge_enabled = get_bridge_default()

    # Auto-wrap in tmux for bridge mode
    if bridge_enabled and not os.environ.get("TMUX_PANE"):
        result = _wrap_in_tmux(args)
        if result == BRIDGE_FALLBACK:
            # tmux not installed — continue without bridge
            bridge_enabled = False
        else:
            return result

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

    # Detect tmux pane for Input Bridge
    tmux_pane_id = None
    if bridge_enabled:
        tmux_pane_id = get_tmux_pane_id()
        if tmux_pane_id:
            print(f"Input Bridge: enabled (tmux pane {tmux_pane_id})")
        else:
            print(
                "Input Bridge: unavailable (not in tmux session)",
                file=sys.stderr,
            )
    else:
        if no_bridge:
            print("Input Bridge: disabled (--no-bridge)")

    # Generate session UUID
    session_uuid = uuid.uuid4()
    print(f"Session: {session_uuid}")

    # Register session
    success, response_data, error = register_session(
        server_url, session_uuid, project_info, iterm_pane_id,
        tmux_pane_id=tmux_pane_id,
    )

    if not success:
        print(f"Error: Failed to register session: {error}", file=sys.stderr)
        return EXIT_REGISTRATION_FAILED

    print(f"Registered agent #{response_data['agent_id']}")

    # Set up environment
    env = setup_environment(server_url, session_uuid)

    # Launch claude with session management
    with SessionManager(server_url, session_uuid):
        exit_code = launch_claude(args.claude_args, env)

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
        "--bridge",
        action="store_true",
        default=False,
        help=(
            "(default) Enable tmux-based Input Bridge. This is now the "
            "default and this flag is kept for backwards compatibility."
        ),
    )
    start_parser.add_argument(
        "--no-bridge",
        action="store_true",
        default=False,
        dest="no_bridge",
        help="Disable tmux bridge. Run without dashboard respond capability.",
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
