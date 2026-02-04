# Configuration

Claude Headspace is configured via `config.yaml` in the project root.

## Editing Configuration

You can edit configuration in two ways:

1. **Config Page** - Navigate to **config** in the header for a web-based editor
2. **Direct Edit** - Edit `config.yaml` directly with any text editor

## Configuration Sections

### Server Settings

```yaml
server:
  host: "0.0.0.0"
  port: 5055
  debug: true
```

- `host` - Interface to bind to (0.0.0.0 for all interfaces)
- `port` - Port number for the web server
- `debug` - Enable Flask debug mode (development only)

### Database Settings

```yaml
database:
  host: localhost
  port: 5432
  name: claude_headspace
  user: samotage
  pool_size: 10
  pool_timeout: 30
```

- `host` / `port` - PostgreSQL server address
- `name` - Database name
- `user` - Database user (password optional for local auth)
- `pool_size` / `pool_timeout` - Connection pool settings

### OpenRouter (LLM)

```yaml
openrouter:
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
```

- `models` - Which LLM to use for each inference level
- `rate_limits` - Rate limiting for API calls
- `cache` - Content-based caching for inference results
- Requires `OPENROUTER_API_KEY` environment variable (in `.env` file)

### Hooks

```yaml
hooks:
  enabled: true
  polling_interval_with_hooks: 60
  fallback_timeout: 1200
```

- `enabled` - Enable Claude Code lifecycle hooks
- `polling_interval_with_hooks` - Reduced polling interval when hooks are active (seconds)
- `fallback_timeout` - Revert to full polling if no hooks received within this time (seconds)

### Tmux Bridge (Input Bridge)

```yaml
tmux_bridge:
  health_check_interval: 30
  subprocess_timeout: 5
  text_enter_delay_ms: 100
```

- `health_check_interval` - Seconds between tmux pane availability checks
- `subprocess_timeout` - Timeout for tmux subprocess calls (seconds)
- `text_enter_delay_ms` - Delay between sending text and pressing Enter (milliseconds)

These settings control the [Input Bridge](input-bridge) feature.

### Headspace Monitoring

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

- `thresholds` - Frustration score thresholds for yellow/red alerts
- `session_rolling_window_minutes` - Window for the session-level rolling average
- `alert_cooldown_minutes` - Minimum time between alerts
- `flow_detection` - Criteria for detecting flow state

See [Headspace](headspace) for details.

### Commander (Input Bridge)

```yaml
commander:
  health_check_interval: 30
  socket_timeout: 2
  socket_path_prefix: /tmp/claudec-
```

- `health_check_interval` - Seconds between commander socket availability checks (1-3600, default: 30)
- `socket_timeout` - Timeout in seconds for socket operations (default: 2)
- `socket_path_prefix` - Path prefix for commander sockets. Must match the `claudec` binary's convention (default: `/tmp/claudec-`)

These settings control the [Input Bridge](input-bridge) feature. You only need to change them if you have a custom `claudec` setup or want to adjust how frequently availability is checked.

### Notifications

```yaml
notifications:
  enabled: true
  sound: true
  rate_limit_seconds: 5
```

- `enabled` - Enable/disable macOS notifications
- `sound` - Play sound with notifications
- `rate_limit_seconds` - Per-agent rate limit to prevent notification spam

### Activity Aggregation

```yaml
activity:
  enabled: true
  interval_seconds: 300
  retention_days: 3000
```

- `interval_seconds` - How often the aggregator computes metrics (default: 5 minutes)
- `retention_days` - How long to keep activity metric records

### Agent Reaper

```yaml
reaper:
  enabled: true
  interval_seconds: 60
  inactivity_timeout_seconds: 300
  grace_period_seconds: 300
```

- `interval_seconds` - How often the reaper runs
- `inactivity_timeout_seconds` - Mark agents as ended after this much inactivity
- `grace_period_seconds` - Grace period before reaping new agents

### Archive

```yaml
archive:
  enabled: true
  retention:
    policy: keep_all
    keep_last_n: 10
    days: 90
```

- `policy` - Retention policy: `keep_all`, `keep_last_n`, or `days`
- `keep_last_n` - Number of archives to keep (if policy is `keep_last_n`)
- `days` - Days to retain archives (if policy is `days`)

### Other Sections

- **`logging`** - Log level and file path
- **`file_watcher`** - Polling intervals and debounce settings for file monitoring
- **`dashboard`** - Stale processing timeout and active timeout
- **`sse`** - SSE heartbeat, max connections, and timeout settings
- **`event_system`** - Event write retry attempts and delay

## Config Page Features

The web-based config editor provides:

- Schema-driven form with validation
- Boolean toggles, text inputs, number inputs, password fields
- Section grouping matching config.yaml structure
- Save with validation and optional server restart

## After Changes

Configuration changes take effect:

- **Immediately** - For objective, notifications, and most runtime settings
- **On restart** - For server, database, and SSE settings (use the Restart button on the config page)
