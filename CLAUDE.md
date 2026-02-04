# CLAUDE.md - Claude Headspace Project Guide

## Project Overview

Claude Headspace is a Kanban-style web dashboard for tracking Claude Code sessions across multiple projects. It monitors terminal sessions and displays real-time session status with click-to-focus functionality, native macOS notifications, and an AI-powered "headspace" monitoring layer.

**Purpose:**

- Track active Claude Code agents across projects
- Display agent status with AI-generated summaries and task instructions
- Click-to-focus: bring iTerm2 windows to foreground from the dashboard
- Respond to agents directly from the dashboard via tmux bridge
- Native macOS notifications when input is needed or tasks complete
- Real-time updates via Server-Sent Events (SSE)
- LLM-powered turn/task summarisation, frustration detection, and cross-project priority scoring
- Headspace monitoring: frustration tracking, flow state detection, traffic-light alerting
- Brain reboot: generate waypoint + progress summary snapshots for project context resets
- Project management with inference pause controls, metadata detection, and per-project settings
- Activity metrics: hourly aggregation at agent, project, and system-wide scope

## Architecture

Flask application factory (`app.py`) with:

- **Event-driven hooks:** Claude Code fires lifecycle hooks (8 event types) -> Flask receives and processes state transitions
- **Persistence:** PostgreSQL via Flask-SQLAlchemy with Alembic migrations (21 migration scripts)
- **Real-time broadcasting:** SSE pushes state changes, summaries, scores, and card refreshes to the dashboard
- **Intelligence layer:** OpenRouter inference service powers summarisation, frustration detection, priority scoring, and progress summaries
- **Headspace monitor:** Tracks frustration scores, detects flow state, and raises traffic-light alerts
- **File watcher fallback:** Monitors Claude Code `.jsonl` and transcript files when hooks are silent
- **Background services:** Agent reaper, activity aggregator, tmux availability checker run in separate threads

```
+---------------------------------------------------------+
|           Claude Code (Terminal Sessions)                |
|   Hooks fire on lifecycle events -----------+           |
+---------------------------------------------+-----------+
                                               |
                                               v
+---------------------------------------------------------+
|           Claude Headspace (Flask)                       |
|                                                         |
|  Hook Receiver -> Session Correlator -> Task Lifecycle  |
|       Intent Detector -> State Machine (5-state)        |
|                                                         |
|  Inference Service (OpenRouter)                         |
|    +-- Summarisation (turn/task + frustration scoring)  |
|    +-- Priority Scoring (agent ranking 0-100)           |
|    +-- Progress Summary (project-level analysis)        |
|    +-- Brain Reboot (waypoint + progress export)        |
|                                                         |
|  Headspace Monitor (frustration / flow / alerts)        |
|  Tmux Bridge (respond to agents via tmux send-keys)     |
|  Activity Aggregator (hourly metrics)                   |
|  Agent Reaper (cleanup inactive agents)                 |
|                                                         |
|  Broadcaster -> SSE -> Dashboard (real-time updates)    |
|  Event Writer -> PostgreSQL (audit trail)               |
+---------------------------------------------------------+
```

## Tech Stack

- **Python:** 3.10+
- **Framework:** Flask 3.0+ with 22 blueprints
- **Database:** PostgreSQL via Flask-SQLAlchemy 3.1+ and Alembic (Flask-Migrate)
- **Build:** Hatchling (pyproject.toml)
- **Config:** PyYAML + python-dotenv
- **CSS:** Tailwind CSS 3.x (via Node.js: postcss, autoprefixer)
- **LLM:** OpenRouter API (Claude Haiku for turns/tasks, Sonnet for project/objective)
- **Real-time:** Server-Sent Events (SSE)
- **Terminal:** iTerm2 (AppleScript-based focus) + tmux (send-keys bridge for agent responses)
- **Notifications:** terminal-notifier (macOS)
- **Testing:** pytest + factory-boy + pytest-cov + pytest-playwright (E2E)

## Common Commands

```bash
python run.py                        # Start the server
./restart_server.sh                  # Restart running server
flask db upgrade                     # Run pending migrations
npx tailwindcss -i static/css/src/input.css -o static/css/main.css --watch  # Tailwind dev (v3)
pytest tests/services/test_foo.py    # Run targeted tests (preferred)
pytest tests/routes/ tests/services/ # Run relevant directories
pytest                               # Full suite (~80 test files) -- only when asked
pytest --cov=src                     # Full suite with coverage -- only when asked
pip install -e ".[dev]"              # Install with dev dependencies
npm install                          # Install Tailwind/Node dependencies
```

## Directory Structure

```
claude_headspace/
+-- run.py                           # Entry point
+-- config.yaml                      # Server/DB/OpenRouter/headspace config
+-- pyproject.toml                   # Build config & dependencies
+-- restart_server.sh                # Server restart script
+-- tailwind.config.js               # Tailwind CSS configuration
+-- package.json                     # Node.js dependencies (Tailwind)
+-- src/claude_headspace/
|   +-- app.py                       # Flask app factory
|   +-- config.py                    # Config loading (YAML + env overrides)
|   +-- database.py                  # SQLAlchemy init
|   +-- cli/
|   |   +-- launcher.py              # CLI launcher
|   +-- models/                      # 10 domain models
|   |   +-- project.py               # Project (monitored codebase)
|   |   +-- agent.py                 # Agent (Claude Code session)
|   |   +-- task.py                  # Task (5-state lifecycle)
|   |   +-- turn.py                  # Turn (user/agent exchange)
|   |   +-- event.py                 # Event (audit trail)
|   |   +-- inference_call.py        # InferenceCall (LLM usage log)
|   |   +-- objective.py             # Objective + ObjectiveHistory
|   |   +-- activity_metric.py       # ActivityMetric (hourly aggregation)
|   |   +-- headspace_snapshot.py    # HeadspaceSnapshot (monitoring state)
|   +-- routes/                      # 22 Flask blueprints
|   |   +-- dashboard.py             # Main dashboard view
|   |   +-- hooks.py                 # Claude Code hook endpoints (8 hooks)
|   |   +-- sse.py                   # SSE streaming
|   |   +-- sessions.py              # Session lifecycle
|   |   +-- projects.py              # Project management CRUD
|   |   +-- inference.py             # Inference status/usage
|   |   +-- summarisation.py         # Turn/task summary API
|   |   +-- priority.py              # Priority scoring API
|   |   +-- objective.py             # Global objective CRUD
|   |   +-- waypoint.py              # Waypoint editor
|   |   +-- focus.py                 # iTerm2 focus + agent dismiss
|   |   +-- respond.py               # Respond to agents via commander
|   |   +-- config.py                # Config viewer/editor
|   |   +-- health.py                # Health check
|   |   +-- help.py                  # Help page + topic search
|   |   +-- logging.py               # Event + inference log viewer
|   |   +-- notifications.py         # Notification settings
|   |   +-- activity.py              # Activity metrics display
|   |   +-- headspace.py             # Headspace monitoring API
|   |   +-- brain_reboot.py          # Brain reboot generation/export
|   |   +-- progress_summary.py      # Progress summary generation
|   |   +-- archive.py               # Archive viewer
|   +-- services/                    # 37 service modules
|       +-- hook_receiver.py         # Processes Claude Code hooks
|       +-- task_lifecycle.py        # Task state management
|       +-- state_machine.py         # Transition validation
|       +-- intent_detector.py       # Turn intent classification (regex + LLM)
|       +-- session_correlator.py    # Session -> Agent mapping
|       +-- inference_service.py     # LLM orchestration via OpenRouter
|       +-- openrouter_client.py     # OpenRouter API client
|       +-- inference_cache.py       # Content-based caching
|       +-- inference_rate_limiter.py # Rate limiting
|       +-- summarisation_service.py # Turn/task summaries + frustration
|       +-- priority_scoring.py      # Agent priority scoring (0-100)
|       +-- progress_summary.py      # Project progress analysis
|       +-- brain_reboot.py          # Brain reboot orchestration
|       +-- headspace_monitor.py     # Frustration/flow/alert tracking
|       +-- broadcaster.py           # SSE distribution
|       +-- event_writer.py          # Async audit logging
|       +-- card_state.py            # Dashboard card state + broadcast
|       +-- file_watcher.py          # .jsonl + transcript monitoring
|       +-- notification_service.py  # macOS notifications
|       +-- iterm_focus.py           # AppleScript iTerm2 control
|       +-- tmux_bridge.py          # Respond to agents via tmux send-keys
|       +-- commander_availability.py # Tmux pane availability monitoring
|       +-- activity_aggregator.py   # Hourly activity metrics
|       +-- agent_reaper.py          # Cleanup inactive agents
|       +-- archive_service.py       # Waypoint/artifact archival
|       +-- staleness.py             # Stale processing detection
|       +-- config_editor.py         # Config read/write/validate
|       +-- git_metadata.py          # Git repo URL + branch
|       +-- git_analyzer.py          # Git analysis utilities
|       +-- prompt_registry.py       # Centralised LLM prompt templates
|       +-- session_registry.py      # Thread-safe session tracking
|       +-- jsonl_parser.py          # Incremental .jsonl parsing
|       +-- transcript_reader.py     # Transcript file reading
|       +-- project_decoder.py       # Path <-> folder name encoding
|       +-- waypoint_editor.py       # Waypoint load/save/archive
|       +-- process_monitor.py       # Process monitoring
+-- tests/
|   +-- conftest.py                  # Root fixtures (app, client, _force_test_database)
|   +-- test_app.py                  # App init tests
|   +-- test_database.py             # DB config tests
|   +-- test_models.py               # Model tests
|   +-- services/                    # Service unit tests (~40 files)
|   +-- routes/                      # Route tests (~25 files)
|   +-- integration/                 # Real PostgreSQL tests (~7 files)
|   |   +-- conftest.py              # DB lifecycle fixtures
|   |   +-- factories.py             # Factory Boy factories
|   +-- e2e/                         # End-to-end browser tests (Playwright)
|   |   +-- conftest.py              # Server + browser fixtures
|   |   +-- helpers/                 # Hook simulator, dashboard assertions
|   +-- cli/                         # CLI tests
+-- migrations/versions/             # 15 Alembic migration scripts
+-- templates/                       # Jinja2 templates
|   +-- base.html                    # Base layout
|   +-- dashboard.html               # Main dashboard
|   +-- partials/                    # 14 reusable components
+-- static/
|   +-- css/                         # Tailwind CSS (src/input.css -> main.css)
|   +-- js/                          # 15 vanilla JS modules (SSE, dashboard, etc.)
+-- bin/                             # Scripts (hooks installer, launcher, watcher)
+-- docs/                            # Architecture docs, PRDs, help topics, roadmaps
+-- openspec/                        # OpenSpec change management
|   +-- specs/                       # ~34 current spec files
|   +-- changes/                     # Active + archived changes (24 archived)
+-- orch/                            # PRD orchestration (Ruby)
+-- .claude/                         # Claude Code settings, rules, skills
    +-- rules/ai-guardrails.md       # AI safety guardrails
```

## Configuration

Edit `config.yaml` to configure the application. Key sections:

```yaml
server:
  host: "0.0.0.0"
  port: 5055
  debug: true

logging:
  level: INFO
  file: logs/app.log

database:
  host: localhost
  port: 5432
  name: claude_headspace
  user: samotage
  pool_size: 10
  pool_timeout: 30

openrouter:
  # Requires OPENROUTER_API_KEY env var (in .env)
  models:
    turn: "anthropic/claude-3-5-haiku-20241022"
    task: "anthropic/claude-3-5-haiku-20241022"
    project: "anthropic/claude-3-5-sonnet-20241022"
    objective: "anthropic/claude-3-5-sonnet-20241022"
  rate_limits:
    calls_per_minute: 20
    tokens_per_minute: 8000
  cache:
    enabled: true
    ttl_seconds: 300

file_watcher:
  polling_interval: 2           # Seconds (fallback mode)
  reconciliation_interval: 60   # Seconds (hooks-active mode)
  inactivity_timeout: 5400      # 90 minutes
  debounce_interval: 0.5

hooks:
  enabled: true
  polling_interval_with_hooks: 60
  fallback_timeout: 1200

dashboard:
  stale_processing_seconds: 600   # 10 min -> display TIMED_OUT
  active_timeout_minutes: 60

headspace:
  enabled: true
  yellow_threshold: 4             # Frustration score for yellow
  red_threshold: 7                # Frustration score for red

reaper:
  enabled: true
  interval: 60                    # Seconds between reaper runs
  inactivity_timeout: 300         # 5 min inactive -> reap

commander:
  health_check_interval: 30
  socket_timeout: 2
  socket_path_prefix: /tmp/claudec-

notifications:
  enabled: true
  sound: true
  rate_limit_seconds: 5

sse:
  heartbeat_interval_seconds: 30
  max_connections: 100
  connection_timeout_seconds: 60

event_system:
  write_retry_attempts: 3
  write_retry_delay_ms: 100

archive:
  enabled: true
```

## Claude Code Hooks (Event-Driven)

The monitor receives lifecycle events directly from Claude Code via hooks:

```
+------------------------------------------------------------+
|              Claude Code (Terminal Session)                  |
|                                                             |
|  Hooks fire on lifecycle events -------------------+        |
+----------------------------------------------------+-------+
                                                     |
                                                     v
+------------------------------------------------------------+
|              Claude Headspace (Flask)                        |
|              http://localhost:5055                           |
|                                                             |
|  POST /hook/session-start      -> Agent created, IDLE       |
|  POST /hook/user-prompt-submit -> Transition to COMMANDED   |
|  POST /hook/stop               -> Detect intent, complete   |
|  POST /hook/notification       -> Timestamp update          |
|  POST /hook/session-end        -> Agent marked inactive     |
|  POST /hook/pre-tool-use       -> Tool execution start      |
|  POST /hook/post-tool-use      -> Tool execution complete   |
|  POST /hook/permission-request -> Permission needed         |
|  GET  /hook/status             -> Receiver status           |
+------------------------------------------------------------+
```

**Benefits over polling:**

- Instant state updates (<100ms vs 2-second polling)
- 100% confidence (event-based vs inference)
- Reduced resource usage (no constant terminal scraping)

**Setup:**

Ask Claude Code to install the hooks, or run `bin/install-hooks.sh`.

**Important:** Hook commands must use absolute paths (e.g., `/Users/yourname/.claude/hooks/...`).

See `docs/architecture/claude-code-hooks.md` for detailed documentation.

## Key Services

Services are registered in `app.extensions` and can be accessed via `app.extensions["service_name"]`.

### Hook & State Management

- **HookReceiver** (`hook_receiver.py`) -- processes 8 Claude Code lifecycle hooks, manages state transitions via TaskLifecycleManager, broadcasts SSE events, triggers notifications and summarisation post-commit
- **TaskLifecycleManager** (`task_lifecycle.py`) -- manages task creation, 5-state transitions, turn processing with intent detection, queues pending summarisation requests for async execution
- **StateMachine** (`state_machine.py`) -- pure stateless validation of `(from_state, actor, intent) -> to_state` transitions
- **IntentDetector** (`intent_detector.py`) -- multi-stage pipeline: regex pattern matching (70+ question patterns, completion patterns, end-of-task patterns) with optional LLM fallback for ambiguous cases
- **SessionCorrelator** (`session_correlator.py`) -- maps Claude Code sessions to Agent records via 5-strategy cascade: memory cache, DB lookup, headspace UUID, working directory, or new agent creation

### Intelligence Layer

- **InferenceService** (`inference_service.py`) -- orchestrates LLM calls via OpenRouter with content-based caching (5-min TTL), rate limiting (20 calls/min, 8k tokens/min), cost tracking, and model selection by level (turn/task/project/objective)
- **SummarisationService** (`summarisation_service.py`) -- generates AI summaries for turns (1-2 sentences) and tasks (2-3 sentences); includes frustration detection for USER turns (0-10 score persisted to turn.frustration_score)
- **PriorityScoringService** (`priority_scoring.py`) -- batch scores all active agents 0-100 based on objective/waypoint alignment, agent state, and recency; debounced (5 seconds)
- **ProgressSummaryService** (`progress_summary.py`) -- generates project-level progress analysis from recent task/turn history
- **BrainRebootService** (`brain_reboot.py`) -- orchestrates brain reboot generation: combines waypoint content with progress summary, exports to project filesystem
- **PromptRegistry** (`prompt_registry.py`) -- centralised registry of all LLM prompt templates (turn summarisation, task completion, frustration detection, priority scoring, progress analysis, project description, classification)

### Monitoring & Lifecycle

- **HeadspaceMonitor** (`headspace_monitor.py`) -- tracks rolling frustration averages (10-turn, 30-min windows), detects flow state, raises traffic-light alerts (green/yellow/red), persists HeadspaceSnapshot records
- **AgentReaper** (`agent_reaper.py`) -- background thread that cleans up inactive agents (5-min timeout by default)
- **ActivityAggregator** (`activity_aggregator.py`) -- background thread that computes hourly activity metrics at agent, project, and system-wide scope
- **StalenessService** (`staleness.py`) -- detects stale PROCESSING state (>10 min) for display-only TIMED_OUT indicator
- **CommanderAvailability** (`commander_availability.py`) -- background thread monitoring commander socket availability for each agent

### Communication

- **Broadcaster** (`broadcaster.py`) -- SSE event distribution with client filters (event_type, project_id, agent_id), queue-based delivery, heartbeat, max 100 connections
- **CardState** (`card_state.py`) -- computes dashboard card JSON for agents (state, summaries, priority, timing) and broadcasts card_refresh SSE events
- **EventWriter** (`event_writer.py`) -- async audit logging to PostgreSQL with retry (3 attempts, exponential backoff), independent SQLAlchemy engine for transaction isolation
- **NotificationService** (`notification_service.py`) -- macOS notifications via terminal-notifier with per-agent rate limiting (5s)
- **CommanderService** (`commander_service.py`) -- sends text responses to Claude Code sessions via Unix domain sockets

### Infrastructure

- **FileWatcher** (`file_watcher.py`) -- hybrid watchdog + polling monitor for `.jsonl` and transcript files; content pipeline with regex-based question detection and inference fallback
- **ConfigEditor** (`config_editor.py`) -- reads, validates, merges, and saves config.yaml changes
- **ArchiveService** (`archive_service.py`) -- archives waypoints and other artifacts with timestamped versions
- **WaypointEditor** (`waypoint_editor.py`) -- loads, saves, and archives project waypoint files (docs/brain_reboot/waypoint.md)
- **GitMetadata** (`git_metadata.py`) -- extracts and caches git repo URL and current branch for projects
- **SessionRegistry** (`session_registry.py`) -- thread-safe registry for FileWatcher session tracking
- **JSONLParser** (`jsonl_parser.py`) -- incremental parser for Claude Code .jsonl session files
- **ProjectDecoder** (`project_decoder.py`) -- encodes/decodes project paths to/from Claude Code folder names
- **ITermFocus** (`iterm_focus.py`) -- AppleScript-based iTerm2 window/pane focus with error classification

## Data Models

| Model | Purpose | Key Fields |
|-------|---------|------------|
| **Project** | Monitored codebase | name, path, github_repo, current_branch, description, inference_paused |
| **Agent** | Claude Code session | session_uuid, claude_session_id, priority_score, priority_reason, iterm_pane_id, transcript_path |
| **Task** | Unit of work (5-state) | state, instruction, completion_summary, started_at, completed_at |
| **Turn** | Individual exchange | actor (USER/AGENT), intent, text, summary, frustration_score |
| **Event** | Audit trail | event_type (12 types), payload (JSONB), project/agent/task/turn refs |
| **InferenceCall** | LLM call log | model, input/output tokens, cost, latency, level, cached, input_hash |
| **Objective** | Global priority context | current_text, constraints, priority_enabled |
| **ObjectiveHistory** | Objective change log | text, constraints, started_at, ended_at |
| **ActivityMetric** | Hourly activity data | bucket_start, turn_count, avg_turn_time, active_agents, scope (agent/project/overall) |
| **HeadspaceSnapshot** | Monitoring state | frustration_rolling_10/30min, state (green/yellow/red), is_flow_state, turn_rate_per_hour |

**Task States:** `IDLE -> COMMANDED -> PROCESSING -> AWAITING_INPUT -> COMPLETE`

**Turn Actors:** `USER`, `AGENT`

**Turn Intents:** `COMMAND`, `ANSWER`, `QUESTION`, `COMPLETION`, `PROGRESS`, `END_OF_TASK`

**Event Types:** `SESSION_REGISTERED`, `SESSION_ENDED`, `TURN_DETECTED`, `STATE_TRANSITION`, `OBJECTIVE_CHANGED`, `NOTIFICATION_SENT`, `HOOK_SESSION_START`, `HOOK_SESSION_END`, `HOOK_USER_PROMPT`, `HOOK_STOP`, `HOOK_NOTIFICATION`, `HOOK_POST_TOOL_USE`

**Inference Levels:** `TURN`, `TASK`, `PROJECT`, `OBJECTIVE`

## API Endpoints

### Dashboard & Real-Time

| Route | Method | Description |
|-------|--------|-------------|
| `/` | GET | Main dashboard view |
| `/dashboard` | GET | Dashboard (alias) |
| `/api/events/stream` | GET | SSE stream (filters: `?types=...&project_id=...&agent_id=...`) |

### Claude Code Hooks

| Route | Method | Description |
|-------|--------|-------------|
| `/hook/session-start` | POST | Claude Code session started |
| `/hook/session-end` | POST | Claude Code session ended |
| `/hook/stop` | POST | Claude finished turn (primary completion signal) |
| `/hook/notification` | POST | Claude Code notification |
| `/hook/user-prompt-submit` | POST | User submitted prompt |
| `/hook/pre-tool-use` | POST | Tool execution starting |
| `/hook/post-tool-use` | POST | Tool execution completed |
| `/hook/permission-request` | POST | Permission needed from user |
| `/hook/status` | GET | Hook receiver status and activity |

### Intelligence Layer

| Route | Method | Description |
|-------|--------|-------------|
| `/api/inference/status` | GET | Inference service health and config |
| `/api/inference/usage` | GET | Usage statistics and cost breakdown |
| `/api/summarise/turn/<id>` | POST | Generate or retrieve turn summary |
| `/api/summarise/task/<id>` | POST | Generate or retrieve task summary |
| `/api/priority/score` | POST | Trigger batch priority scoring |
| `/api/priority/rankings` | GET | Get current priority rankings |

### Project Management

| Route | Method | Description |
|-------|--------|-------------|
| `/projects` | GET | Projects management page |
| `/api/projects` | GET/POST | List all or create project |
| `/api/projects/<id>` | GET/PUT/DELETE | Project CRUD |
| `/api/projects/<id>/settings` | GET/PUT | Project inference settings |
| `/api/projects/<id>/detect-metadata` | POST | Auto-detect git info + description |
| `/api/projects/<id>/waypoint` | GET/POST | Waypoint content |
| `/api/projects/<id>/progress-summary` | GET/POST | Progress summary |
| `/api/projects/<id>/brain-reboot` | GET/POST | Brain reboot generation |
| `/api/projects/<id>/brain-reboot/export` | POST | Export brain reboot to filesystem |
| `/api/projects/<id>/archives` | GET | List archived artifacts |
| `/api/projects/<id>/archives/<artifact>/<ts>` | GET | Retrieve specific archive |

### Session & Agent Control

| Route | Method | Description |
|-------|--------|-------------|
| `/api/sessions` | POST | Register new session |
| `/api/sessions/<uuid>` | GET/DELETE | Get or end session |
| `/api/focus/<agent_id>` | POST | iTerm2 focus control |
| `/api/agents/<agent_id>/dismiss` | POST | Dismiss agent (mark ended) |
| `/api/respond/<agent_id>` | POST | Send text response to agent |
| `/api/respond/<agent_id>/availability` | GET | Check commander socket availability |

### Headspace & Activity

| Route | Method | Description |
|-------|--------|-------------|
| `/activity` | GET | Activity monitoring page |
| `/api/metrics/agents/<id>` | GET | Agent activity metrics |
| `/api/metrics/projects/<id>` | GET | Project activity metrics |
| `/api/metrics/overall` | GET | System-wide activity metrics |
| `/api/headspace/current` | GET | Current headspace state |
| `/api/headspace/history` | GET | Headspace snapshot history |
| `/api/headspace/suppress` | POST | Suppress alerts for 1 hour |

### Other Endpoints

| Route | Method | Description |
|-------|--------|-------------|
| `/api/objective` | GET/POST | Global objective CRUD |
| `/api/objective/history` | GET | Objective change history |
| `/api/objective/priority` | GET/POST | Toggle priority scoring |
| `/config` | GET | Configuration editor page |
| `/api/config` | GET/POST | Get or save configuration |
| `/api/notifications/preferences` | GET/PUT | Notification preferences |
| `/api/notifications/test` | POST | Send test notification |
| `/logging` | GET | Event log viewer page |
| `/api/events` | GET/DELETE | Events (paginated, filterable) |
| `/api/inference/calls` | GET/DELETE | Inference calls (paginated) |
| `/health` | GET | Health check |
| `/help` | GET | Help documentation |
| `/api/help/topics` | GET | List help topics |
| `/api/help/search` | GET | Search help content |

## Notes for AI Assistants

### Auto-Commit After Plan Execution

After finishing execution of a plan (e.g., implementing tasks from `/opsx:apply`, completing a unit of work from orchestration, or finishing any multi-step implementation), automatically run `/commit-push` to stage, commit, and push all changes to the current branch. Do not ask for confirmation -- the skill handles everything including meaningful commit messages derived from the actual diff.

This applies when:
- You finish implementing all tasks from a plan or spec
- You complete a significant unit of work (feature, fix, refactor)
- Orchestration phases complete (build, test passing, etc.)

This does **not** apply when:
- You are only doing research, exploration, or answering questions
- The user explicitly says not to commit
- You are in the middle of multi-step work that isn't yet complete

### Notifications

Notifications require `terminal-notifier` installed via Homebrew:

```bash
brew install terminal-notifier
```

Notifications can be enabled/disabled via:

- **Dashboard:** Toggle in settings panel
- **API:** `PUT /api/notifications/preferences`
- **Config:** `notifications.enabled` in config.yaml

### Development Tips

- **Run targeted tests:** Run only the tests relevant to your change (e.g., `pytest tests/services/test_hook_receiver.py tests/routes/test_hooks.py`). Do NOT run the full suite unless explicitly asked by the user or preparing a commit/PR. Use `-k` to narrow further when useful.
- **Use run.py:** Recommended entry point -- `python run.py`
- **Debug mode:** Set `debug: true` in config.yaml for Flask debug mode
- **Service injection:** Access services via `app.extensions["service_name"]`
- **State transitions:** Use the state machine via `TaskLifecycleManager`
- **Migrations:** Run `flask db upgrade` after model changes
- **LLM features:** Set `OPENROUTER_API_KEY` in `.env` for inference/summarisation/priority
- **Tailwind CSS:** Run the Tailwind CLI watcher during frontend development; source is `static/css/src/input.css`, output is `static/css/main.css`
- The frontend uses vanilla JS with Tailwind CSS -- no framework dependencies

### Testing

#### CRITICAL: Test Database Safety

**Tests MUST NEVER connect to production or development databases.** All databases that do not end in `_test` are protected. This rule is enforced at multiple levels:

1. **Fixture enforcement:** `tests/conftest.py` contains a session-scoped autouse fixture `_force_test_database` that sets `DATABASE_URL` to `claude_headspace_test` before any test runs. This fixture must NEVER be removed, bypassed, or weakened.
2. **Config guard:** `config.py` contains `_guard_production_db()` that raises `RuntimeError` if tests attempt to connect to a non-test database.
3. **New test requirement:** All new test files MUST use the existing fixture system (`app`, `client`, `db_session`). No ad-hoc database connections are allowed.
4. **AI guardrail:** See `.claude/rules/ai-guardrails.md` -- Database Protection section.

Testing must not pollute, corrupt, or delete any user data in production or development databases.

#### Commands

```bash
# Targeted testing (default -- run what's relevant to the change)
pytest tests/services/test_hook_receiver.py          # Specific service test
pytest tests/routes/test_hooks.py                    # Specific route test
pytest tests/services/ tests/routes/                 # Relevant directories
pytest -k "test_state_machine"                       # Pattern match
pytest tests/integration/test_persistence_flow.py    # Specific integration test
pytest tests/e2e/ -v                                 # E2E browser tests (requires Playwright)

# Full suite (only when explicitly requested or before commit/PR)
pytest                                    # All tests (always uses _test DB)
pytest --cov=src                          # With coverage report
```

#### Test Architecture (4-Tier)

- **Unit tests** (`tests/services/`, ~39 files) -- mock dependencies, validate pure service logic in isolation
- **Route tests** (`tests/routes/`, ~23 files) -- Flask test client with mocked services, validate HTTP contracts and response codes
- **Integration tests** (`tests/integration/`, ~7 files) -- real PostgreSQL `_test` database, factory-boy data creation, verify actual persistence and constraints
- **E2E tests** (`tests/e2e/`, ~4 files) -- real Flask server + Playwright browser, hook simulation, full lifecycle validation with screenshots

#### Integration Testing Framework

Real PostgreSQL integration tests with automatic database lifecycle management.

**Prerequisites:**

- PostgreSQL running locally
- Database user with `CREATE DATABASE` privilege
- Dev dependencies installed: `pip install -e ".[dev]"`

**Database lifecycle (automatic):**

1. **Session start:** creates `claude_headspace_test` database (drops first if exists)
2. **Schema creation:** `db.metadata.create_all()` initialises all tables
3. **Per-test isolation:** each test wrapped in a transaction, rolled back after
4. **Session end:** drops the test database

**Test database URL** is resolved in order:

1. `TEST_DATABASE_URL` environment variable (if set)
2. Auto-constructed from `config.yaml` database settings with `_test` suffix

**Factory Boy factories** (`tests/integration/factories.py`):

| Factory | Model | Auto-creates Parent |
|---------|-------|---------------------|
| `ProjectFactory` | Project | -- |
| `AgentFactory` | Agent | Project |
| `TaskFactory` | Task | Agent -> Project |
| `TurnFactory` | Turn | Task -> Agent -> Project |
| `EventFactory` | Event | -- (refs optional) |
| `ObjectiveFactory` | Objective | -- |
| `ObjectiveHistoryFactory` | ObjectiveHistory | Objective |

**Key fixtures** (`tests/integration/conftest.py`):

| Fixture | Scope | Description |
|---------|-------|-------------|
| `test_database_url` | session | Test database connection URL |
| `test_db_engine` | session | Engine that manages create/drop of test DB |
| `TestSessionFactory` | session | `sessionmaker` bound to test engine |
| `db_session` | function | Per-test session with automatic rollback |

**Writing new integration tests:**

```python
import pytest
from sqlalchemy import select
from claude_headspace.models import Project, Agent
from .factories import ProjectFactory, AgentFactory

@pytest.fixture(autouse=True)
def _set_factory_session(db_session):
    ProjectFactory._meta.sqlalchemy_session = db_session
    AgentFactory._meta.sqlalchemy_session = db_session

class TestMyFeature:
    def test_something(self, db_session):
        project = ProjectFactory(name="my-project")
        db_session.flush()

        result = db_session.execute(
            select(Project).where(Project.id == project.id)
        ).scalar_one()
        assert result.name == "my-project"
```

See `docs/testing/integration-testing-guide.md` for the full guide.

#### E2E Testing Framework

Browser-based end-to-end tests using Playwright with a real Flask server.

**Prerequisites:**

- Playwright installed: `pip install pytest-playwright && playwright install`
- PostgreSQL running locally

**E2E fixtures** (`tests/e2e/conftest.py`):

| Fixture | Scope | Description |
|---------|-------|-------------|
| `e2e_test_db` | session | Creates/drops E2E test database |
| `e2e_app` | session | Flask app configured for E2E |
| `e2e_server` | session | Flask running in background thread |
| `clean_db` | function | Truncates tables between tests |
| `hook_client` | function | HookSimulator for firing lifecycle events |
| `dashboard` | function | Navigates to dashboard, asserts SSE connected |

**E2E helpers** (`tests/e2e/helpers/`):

- `HookSimulator` -- fires POST requests to hook endpoints simulating Claude Code
- `DashboardAssertions` -- SSE connection checks, DOM assertions, screenshot capture

#### Test Configuration

From `pyproject.toml`:

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
python_functions = ["test_*"]
addopts = "-v"
markers = ["e2e: end-to-end browser tests"]
```

Dev dependencies: `pip install -e ".[dev]"` (pytest, pytest-cov, factory-boy, pytest-playwright)

### AppleScript (Legacy)

Test AppleScript commands manually before modifying:

```bash
osascript -e 'tell application "iTerm" to get name of windows'
```

If permissions errors occur, check System Preferences -> Privacy & Security -> Automation.

### Auto-Restart Server

When making changes that require a server restart, **use the restart script**:

```bash
./restart_server.sh
```

The script handles everything: kills old process, activates venv, starts new one, verifies it's running.

## PRD Orchestration System

This project includes a PRD-driven development orchestration system for managing feature development through a structured pipeline, plus an OpenSpec change management system for tracking individual changes.

### Orchestration Overview

The system uses Ruby scripts (`orch/`) with Claude Code commands (`.claude/commands/otl/`) to automate:

1. **PRD Workshop** - Create and validate PRDs
2. **Queue Management** - Batch processing of multiple PRDs
3. **Proposal Generation** - Create OpenSpec change proposals from PRDs
4. **Build Phase** - Implement changes with AI assistance
5. **Test Phase** - Run pytest with auto-retry (Ralph loop)
6. **Validation** - Verify implementation matches spec
7. **Finalize** - Commit, create PR, and merge

### Git Workflow

```
development (base) -> feature/change-name -> PR -> development
```

- Feature branches are created FROM `development`
- PRs target `development` branch
- `main` is the stable/release branch

### Key Commands

```bash
# PRD Management
/10: prd-workshop      # Create/remediate PRDs
/20: prd-list          # List pending PRDs
/30: prd-validate      # Quality gate validation

# Orchestration (from development branch)
/10: queue-add         # Add PRDs to queue
/20: prd-orchestrate   # Start queue processing

# Ruby CLI (direct access)
ruby orch/orchestrator.rb status      # Show current state
ruby orch/orchestrator.rb queue list  # List queue items
ruby orch/prd_validator.rb list-all   # List PRDs with validation status
```

### Orchestration Directories

```
orch/
+-- orchestrator.rb      # Main orchestration dispatcher
+-- state_manager.rb     # State persistence
+-- queue_manager.rb     # Queue operations
+-- prd_validator.rb     # PRD validation
+-- usage_tracker.rb     # Usage tracking
+-- config.yaml          # Orchestration config
+-- commands/            # Ruby command implementations
+-- working/             # State/queue files (gitignored)
+-- log/                 # Log files (gitignored)

openspec/
+-- config.yaml          # OpenSpec configuration
+-- specs/               # ~34 current specification files
+-- changes/
    +-- archive/         # 24 completed changes
    +-- (active changes)

.claude/commands/otl/
+-- prds/                # PRD management commands
+-- orch/                # Orchestration commands
```

### PRD Location

PRDs are stored in `docs/prds/{subsystem}/`:

```
docs/prds/
+-- core/done/           # Core system PRDs (9)
+-- events/done/         # Event handling PRDs (3)
+-- inference/done/      # Intelligence layer PRDs (6)
+-- ui/done/             # UI layer PRDs (7)
+-- notifications/done/  # Notification PRDs (1)
+-- scripts/done/        # Script PRDs (2)
+-- state/done/          # State management PRDs (1)
+-- testing/done/        # Testing PRDs (1)
+-- bridge/done/         # Bridge PRDs (1)
+-- flask/done/          # Flask setup PRDs
+-- api/done/            # API layer PRDs
```

### Running the Orchestration

1. Create a PRD in `docs/prds/{subsystem}/`
2. Run `/10: prd-workshop` to validate
3. Switch to `development` branch
4. Run `/10: queue-add` to add to queue
5. Run `/20: prd-orchestrate` to start processing

See `.claude/commands/otl/README.md` for detailed documentation.
