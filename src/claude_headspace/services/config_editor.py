"""Config editor service for validation and persistence."""

import logging
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)


@dataclass
class FieldSchema:
    """Schema definition for a config field."""

    name: str
    field_type: str  # "string", "integer", "float", "boolean", "password"
    description: str
    required: bool = False
    min_value: int | float | None = None
    max_value: int | float | None = None
    default: Any = None
    help_text: str = ""


@dataclass
class SectionSchema:
    """Schema definition for a config section."""

    name: str
    title: str
    fields: list[FieldSchema]
    section_description: str = ""


@dataclass
class ValidationError:
    """Validation error for a config field."""

    section: str
    field: str
    message: str


@dataclass
class ValidationResult:
    """Result of config validation."""

    valid: bool
    errors: list[ValidationError]


# Config schema definition
CONFIG_SCHEMA = [
    SectionSchema(
        name="server",
        title="Server",
        section_description="Core web server settings. Changes require a server restart to take effect.",
        fields=[
            FieldSchema("host", "string", "Server bind address", default="127.0.0.1",
                         help_text="The network interface to bind to. Use 0.0.0.0 to accept connections from any interface, or 127.0.0.1 for localhost only. Change this if you need to access the dashboard from other machines on your network."),
            FieldSchema("port", "integer", "Server port number", min_value=1, max_value=65535, default=5050,
                         help_text="The TCP port the web server listens on. Change if port 5050 conflicts with another service. Values below 1024 require root privileges."),
            FieldSchema("debug", "boolean", "Enable debug mode", default=False,
                         help_text="Enables Flask debug mode with auto-reload and detailed error pages. Enable during development for live code reloading. Disable in production as it exposes stack traces."),
        ],
    ),
    SectionSchema(
        name="logging",
        title="Logging",
        section_description="Controls application logging output and verbosity.",
        fields=[
            FieldSchema("level", "string", "Log level (DEBUG, INFO, WARNING, ERROR)", default="INFO",
                         help_text="Controls which log messages are recorded. DEBUG captures everything including LLM prompts, INFO records normal operations, WARNING shows potential issues, ERROR shows failures only. Lower levels produce much more output."),
            FieldSchema("file", "string", "Log file path", default="logs/app.log",
                         help_text="Path where log files are written. Relative paths are relative to the project root. Ensure the directory exists and is writable."),
        ],
    ),
    SectionSchema(
        name="database",
        title="Database",
        section_description="PostgreSQL connection settings. Changes require a server restart.",
        fields=[
            FieldSchema("host", "string", "Database host", default="localhost",
                         help_text="PostgreSQL server hostname or IP address. Use 'localhost' for a local database or a remote hostname/IP for external databases."),
            FieldSchema("port", "integer", "Database port", min_value=1, max_value=65535, default=5432,
                         help_text="PostgreSQL server port. The default PostgreSQL port is 5432. Only change if your database runs on a non-standard port."),
            FieldSchema("name", "string", "Database name", default="claude_headspace",
                         help_text="Name of the PostgreSQL database. Must already exist. Run 'flask db upgrade' after changing to apply migrations to the new database."),
            FieldSchema("user", "string", "Database user", default="postgres",
                         help_text="PostgreSQL username for authentication. Must have read/write access to the specified database."),
            FieldSchema("password", "password", "Database password", default="",
                         help_text="PostgreSQL password. Leave empty if using local peer authentication. This value is stored in config.yaml in plaintext."),
            FieldSchema("pool_size", "integer", "Connection pool size", min_value=1, max_value=100, default=10,
                         help_text="Number of persistent database connections maintained. Too low causes connection contention under load. Too high wastes database resources. 10 is suitable for most single-user setups."),
            FieldSchema("pool_timeout", "integer", "Pool timeout in seconds", min_value=1, max_value=300, default=30,
                         help_text="Seconds to wait for a connection from the pool before raising an error. Increase if you see pool timeout errors during high activity."),
        ],
    ),
    SectionSchema(
        name="claude",
        title="Claude",
        section_description="Paths used to locate Claude Code session data.",
        fields=[
            FieldSchema("projects_path", "string", "Path to Claude projects directory", default="~/.claude/projects",
                         help_text="Directory where Claude Code stores project-level state. This is the standard Claude Code path. Only change if you have a custom Claude Code installation."),
        ],
    ),
    SectionSchema(
        name="file_watcher",
        title="File Watcher",
        section_description="Controls how Claude Headspace monitors Claude Code session files for changes. The file watcher is the fallback mechanism when hooks are not active.",
        fields=[
            FieldSchema("polling_interval", "float", "Polling interval in seconds", min_value=0.1, max_value=60, default=2,
                         help_text="How often to check for file changes. Lower values detect changes faster but use more CPU. Too low (< 0.5s) causes excessive disk I/O. Too high (> 10s) makes the dashboard feel sluggish."),
            FieldSchema("reconciliation_interval", "integer", "Reconciliation interval in seconds", min_value=10, max_value=600, default=60,
                         help_text="How often to run a full reconciliation scan to catch any missed events. This is a safety net for the event-driven watcher. Lower values improve reliability but increase CPU usage."),
            FieldSchema("inactivity_timeout", "integer", "Inactivity timeout in seconds", min_value=60, max_value=86400, default=5400,
                         help_text="Stop watching a session after this much inactivity (default: 90 minutes). Prevents stale watchers from accumulating. Increase for long-running sessions that may pause."),
            FieldSchema("debounce_interval", "float", "Debounce interval in seconds", min_value=0.1, max_value=10, default=0.5,
                         help_text="Minimum time between processing file change events. Prevents duplicate processing when Claude Code writes multiple files in quick succession. Too low causes redundant work, too high delays detection."),
        ],
    ),
    SectionSchema(
        name="event_system",
        title="Event System",
        section_description="Controls the background event writer that persists audit events to PostgreSQL.",
        fields=[
            FieldSchema("write_retry_attempts", "integer", "Write retry attempts", min_value=1, max_value=10, default=3,
                         help_text="Number of times to retry writing an event to the database before giving up. Increase if you see transient database connection errors."),
            FieldSchema("write_retry_delay_ms", "integer", "Write retry delay in milliseconds", min_value=10, max_value=5000, default=100,
                         help_text="Milliseconds to wait between write retry attempts. Allows transient database issues to resolve before retrying."),
            FieldSchema("max_restarts_per_minute", "integer", "Max restarts per minute", min_value=1, max_value=60, default=5,
                         help_text="Maximum times the event writer thread can restart per minute. Prevents runaway restart loops if there is a persistent error."),
            FieldSchema("shutdown_timeout_seconds", "integer", "Shutdown timeout in seconds", min_value=1, max_value=60, default=2,
                         help_text="Seconds to wait for the event writer to flush pending events during shutdown. Increase if events are being lost during restarts."),
        ],
    ),
    SectionSchema(
        name="reaper",
        title="Agent Reaper",
        section_description="The agent reaper automatically cleans up agents that have gone silent, removing stale entries from the dashboard.",
        fields=[
            FieldSchema("enabled", "boolean", "Enable agent reaper (cleans up dead agents)", default=True,
                         help_text="When enabled, agents that haven't sent any activity within the inactivity timeout are automatically marked as ended and removed from the active dashboard."),
            FieldSchema("interval_seconds", "integer", "Seconds between reaper checks", min_value=10, max_value=600, default=60,
                         help_text="How often the reaper scans for inactive agents. Lower values detect dead agents faster. Too low wastes CPU on frequent scans."),
            FieldSchema("inactivity_timeout_seconds", "integer", "Reap agents inactive for this many seconds", min_value=60, max_value=3600, default=300,
                         help_text="Mark agents as ended after this much inactivity (default: 5 minutes). Too low causes premature reaping of slow-working agents. Too high leaves stale cards on the dashboard."),
            FieldSchema("grace_period_seconds", "integer", "Don't reap agents younger than this (seconds)", min_value=60, max_value=3600, default=300,
                         help_text="Newly created agents are protected from reaping for this long (default: 5 minutes). Prevents reaping agents that are initialising and haven't sent activity yet."),
        ],
    ),
    SectionSchema(
        name="sse",
        title="SSE",
        section_description="Server-Sent Events configuration for real-time dashboard updates.",
        fields=[
            FieldSchema("heartbeat_interval_seconds", "integer", "Heartbeat interval in seconds", min_value=1, max_value=300, default=30,
                         help_text="How often to send a keep-alive heartbeat to connected browsers. Prevents proxies and browsers from closing idle connections. Too low wastes bandwidth, too high may cause connection drops."),
            FieldSchema("max_connections", "integer", "Maximum SSE connections", min_value=1, max_value=1000, default=100,
                         help_text="Maximum number of simultaneous SSE connections. Each open browser tab uses one connection. Lower this if you're running low on file descriptors."),
            FieldSchema("connection_timeout_seconds", "integer", "Connection timeout in seconds", min_value=10, max_value=600, default=60,
                         help_text="Close SSE connections after this much inactivity. Clients will automatically reconnect. Helps clean up abandoned connections."),
            FieldSchema("retry_after_seconds", "integer", "Retry after seconds", min_value=1, max_value=60, default=5,
                         help_text="Tells the browser how long to wait before reconnecting after a connection drop. Lower values recover faster, higher values reduce reconnect storms during outages."),
        ],
    ),
    SectionSchema(
        name="hooks",
        title="Hooks",
        section_description="Claude Code lifecycle hooks provide real-time session events. When hooks are active, the file watcher reduces its polling frequency.",
        fields=[
            FieldSchema("enabled", "boolean", "Enable hook receiver", default=True,
                         help_text="Enable the HTTP hook receiver that Claude Code sends lifecycle events to. This is the primary mechanism for tracking sessions. Disable only if you want to rely solely on file watching."),
            FieldSchema("polling_interval_with_hooks", "integer", "Polling interval when hooks active (seconds)", min_value=10, max_value=600, default=60,
                         help_text="When hooks are actively sending events, the file watcher reduces to this polling rate as a fallback. Higher values save CPU since hooks handle most updates."),
            FieldSchema("fallback_timeout", "integer", "Fallback timeout in seconds", min_value=60, max_value=3600, default=300,
                         help_text="If no hook events are received within this time, the system falls back to full-speed file polling. Increase if your sessions have long idle periods where no hooks fire."),
        ],
    ),
    SectionSchema(
        name="voice_bridge",
        title="Voice Bridge",
        section_description="Voice Bridge is a PWA for hands-free voice interaction with agents from a mobile device. Requires a server restart after changes.",
        fields=[
            FieldSchema("enabled", "boolean", "Enable voice bridge services", default=False,
                         help_text="Enable voice bridge token authentication and voice-friendly response formatting. The /voice page loads regardless, but API responses won't include voice formatting when disabled."),
            FieldSchema("auth.token", "password", "Bearer token for API authentication", default="",
                         help_text="Bearer token required for voice bridge API calls. Leave empty for no authentication (only safe on localhost). Set a strong random string when accessing from other devices on your network."),
            FieldSchema("auth.localhost_bypass", "boolean", "Skip auth for localhost requests", default=True,
                         help_text="Skip token authentication for requests originating from localhost (127.0.0.1). Convenient for development. Disable to enforce token auth even for local requests."),
            FieldSchema("rate_limit.requests_per_minute", "integer", "Max API requests per minute", min_value=1, max_value=600, default=60,
                         help_text="Maximum voice bridge API requests per minute per token. Prevents runaway calls. Default of 60 is generous for normal voice interaction."),
            FieldSchema("default_verbosity", "string", "Default response verbosity (concise, normal, detailed)", default="concise",
                         help_text="Server-side default for response detail level. 'concise' gives brief status lines, 'normal' includes summaries, 'detailed' includes full output. The client can override this per-request."),
            FieldSchema("auto_target", "boolean", "Auto-target sole awaiting agent", default=False,
                         help_text="When enabled, voice commands without an explicit agent_id automatically target the sole awaiting agent. When disabled, the client must always specify which agent to target."),
        ],
    ),
    SectionSchema(
        name="tmux_bridge",
        title="Tmux Bridge",
        section_description="Controls the tmux-based text input bridge that sends responses to Claude Code sessions via tmux send-keys.",
        fields=[
            FieldSchema("health_check_interval", "integer", "Seconds between tmux pane availability checks", min_value=1, max_value=600, default=30,
                         help_text="How often to check if tmux panes are available for each agent. Lower values update availability status faster. Too low wastes CPU on frequent tmux subprocess calls."),
            FieldSchema("subprocess_timeout", "integer", "Timeout for tmux subprocess calls (seconds)", min_value=1, max_value=30, default=10,
                         help_text="Maximum seconds to wait for a tmux command to complete. Increase if you see timeout errors, but high values can block the thread if tmux hangs."),
            FieldSchema("text_enter_delay_ms", "integer", "Delay between sending text and pressing Enter (ms)", min_value=0, max_value=5000, default=100,
                         help_text="Milliseconds to wait between sending text and pressing Enter in tmux. Some terminals need a small delay to process text before the Enter key arrives. Increase if text appears garbled."),
        ],
    ),
    SectionSchema(
        name="dashboard",
        title="Dashboard",
        section_description="Controls dashboard display behaviour including stale state detection and agent timeout.",
        fields=[
            FieldSchema("stale_processing_seconds", "integer", "Stale processing timeout (seconds)", min_value=60, max_value=7200, default=600,
                         help_text="Agents in PROCESSING state for longer than this are displayed as TIMED_OUT on the dashboard (default: 10 minutes). This is a display-only indicator — the agent is not actually stopped. Increase if your agents routinely process for long periods."),
            FieldSchema("active_timeout_minutes", "integer", "Active timeout (minutes)", min_value=1, max_value=1440, default=5,
                         help_text="Minutes of inactivity before an agent is considered no longer active for dashboard display purposes. Affects which agents appear in the active count."),
        ],
    ),
    SectionSchema(
        name="archive",
        title="Archive",
        section_description="Controls archiving and retention of waypoints and other project artifacts.",
        fields=[
            FieldSchema("enabled", "boolean", "Enable archiving", default=True,
                         help_text="When enabled, waypoints and other artifacts are automatically archived with timestamps when updated. Disable to prevent archive files from accumulating."),
            FieldSchema("retention.policy", "string", "Retention policy", default="keep_last_n",
                         help_text="How archived files are retained. 'keep_all' keeps everything, 'keep_last_n' keeps the N most recent, 'days' deletes archives older than the specified number of days."),
            FieldSchema("retention.keep_last_n", "integer", "Keep last N archives", min_value=1, max_value=1000, default=10,
                         help_text="Number of recent archives to keep when using the 'keep_last_n' retention policy. Old archives beyond this count are deleted."),
            FieldSchema("retention.days", "integer", "Retention days", min_value=1, max_value=3650, default=90,
                         help_text="Delete archives older than this many days when using the 'days' retention policy. Does not apply when policy is 'keep_all' or 'keep_last_n'."),
        ],
    ),
    SectionSchema(
        name="commander",
        title="Commander (Input Bridge)",
        section_description="Controls the commander socket-based input bridge for sending responses to Claude Code sessions via Unix domain sockets.",
        fields=[
            FieldSchema("health_check_interval", "integer", "Seconds between socket availability checks", min_value=1, max_value=3600, default=30,
                         help_text="How often to check if commander sockets are available for each agent. Lower values detect commander availability changes faster. Too low wastes CPU on frequent socket probes."),
            FieldSchema("socket_timeout", "integer", "Socket operation timeout in seconds", min_value=1, max_value=30, default=2,
                         help_text="Maximum seconds to wait for a socket operation (connect/read/write) to complete. Increase if socket operations are timing out, but high values can block threads."),
            FieldSchema("socket_path_prefix", "string", "Socket path prefix (must match claudec convention)", default="/tmp/claudec-",
                         help_text="Path prefix for commander Unix domain sockets. Must match what the claudec binary uses. Only change if you have a custom claudec setup."),
        ],
    ),
    SectionSchema(
        name="notifications",
        title="Notifications",
        section_description="macOS desktop notifications via terminal-notifier. Alerts you when agents need input or complete tasks.",
        fields=[
            FieldSchema("enabled", "boolean", "Enable macOS notifications (requires terminal-notifier)", default=True,
                         help_text="Enable desktop notifications for agent events. Requires terminal-notifier to be installed via Homebrew (brew install terminal-notifier). Disable if you find notifications distracting."),
            FieldSchema("sound", "boolean", "Play sound with notifications", default=True,
                         help_text="Play the macOS notification sound when notifications are sent. Disable for silent notifications that only appear visually."),
            FieldSchema("rate_limit_seconds", "integer", "Minimum seconds between notifications per agent", min_value=0, max_value=60, default=5,
                         help_text="Minimum seconds between notifications for the same agent. Prevents notification spam when an agent rapidly changes state. Set to 0 to allow all notifications."),
        ],
    ),
    SectionSchema(
        name="activity",
        title="Activity Metrics",
        section_description="Background aggregation of hourly activity metrics at agent, project, and system-wide scope.",
        fields=[
            FieldSchema("enabled", "boolean", "Enable activity metrics aggregation", default=True,
                         help_text="Enable the background thread that computes hourly activity metrics. Disable if you don't use the activity dashboard and want to save CPU/database resources."),
            FieldSchema("interval_seconds", "integer", "Seconds between aggregation passes", min_value=10, max_value=3600, default=300,
                         help_text="How often the aggregator runs to compute metrics (default: 5 minutes). Lower values produce more up-to-date metrics. Too low wastes CPU on frequent database queries."),
            FieldSchema("retention_days", "integer", "Days to retain metric records before pruning", min_value=1, max_value=3650, default=30,
                         help_text="How long to keep activity metric records before they are pruned. Longer retention allows historical analysis but uses more database storage."),
        ],
    ),
    SectionSchema(
        name="headspace",
        title="Headspace",
        section_description="Headspace monitoring tracks frustration levels, detects flow state, and raises traffic-light alerts (green/yellow/red) based on agent interaction patterns.",
        fields=[
            FieldSchema("enabled", "boolean", "Enable headspace monitoring", default=True,
                         help_text="Enable frustration tracking, flow state detection, and traffic-light alerting. When disabled, no headspace snapshots are created and frustration scores are not computed."),
            FieldSchema("thresholds.yellow", "integer", "Yellow frustration threshold (0-10)", min_value=0, max_value=10, default=4,
                         help_text="Rolling frustration average above this triggers a yellow (caution) alert. Lower values make the system more sensitive to frustration. Set closer to the red threshold for less frequent warnings."),
            FieldSchema("thresholds.red", "integer", "Red frustration threshold (0-10)", min_value=0, max_value=10, default=7,
                         help_text="Rolling frustration average above this triggers a red (critical) alert. Should be higher than the yellow threshold. Indicates the developer may need to take a break or change approach."),
            FieldSchema("session_rolling_window_minutes", "integer", "Session rolling window duration (minutes)", min_value=10, max_value=1440, default=180,
                         help_text="Duration of the rolling window for the session-level frustration average (default: 3 hours). Longer windows smooth out spikes, shorter windows are more responsive to recent frustration."),
            FieldSchema("alert_cooldown_minutes", "integer", "Minutes between alerts", min_value=1, max_value=60, default=10,
                         help_text="Minimum time between frustration alerts for the same agent. Prevents alert fatigue from repeated notifications. Increase if alerts feel too frequent."),
            FieldSchema("snapshot_retention_days", "integer", "Days to retain snapshots", min_value=1, max_value=365, default=7,
                         help_text="How long to keep headspace snapshot records in the database. Longer retention enables historical analysis of frustration patterns."),
            FieldSchema("flow_detection.min_turn_rate", "integer", "Minimum turn rate for flow state (turns/hour)", min_value=1, max_value=60, default=6,
                         help_text="Minimum turns per hour required to consider an agent in flow state. Flow state requires sustained interaction. Too low detects false flow, too high misses legitimate flow periods."),
            FieldSchema("flow_detection.max_frustration", "float", "Maximum frustration for flow state", min_value=0, max_value=10, default=3.0,
                         help_text="Maximum rolling frustration score allowed during flow state. Flow state requires low frustration. Set higher if your workflow naturally has some friction."),
            FieldSchema("flow_detection.min_duration_minutes", "integer", "Minimum flow duration (minutes)", min_value=1, max_value=120, default=15,
                         help_text="Minimum sustained duration before flow state is declared. Prevents brief productive bursts from being flagged as flow. Increase for a stricter flow state definition."),
        ],
    ),
    SectionSchema(
        name="openrouter",
        title="Inference",
        section_description="LLM inference settings via OpenRouter API. Controls model selection, rate limiting, caching, and retry behaviour for AI-powered summaries and scoring.",
        fields=[
            FieldSchema("base_url", "string", "OpenRouter API base URL",
                         default="https://openrouter.ai/api/v1",
                         help_text="The OpenRouter API endpoint URL. Only change if using a proxy or alternative API-compatible service."),
            FieldSchema("timeout", "integer", "Request timeout (seconds)",
                         min_value=1, max_value=300, default=30,
                         help_text="Maximum seconds to wait for an LLM API response. Increase for complex prompts or during high API load. Too low causes frequent timeouts, too high blocks the inference queue."),
            FieldSchema("models.turn", "string", "Model for turn summaries",
                         default="anthropic/claude-3-haiku",
                         help_text="LLM model used for individual turn summaries and frustration scoring. Use a fast, cheap model (e.g. Haiku) since these are high-frequency calls."),
            FieldSchema("models.task", "string", "Model for task summaries",
                         default="anthropic/claude-3-haiku",
                         help_text="LLM model used for task-level summaries. Can be the same as the turn model or a slightly more capable model for better task synthesis."),
            FieldSchema("models.project", "string", "Model for project analysis",
                         default="anthropic/claude-3.5-sonnet",
                         help_text="LLM model used for project-level progress analysis and brain reboot generation. Use a capable model (e.g. Sonnet) since these are infrequent but require deeper reasoning."),
            FieldSchema("models.objective", "string", "Model for priority scoring",
                         default="anthropic/claude-3.5-sonnet",
                         help_text="LLM model used for cross-project priority scoring. Use a capable model for accurate ranking of agent priorities against the current objective."),
            FieldSchema("rate_limits.calls_per_minute", "integer", "Max API calls per minute",
                         min_value=1, max_value=1000, default=30,
                         help_text="Maximum LLM API calls per minute across all inference types. Prevents runaway costs. Increase if summaries are being delayed by rate limiting."),
            FieldSchema("rate_limits.tokens_per_minute", "integer", "Max tokens per minute",
                         min_value=1, max_value=1000000, default=50000,
                         help_text="Maximum tokens (input + output) per minute. Works alongside the calls-per-minute limit. Increase if large prompts are being throttled."),
            FieldSchema("cache.enabled", "boolean", "Enable inference result caching",
                         default=True,
                         help_text="Cache LLM responses using content-based hashing. Avoids redundant API calls for identical prompts. Disable if you need fresh responses every time."),
            FieldSchema("cache.ttl_seconds", "integer", "Cache TTL (seconds)",
                         min_value=1, max_value=3600, default=300,
                         help_text="How long cached inference results remain valid (default: 5 minutes). Shorter TTL means more API calls but fresher results. Longer TTL saves costs but may return stale summaries."),
            FieldSchema("retry.max_attempts", "integer", "Max retry attempts",
                         min_value=1, max_value=10, default=3,
                         help_text="Number of times to retry a failed LLM API call. Handles transient network errors and rate limit responses. Higher values improve reliability but delay failure detection."),
            FieldSchema("retry.base_delay_seconds", "float", "Base retry delay (seconds)",
                         min_value=0.1, max_value=60, default=1.0,
                         help_text="Initial delay before the first retry attempt. Subsequent retries use exponential backoff from this base. Too low may hit rate limits again immediately."),
            FieldSchema("retry.max_delay_seconds", "float", "Maximum retry delay (seconds)",
                         min_value=1, max_value=300, default=30.0,
                         help_text="Maximum delay between retry attempts (caps the exponential backoff). Prevents excessively long waits between retries."),
            FieldSchema("priority_scoring.debounce_seconds", "float", "Priority scoring debounce (seconds)",
                         min_value=0.1, max_value=60, default=5.0,
                         help_text="Minimum seconds between priority scoring runs. Prevents redundant scoring when multiple agents update in quick succession. Increase if scoring API calls are too frequent."),
        ],
    ),
]


def get_config_schema() -> list[dict]:
    """
    Get the config schema as a serializable list.

    Returns:
        List of section dictionaries with field information
    """
    result = []
    for section in CONFIG_SCHEMA:
        section_dict = {
            "name": section.name,
            "title": section.title,
            "section_description": section.section_description,
            "fields": [],
        }
        for field in section.fields:
            field_dict = {
                "name": field.name,
                "type": field.field_type,
                "description": field.description,
                "required": field.required,
                "default": field.default,
                "help_text": field.help_text,
            }
            if field.min_value is not None:
                field_dict["min"] = field.min_value
            if field.max_value is not None:
                field_dict["max"] = field.max_value
            section_dict["fields"].append(field_dict)
        result.append(section_dict)
    return result


def load_config_file(config_path: str | Path = "config.yaml") -> dict:
    """
    Load configuration from YAML file only (no env vars).

    Args:
        config_path: Path to config file

    Returns:
        Configuration dictionary from file
    """
    path = Path(config_path)
    if not path.exists():
        return {}

    with open(path, "r") as f:
        content = yaml.safe_load(f)
        return content if content else {}


def validate_config(config: dict) -> ValidationResult:
    """
    Validate configuration against schema.

    Args:
        config: Configuration dictionary to validate

    Returns:
        ValidationResult with validation status and errors
    """
    errors = []

    for section in CONFIG_SCHEMA:
        section_data = config.get(section.name, {})

        for field in section.fields:
            value = section_data.get(field.name)

            # Check required fields
            if field.required and value is None:
                errors.append(ValidationError(
                    section=section.name,
                    field=field.name,
                    message=f"{field.name} is required",
                ))
                continue

            # Skip validation if value is None and not required
            if value is None:
                continue

            # Type validation
            if field.field_type in ("string", "password"):
                if not isinstance(value, str):
                    errors.append(ValidationError(
                        section=section.name,
                        field=field.name,
                        message=f"{field.name} must be a string",
                    ))

            elif field.field_type == "integer":
                if not isinstance(value, int) or isinstance(value, bool):
                    errors.append(ValidationError(
                        section=section.name,
                        field=field.name,
                        message=f"{field.name} must be an integer",
                    ))
                else:
                    # Range validation
                    if field.min_value is not None and value < field.min_value:
                        errors.append(ValidationError(
                            section=section.name,
                            field=field.name,
                            message=f"{field.name} must be at least {field.min_value}",
                        ))
                    if field.max_value is not None and value > field.max_value:
                        errors.append(ValidationError(
                            section=section.name,
                            field=field.name,
                            message=f"{field.name} must be at most {field.max_value}",
                        ))

            elif field.field_type == "float":
                if not isinstance(value, (int, float)) or isinstance(value, bool):
                    errors.append(ValidationError(
                        section=section.name,
                        field=field.name,
                        message=f"{field.name} must be a number",
                    ))
                else:
                    # Range validation
                    if field.min_value is not None and value < field.min_value:
                        errors.append(ValidationError(
                            section=section.name,
                            field=field.name,
                            message=f"{field.name} must be at least {field.min_value}",
                        ))
                    if field.max_value is not None and value > field.max_value:
                        errors.append(ValidationError(
                            section=section.name,
                            field=field.name,
                            message=f"{field.name} must be at most {field.max_value}",
                        ))

            elif field.field_type == "boolean":
                if not isinstance(value, bool):
                    errors.append(ValidationError(
                        section=section.name,
                        field=field.name,
                        message=f"{field.name} must be a boolean",
                    ))

    return ValidationResult(
        valid=len(errors) == 0,
        errors=errors,
    )


def save_config_file(
    config: dict,
    config_path: str | Path = "config.yaml",
) -> tuple[bool, str | None]:
    """
    Save configuration to YAML file atomically.

    Writes to a temp file first, then renames to prevent corruption.
    Password values are never logged in error messages.

    Args:
        config: Configuration dictionary to save
        config_path: Path to config file

    Returns:
        Tuple of (success, error_message)
    """
    path = Path(config_path)

    try:
        # Write to temporary file first
        fd, temp_path = tempfile.mkstemp(
            suffix=".yaml",
            prefix="config_",
            dir=path.parent,
        )

        try:
            with os.fdopen(fd, "w") as f:
                yaml.safe_dump(config, f, default_flow_style=False, sort_keys=False)

            # Atomic rename
            os.replace(temp_path, path)

            # Restrict file permissions (config may contain passwords)
            os.chmod(path, 0o600)

            # Log success without sensitive data
            logger.info(f"Configuration saved to {path}")
            return True, None

        except Exception as e:
            # Clean up temp file on error
            if os.path.exists(temp_path):
                os.unlink(temp_path)
            raise

    except PermissionError:
        error_msg = f"Permission denied writing to {path}"
        logger.error(error_msg)
        return False, error_msg

    except Exception as e:
        # Never log config values (may contain password)
        error_msg = f"Failed to save configuration: {type(e).__name__}"
        logger.error(error_msg)
        return False, error_msg


def _flatten_section(config: dict, section_name: str) -> None:
    """Flatten nested keys in a config section into dot-notation (in-place)."""
    section = config.get(section_name)
    if not isinstance(section, dict):
        return

    flat = {}
    for key, value in list(section.items()):
        if isinstance(value, dict):
            for subkey, subvalue in value.items():
                flat[f"{key}.{subkey}"] = subvalue
        else:
            flat[key] = value

    config[section_name] = flat


def _unflatten_section(config: dict, section_name: str) -> None:
    """Unflatten dot-notation keys in a config section back to nested dicts (in-place)."""
    section = config.get(section_name)
    if not isinstance(section, dict):
        return

    nested = {}
    for key, value in section.items():
        if "." in key:
            parent, child = key.split(".", 1)
            if parent not in nested:
                nested[parent] = {}
            nested[parent][child] = value
        else:
            nested[key] = value

    config[section_name] = nested


NESTED_SECTIONS = ["openrouter", "headspace", "archive", "voice_bridge"]


def flatten_nested_sections(config: dict) -> dict:
    """Flatten nested config keys into dot-notation for all NESTED_SECTIONS.

    Converts e.g. config['openrouter']['models']['turn'] to
    config['openrouter']['models.turn'] so the flat section[field]
    editor can handle it. Applies to all sections in NESTED_SECTIONS
    (currently openrouter and headspace).

    Args:
        config: Configuration dictionary (modified in-place and returned)

    Returns:
        The config dict with nested sections flattened
    """
    for section_name in NESTED_SECTIONS:
        _flatten_section(config, section_name)
    return config


def unflatten_nested_sections(config: dict) -> dict:
    """Unflatten dot-notation keys back to nested dicts for YAML serialisation.

    Applies to all sections in NESTED_SECTIONS (currently openrouter
    and headspace). Converts e.g. config['openrouter']['models.turn']
    to config['openrouter']['models']['turn'].

    Args:
        config: Configuration dictionary (modified in-place and returned)

    Returns:
        The config dict with nested sections unflattened
    """
    for section_name in NESTED_SECTIONS:
        _unflatten_section(config, section_name)
    return config


def merge_with_defaults(config: dict) -> dict:
    """
    Merge provided config with defaults for any missing values.

    Args:
        config: Partial configuration dictionary

    Returns:
        Configuration with defaults filled in
    """
    result = {}

    for section in CONFIG_SCHEMA:
        section_data = config.get(section.name, {})
        result[section.name] = {}

        for field in section.fields:
            if field.name in section_data:
                result[section.name][field.name] = section_data[field.name]
            elif field.default is not None:
                result[section.name][field.name] = field.default

    return result
