"""Permission command summarizer for generating meaningful permission dialog descriptions.

Pure-function module — no service registration needed. Provides pattern-matching
classification of tool permissions and safety classification for future auto-responder.
"""

import os
import re
import shlex
from urllib.parse import urlparse

# Maximum length for summary output
MAX_SUMMARY_LENGTH = 60


def summarize_permission_command(
    tool_name: str | None,
    tool_input: dict | None,
    pane_context: dict | None = None,
) -> str:
    """Generate a short summary of what a permission request will do.

    Args:
        tool_name: The tool requesting permission (e.g. "Bash", "Read")
        tool_input: The tool's input parameters dict
        pane_context: Optional parsed pane context with "command" and "description" keys

    Returns:
        A short summary string (max ~60 chars), e.g. "Bash: curl from localhost:5055"
    """
    if not tool_name:
        return "Permission needed"

    # If pane_context has a description from Claude Code's UI, prefer it
    if pane_context and pane_context.get("description"):
        desc = pane_context["description"].strip()
        if desc:
            summary = f"{tool_name}: {desc}"
            return _truncate(summary)

    tool_input = tool_input or {}

    if tool_name == "Bash":
        return _summarize_bash(tool_input)
    elif tool_name == "Read":
        return _summarize_file_op("Read", tool_input.get("file_path", ""))
    elif tool_name == "Write":
        return _summarize_file_op("Write", tool_input.get("file_path", ""))
    elif tool_name == "Edit":
        return _summarize_file_op("Edit", tool_input.get("file_path", ""))
    elif tool_name in ("Glob", "Grep"):
        pattern = tool_input.get("pattern", "")
        return _truncate(f"Search: {pattern}") if pattern else f"Search: {tool_name.lower()}"
    elif tool_name in ("WebFetch", "WebSearch"):
        return _summarize_web(tool_name, tool_input)
    elif tool_name == "NotebookEdit":
        return _summarize_file_op("NotebookEdit", tool_input.get("notebook_path", ""))
    else:
        return f"Permission: {tool_name}"


def classify_safety(tool_name: str | None, tool_input: dict | None) -> str:
    """Classify the safety level of a permission request.

    Returns:
        One of: "safe_read", "safe_write", "destructive", "unknown"
    """
    if not tool_name:
        return "unknown"

    tool_input = tool_input or {}

    # Read-only tools
    if tool_name in ("Read", "Glob", "Grep", "WebFetch", "WebSearch"):
        return "safe_read"

    # Write tools
    if tool_name in ("Write", "Edit", "NotebookEdit"):
        return "safe_write"

    if tool_name == "Bash":
        return _classify_bash_safety(tool_input)

    return "unknown"


# --- Bash command parsing ---

def _summarize_bash(tool_input: dict) -> str:
    """Summarize a Bash permission request from its command string."""
    command = tool_input.get("command", "")
    if not command or not command.strip():
        return "Bash: (empty command)"

    # Get the primary command (first in a pipe chain)
    primary = _extract_primary_command(command)
    if not primary:
        return _truncate(f"Bash: {command}")

    cmd_name = primary[0]
    args = primary[1:]

    # Match against known command patterns
    summary = _match_bash_command(cmd_name, args, command)
    if summary:
        return _truncate(summary)

    # Fallback: use the raw command, truncated
    return _truncate(f"Bash: {command}")


def _extract_primary_command(command: str) -> list[str] | None:
    """Extract the first command from a potentially piped command string.

    Returns tokenized first command, or None on parse failure.
    """
    # Split on pipe, take first command
    pipe_parts = command.split("|")
    first_cmd = pipe_parts[0].strip()

    # Split on && or ;, take first command
    for sep in ("&&", ";"):
        first_cmd = first_cmd.split(sep)[0].strip()

    # Strip leading env vars (FOO=bar cmd ...)
    while re.match(r"^\w+=\S+\s+", first_cmd):
        first_cmd = re.sub(r"^\w+=\S+\s+", "", first_cmd, count=1)

    try:
        tokens = shlex.split(first_cmd)
        return tokens if tokens else None
    except ValueError:
        # shlex can't parse (unmatched quotes, etc.) — split naively
        tokens = first_cmd.split()
        return tokens if tokens else None


def _match_bash_command(cmd_name: str, args: list[str], full_command: str) -> str | None:
    """Match a bash command name against known patterns and return a summary."""
    # Strip path prefix (e.g. /usr/bin/curl -> curl)
    base_cmd = os.path.basename(cmd_name)

    # HTTP clients
    if base_cmd in ("curl", "wget", "http", "httpie"):
        return _summarize_http(base_cmd, args)

    # File readers
    if base_cmd in ("cat", "head", "tail", "less", "more", "bat"):
        target = _first_file_arg(args)
        if target:
            return f"Bash: read {os.path.basename(target)}"
        return f"Bash: {base_cmd}"

    # Directory listing
    if base_cmd in ("ls", "find", "tree", "fd"):
        target = _first_path_arg(args)
        if target:
            return f"Bash: list {_abbreviate_path(target)}"
        return f"Bash: {base_cmd}"

    # Git
    if base_cmd == "git":
        subcmd = _first_non_flag(args)
        return f"Bash: git {subcmd}" if subcmd else "Bash: git"

    # Package managers
    if base_cmd in ("npm", "yarn", "pnpm", "pip", "pip3", "brew", "cargo", "gem", "go"):
        subcmd = _first_non_flag(args)
        return f"Bash: {base_cmd} {subcmd}" if subcmd else f"Bash: {base_cmd}"

    # File operations
    if base_cmd in ("mkdir", "rm", "mv", "cp", "ln", "chmod", "chown"):
        target = _last_path_arg(args)
        if target:
            return f"Bash: {base_cmd} {os.path.basename(target)}"
        return f"Bash: {base_cmd}"

    # Script runners
    if base_cmd in ("python", "python3", "node", "ruby", "perl", "bash", "sh", "zsh"):
        script = _first_file_arg(args)
        if script:
            return f"Bash: run {os.path.basename(script)}"
        return f"Bash: {base_cmd}"

    # Text transforms
    if base_cmd in ("sed", "awk", "sort", "uniq", "wc", "tr", "cut"):
        target = _first_file_arg(args)
        if target:
            return f"Bash: transform {os.path.basename(target)}"
        return f"Bash: {base_cmd}"

    # Container tools
    if base_cmd in ("docker", "kubectl", "podman"):
        subcmd = _first_non_flag(args)
        return f"Bash: {base_cmd} {subcmd}" if subcmd else f"Bash: {base_cmd}"

    # Build tools
    if base_cmd in ("make", "cmake", "gradle", "mvn"):
        target = _first_non_flag(args)
        return f"Bash: {base_cmd} {target}" if target else f"Bash: {base_cmd}"

    # Test runners
    if base_cmd in ("pytest", "jest", "mocha", "rspec"):
        target = _first_non_flag(args)
        if target:
            return f"Bash: {base_cmd} {os.path.basename(target)}"
        return f"Bash: {base_cmd}"

    # Database clients
    if base_cmd in ("psql", "mysql", "sqlite3", "redis-cli", "mongosh"):
        return f"Bash: {base_cmd}"

    return None


def _summarize_http(cmd_name: str, args: list[str]) -> str:
    """Summarize curl/wget by extracting the target host."""
    for arg in args:
        if arg.startswith(("-", "--")):
            continue
        try:
            parsed = urlparse(arg if "://" in arg else f"http://{arg}")
            host = parsed.hostname or arg
            # Include port if non-standard
            if parsed.port and parsed.port not in (80, 443):
                host = f"{host}:{parsed.port}"
            return f"Bash: {cmd_name} from {host}"
        except Exception:
            continue
    return f"Bash: {cmd_name}"


def _summarize_web(tool_name: str, tool_input: dict) -> str:
    """Summarize WebFetch/WebSearch tools."""
    if tool_name == "WebFetch":
        url = tool_input.get("url", "")
        if url:
            try:
                parsed = urlparse(url)
                host = parsed.hostname or url
                return f"Web: fetch {host}"
            except Exception:
                pass
        return "Web: fetch"
    else:  # WebSearch
        query = tool_input.get("query", "")
        if query:
            return _truncate(f"Web: search '{query}'")
        return "Web: search"


# --- File/path helpers ---

def _summarize_file_op(tool_name: str, file_path: str) -> str:
    """Summarize a file operation (Read/Write/Edit) with abbreviated path."""
    if not file_path:
        return f"{tool_name}: (no path)"
    return _truncate(f"{tool_name}: {_abbreviate_path(file_path)}")


def _abbreviate_path(path: str) -> str:
    """Abbreviate a file path for display.

    Keeps the last 2 path components for readability.
    Replaces common temp/scratchpad prefixes.
    """
    if not path:
        return ""

    # Flag temp/scratchpad paths
    if "/tmp/" in path or "/scratchpad/" in path:
        basename = os.path.basename(path)
        return f"(temp) {basename}" if basename else "(temp file)"

    # Keep last 2 components
    parts = path.rstrip("/").split("/")
    if len(parts) <= 2:
        return path
    return "/".join(parts[-2:])


def _first_file_arg(args: list[str]) -> str | None:
    """Find the first non-flag argument that looks like a file path."""
    skip_next = False
    for arg in args:
        if skip_next:
            skip_next = False
            continue
        if arg.startswith("-"):
            # Flags that take a value argument (skip the next arg)
            if arg in ("-n", "-c", "-e", "-o", "-p", "-s", "-t", "-w",
                        "--lines", "--bytes", "--output", "--file"):
                skip_next = True
            continue
        # Must look like a file path (contains / or . with extension, or starts with ./)
        if "/" in arg or re.match(r"^[\w.-]+\.[\w]+$", arg) or arg.startswith("./"):
            # Skip sed/awk expressions
            if arg.startswith("s/") or arg.startswith("'s/") or arg.startswith('"s/'):
                continue
            return arg
    return None


def _first_path_arg(args: list[str]) -> str | None:
    """Find the first non-flag argument (path-like)."""
    for arg in args:
        if not arg.startswith("-"):
            return arg
    return None


def _last_path_arg(args: list[str]) -> str | None:
    """Find the last non-flag argument (typically the target in cp/mv/rm)."""
    last = None
    for arg in args:
        if not arg.startswith("-"):
            last = arg
    return last


def _first_non_flag(args: list[str]) -> str | None:
    """Find the first argument that isn't a flag."""
    for arg in args:
        if not arg.startswith("-"):
            return arg
    return None


def _truncate(text: str, max_length: int = MAX_SUMMARY_LENGTH) -> str:
    """Truncate text to max_length, adding ellipsis if needed."""
    if len(text) <= max_length:
        return text
    return text[: max_length - 3] + "..."


# --- Bash safety classification ---

_SAFE_READ_COMMANDS = frozenset({
    "cat", "head", "tail", "less", "more", "bat",
    "ls", "find", "tree", "fd", "wc", "file",
    "which", "whereis", "type", "whoami", "id",
    "echo", "printf", "date", "uname", "hostname",
    "pwd", "env", "printenv",
    "sort", "uniq", "tr", "cut", "grep", "rg", "ag",
    "diff", "comm",
})

_SAFE_READ_GIT = frozenset({
    "status", "log", "diff", "show", "branch", "tag",
    "describe", "rev-parse", "ls-files", "ls-tree",
    "stash", "reflog", "shortlog", "blame",
})

_DESTRUCTIVE_COMMANDS = frozenset({
    "rm", "rmdir", "shred",
    "dd",
    "truncate",
})

_DESTRUCTIVE_GIT = frozenset({
    "push", "reset", "clean", "checkout",
    "rebase", "merge", "cherry-pick",
})


def _classify_bash_safety(tool_input: dict) -> str:
    """Classify a Bash command's safety level."""
    command = tool_input.get("command", "")
    if not command:
        return "unknown"

    primary = _extract_primary_command(command)
    if not primary:
        return "unknown"

    base_cmd = os.path.basename(primary[0])
    args = primary[1:]

    # Explicitly safe read commands
    if base_cmd in _SAFE_READ_COMMANDS:
        return "safe_read"

    # curl/wget without -X POST/PUT/DELETE or -d/--data are reads
    if base_cmd in ("curl", "wget"):
        cmd_str = " ".join([base_cmd] + args).lower()
        if any(flag in cmd_str for flag in ("-x post", "-x put", "-x delete", "-d ", "--data")):
            return "safe_write"
        return "safe_read"

    # Git subcommand classification
    if base_cmd == "git":
        subcmd = _first_non_flag(args)
        if subcmd in _SAFE_READ_GIT:
            return "safe_read"
        if subcmd in _DESTRUCTIVE_GIT:
            # Check for --force
            if any("force" in a.lower() for a in args):
                return "destructive"
            return "safe_write"
        if subcmd in ("add", "commit"):
            return "safe_write"
        return "unknown"

    # Destructive commands
    if base_cmd in _DESTRUCTIVE_COMMANDS:
        return "destructive"

    # Package managers: install/uninstall
    if base_cmd in ("pip", "pip3", "npm", "yarn", "brew"):
        subcmd = _first_non_flag(args)
        if subcmd in ("install", "add", "uninstall", "remove"):
            return "safe_write"
        return "unknown"

    # Script runners, test runners, build tools — generally safe writes
    if base_cmd in ("python", "python3", "node", "ruby", "pytest", "jest", "make"):
        return "safe_write"

    return "unknown"
