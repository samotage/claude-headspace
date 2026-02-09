# Configuration

Claude Headspace is configured via `config.yaml` in the project root.

## Editing Configuration

You can edit configuration in two ways:

1. **Config Page** - Navigate to **config** in the header for a web-based editor
2. **Direct Edit** - Edit `config.yaml` directly with any text editor

Click the **ⓘ** icon next to any field or section header on the config page for a quick description, default value, and valid range.

## Configuration Sections

### Server

Core web server settings. Changes to these require a server restart.

```yaml
server:
  host: "0.0.0.0"
  port: 5055
  debug: true
```

- `host` - The network interface to bind to. Use `0.0.0.0` to accept connections from any interface on your network, or `127.0.0.1` to restrict to localhost only. Change this if you need to access the dashboard from another machine.
- `port` - TCP port for the web server. Change if port 5055 conflicts with another service. Ports below 1024 require root privileges.
- `debug` - Enables Flask debug mode with auto-reload and detailed error pages. Enable during development for live code reloading. **Disable in production** as it exposes stack traces and allows code execution.

### Logging

Controls application logging output and verbosity.

```yaml
logging:
  level: INFO
  file: logs/app.log
```

- `level` - Controls which log messages are recorded. `DEBUG` captures everything including LLM prompt contents, `INFO` records normal operations, `WARNING` shows potential issues, `ERROR` only shows failures. Lower levels produce significantly more output and may impact performance.
- `file` - Path where log files are written. Relative paths resolve from the project root. Ensure the directory exists and is writable.

### Database

PostgreSQL connection settings. Changes require a server restart.

```yaml
database:
  host: localhost
  port: 5432
  name: claude_headspace
  user: samotage
  pool_size: 10
  pool_timeout: 30
```

- `host` - PostgreSQL server hostname or IP. Use `localhost` for a local database.
- `port` - PostgreSQL server port. Default is `5432`. Only change for non-standard setups.
- `name` - Database name. Must already exist. Run `flask db upgrade` after changing to apply migrations.
- `user` - PostgreSQL username. Must have read/write access to the database.
- `password` - PostgreSQL password. Leave empty for local peer authentication. Stored in plaintext in config.yaml.
- `pool_size` - Number of persistent database connections maintained. Too low (< 5) causes connection contention when multiple agents are active. Too high (> 50) wastes database server resources. Default of 10 is suitable for most single-user setups.
- `pool_timeout` - Seconds to wait for a connection from the pool. If you see "pool timeout" errors during high activity, increase this value.

### Claude

Paths used to locate Claude Code session data.

```yaml
claude:
  projects_path: ~/.claude/projects
```

- `projects_path` - Directory where Claude Code stores project-level state files. This is the standard Claude Code path. Only change if you have a custom Claude Code installation or symlinked projects directory.

### File Watcher

Controls how Claude Headspace monitors Claude Code session files. The file watcher is the fallback mechanism when hooks are not sending events.

```yaml
file_watcher:
  polling_interval: 2
  reconciliation_interval: 60
  inactivity_timeout: 5400
  debounce_interval: 0.5
```

- `polling_interval` - Seconds between file change checks. Lower values (0.5-1s) detect changes faster but use more CPU and disk I/O. Higher values (5-10s) save resources but make the dashboard feel sluggish. Default of 2s is a good balance.
- `reconciliation_interval` - Seconds between full reconciliation scans. This safety net catches events missed by the event-driven watcher. Lower values improve reliability but increase CPU.
- `inactivity_timeout` - Stop watching a session after this much inactivity (default: 90 minutes). Prevents stale watchers from accumulating. Increase for long-running sessions that may pause for extended periods.
- `debounce_interval` - Minimum seconds between processing file change events. Claude Code often writes multiple files in quick succession — debouncing prevents redundant processing. Too low causes duplicate work, too high delays detection.

### Event System

Controls the background event writer that persists audit events to PostgreSQL.

```yaml
event_system:
  write_retry_attempts: 3
  write_retry_delay_ms: 100
  max_restarts_per_minute: 5
  shutdown_timeout_seconds: 2
```

- `write_retry_attempts` - Number of retries for writing events to the database. Increase if you experience transient database connection errors.
- `write_retry_delay_ms` - Milliseconds between retry attempts. Gives transient issues time to resolve.
- `max_restarts_per_minute` - Caps how often the event writer thread can restart per minute. Prevents runaway restart loops.
- `shutdown_timeout_seconds` - Seconds to wait for the event writer to flush pending events during shutdown. Increase if events are being lost during restarts.

### SSE

Server-Sent Events configuration for real-time dashboard updates.

```yaml
sse:
  heartbeat_interval_seconds: 30
  max_connections: 100
  connection_timeout_seconds: 60
  retry_after_seconds: 5
```

- `heartbeat_interval_seconds` - Keep-alive heartbeat frequency. Prevents proxies and browsers from closing idle connections. Too low wastes bandwidth, too high (> 60s) risks connection drops behind proxies.
- `max_connections` - Maximum simultaneous SSE connections. Each open browser tab uses one connection. Lower this if running low on file descriptors.
- `connection_timeout_seconds` - Close idle SSE connections after this long. Clients reconnect automatically. Helps clean up abandoned connections.
- `retry_after_seconds` - Browser reconnect delay after a connection drop. Lower values recover faster; higher values reduce reconnect storms during outages.

### Hooks

Claude Code lifecycle hooks provide real-time session events. When hooks are active, the file watcher reduces its polling frequency.

```yaml
hooks:
  enabled: true
  polling_interval_with_hooks: 60
  fallback_timeout: 1200
```

- `enabled` - Enable the HTTP hook receiver. This is the primary mechanism for tracking sessions. Disable only to rely solely on file watching.
- `polling_interval_with_hooks` - When hooks are actively sending events, the file watcher uses this reduced polling rate as a fallback. Higher values save CPU since hooks handle most updates.
- `fallback_timeout` - If no hooks arrive within this time, the system falls back to full-speed file polling. Increase if sessions have long idle periods where no hooks fire.

### Tmux Bridge

Controls the tmux-based text input bridge for sending responses to Claude Code sessions.

```yaml
tmux_bridge:
  health_check_interval: 30
  subprocess_timeout: 5
  text_enter_delay_ms: 100
```

- `health_check_interval` - Seconds between tmux pane availability checks. Lower values detect availability changes faster. Too low wastes CPU on frequent tmux subprocess calls.
- `subprocess_timeout` - Maximum seconds to wait for a tmux command to complete. Increase if you see timeout errors, but high values can block the thread if tmux hangs.
- `text_enter_delay_ms` - Milliseconds between sending text and pressing Enter in tmux. Some terminals need a small delay to process text before the Enter key. Increase if text appears garbled or incomplete.

These settings control the [Input Bridge](input-bridge) feature.

### Dashboard

Controls dashboard display behaviour.

```yaml
dashboard:
  stale_processing_seconds: 600
  active_timeout_minutes: 60
```

- `stale_processing_seconds` - Agents in PROCESSING state for longer than this are shown as TIMED_OUT (default: 10 minutes). This is a display-only indicator — the agent is not stopped. Increase if your agents routinely process for long periods without sending updates.
- `active_timeout_minutes` - Minutes of inactivity before an agent is considered no longer active. Affects which agents appear in the dashboard active count.

### Reaper

The agent reaper automatically removes agents that have gone silent from the dashboard.

```yaml
reaper:
  enabled: true
  interval_seconds: 60
  inactivity_timeout_seconds: 300
  grace_period_seconds: 300
```

- `enabled` - Enable automatic cleanup of inactive agents. Disable if you want agents to remain on the dashboard indefinitely.
- `interval_seconds` - How often the reaper scans for inactive agents. Lower values detect dead agents faster.
- `inactivity_timeout_seconds` - Mark agents as ended after this much inactivity (default: 5 minutes). Too low causes premature reaping of slow agents. Too high leaves stale cards on the dashboard.
- `grace_period_seconds` - Newly created agents are protected for this long (default: 5 minutes). Prevents reaping agents that are still initialising.

### Headspace

Headspace monitoring tracks frustration levels, detects flow state, and raises traffic-light alerts (green/yellow/red).

```yaml
headspace:
  enabled: true
  thresholds:
    yellow: 4
    red: 7
  session_rolling_window_minutes: 180
  alert_cooldown_minutes: 10
  flow_detection:
    min_turn_rate: 6
    max_frustration: 3
    min_duration_minutes: 15
```

- `thresholds.yellow` - Rolling frustration average above this triggers a yellow (caution) alert. Lower values make the system more sensitive. Should be lower than the red threshold.
- `thresholds.red` - Rolling frustration average above this triggers a red (critical) alert. Indicates the developer may need a break or a change in approach.
- `session_rolling_window_minutes` - Duration of the rolling window for session-level frustration (default: 3 hours). Longer windows smooth out spikes, shorter windows respond faster to recent frustration.
- `alert_cooldown_minutes` - Minimum time between alerts for the same agent. Prevents alert fatigue. Increase if alerts feel too frequent.
- `snapshot_retention_days` - How long to keep headspace snapshots for historical analysis.
- `flow_detection.min_turn_rate` - Minimum turns per hour to consider an agent in flow state. Too low detects false flow, too high misses legitimate flow.
- `flow_detection.max_frustration` - Maximum frustration score during flow state. Flow requires low frustration.
- `flow_detection.min_duration_minutes` - Minimum sustained duration before flow is declared. Prevents brief bursts from being flagged.

See [Headspace](headspace) for details on how frustration scoring and flow detection work.

### Archive

Controls archiving and retention of waypoints and project artifacts.

```yaml
archive:
  enabled: true
  retention:
    policy: keep_all
    keep_last_n: 10
    days: 90
```

- `enabled` - Enable automatic archiving of waypoints and artifacts when they are updated.
- `retention.policy` - How archives are retained: `keep_all` keeps everything, `keep_last_n` keeps the N most recent, `days` deletes archives older than the specified days.
- `retention.keep_last_n` - Number of recent archives to keep (when using `keep_last_n` policy).
- `retention.days` - Delete archives older than this many days (when using `days` policy).

### Commander

Controls the commander socket-based input bridge for sending responses to Claude Code sessions via Unix domain sockets.

```yaml
commander:
  health_check_interval: 30
  socket_timeout: 2
  socket_path_prefix: /tmp/claudec-
```

- `health_check_interval` - Seconds between socket availability checks (1-3600, default: 30). Lower values detect changes faster.
- `socket_timeout` - Timeout in seconds for socket operations (default: 2). Increase if operations time out.
- `socket_path_prefix` - Path prefix for commander sockets. Must match the `claudec` binary's convention (default: `/tmp/claudec-`). Only change with a custom `claudec` setup.

These settings control the [Input Bridge](input-bridge) feature.

### Voice Bridge

Controls the voice bridge PWA for hands-free mobile interaction with agents. Disabled by default.

```yaml
voice_bridge:
  enabled: false
  auth:
    token: ""
    localhost_bypass: true
  rate_limit:
    requests_per_minute: 60
  default_verbosity: "concise"
```

- `enabled` - Enable voice bridge services (token auth and voice-friendly response formatting). The `/voice` page loads regardless, but API responses won't include voice formatting when disabled.
- `auth.token` - Bearer token required for API calls from the PWA. Leave empty for open access (only safe on localhost). Set a strong random string when accessing from other devices on your network.
- `auth.localhost_bypass` - Skip token authentication for requests originating from localhost (127.0.0.1). Convenient for development, but disable if you want strict auth everywhere.
- `rate_limit.requests_per_minute` - Maximum API requests per minute per token. Default of 60 is generous for voice interaction. Lower if concerned about abuse.
- `default_verbosity` - Server-side default for response detail: `concise`, `normal`, or `detailed`. The client can override this per-request via its settings screen.

See [Voice Bridge](voice-bridge) for full setup and usage instructions.

### Notifications

macOS desktop notifications via terminal-notifier.

```yaml
notifications:
  enabled: true
  sound: true
  rate_limit_seconds: 5
```

- `enabled` - Enable desktop notifications. Requires `terminal-notifier` installed via Homebrew (`brew install terminal-notifier`).
- `sound` - Play the macOS notification sound. Disable for silent visual-only notifications.
- `rate_limit_seconds` - Minimum seconds between notifications for the same agent. Set to 0 to allow all notifications. Increase if notifications feel spammy.

### Activity

Background aggregation of hourly activity metrics.

```yaml
activity:
  enabled: true
  interval_seconds: 300
  retention_days: 3000
```

- `enabled` - Enable the background aggregation thread. Disable if you don't use the activity dashboard.
- `interval_seconds` - How often metrics are computed (default: 5 minutes). Lower values produce fresher data.
- `retention_days` - How long to keep metric records. Longer retention enables historical analysis but uses more storage.

### OpenRouter (LLM)

LLM inference via the OpenRouter API. Powers summaries, frustration scoring, priority ranking, and progress analysis.

```yaml
openrouter:
  base_url: https://openrouter.ai/api/v1
  timeout: 30
  models:
    turn: "anthropic/claude-haiku-4.5"
    task: "anthropic/claude-haiku-4.5"
    project: "anthropic/claude-3.5-sonnet"
    objective: "anthropic/claude-3.5-sonnet"
  rate_limits:
    calls_per_minute: 30
    tokens_per_minute: 10000
  cache:
    enabled: true
    ttl_seconds: 300
  retry:
    max_attempts: 1
    base_delay_seconds: 1.0
    max_delay_seconds: 30.0
  priority_scoring:
    debounce_seconds: 5.0
```

- `base_url` - OpenRouter API endpoint. Only change if using a proxy or alternative service.
- `timeout` - Maximum seconds for an LLM API response. Increase for complex prompts or high API load.
- `models.turn` - Model for turn summaries and frustration scoring. Use a fast, cheap model (Haiku) for high-frequency calls.
- `models.task` - Model for task-level summaries. Can be the same as turn or slightly more capable.
- `models.project` - Model for project progress analysis. Use a capable model (Sonnet) for deeper reasoning.
- `models.objective` - Model for cross-project priority scoring.
- `rate_limits.calls_per_minute` - API call cap per minute. Prevents runaway costs.
- `rate_limits.tokens_per_minute` - Token cap per minute. Works alongside calls limit.
- `cache.enabled` - Cache responses using content-based hashing. Avoids redundant calls.
- `cache.ttl_seconds` - Cache lifetime (default: 5 minutes). Shorter = fresher but more expensive.
- `retry.max_attempts` - Retries for failed API calls. Handles transient errors.
- `retry.base_delay_seconds` - Initial retry delay. Uses exponential backoff.
- `retry.max_delay_seconds` - Maximum retry delay cap.
- `priority_scoring.debounce_seconds` - Minimum time between priority scoring runs. Prevents redundant scoring.
- Requires `OPENROUTER_API_KEY` environment variable (in `.env` file)

## Config Page Features

The web-based config editor provides:

- Schema-driven form with validation
- Boolean toggles, text inputs, number inputs, password fields
- Section grouping matching config.yaml structure
- Help icons with popover descriptions for every field and section
- "Learn more" links from popovers to this documentation
- Save with validation and optional server restart

## After Changes

Configuration changes take effect:

- **Immediately** - For objective, notifications, and most runtime settings
- **On restart** - For server, database, and SSE settings (use the Restart button on the config page)
