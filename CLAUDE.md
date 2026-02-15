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

## CRITICAL: Server & URL Rules

**These rules are non-negotiable. Violations cause server instability, zombie processes, and socket errors.**

### Server Management

**Do NOT restart the server unless absolutely necessary.** Flask's debug reloader picks up most Python file changes automatically. The server should be left running.

When a restart IS required:
- Server has crashed or is unresponsive
- `config.yaml` or dependency changes that the reloader cannot pick up
- Expected application behavior is not being exhibited AND a restart is the last resort after investigating the root cause
- User explicitly requests it

In ALL of these cases:
- **The ONLY way is `./restart_server.sh`.** No exceptions.
- **NEVER** run `python run.py` directly — it does not handle TLS certs, process cleanup, or startup verification
- **NEVER** kill the server with `kill`, `kill -9`, `lsof | xargs kill`, or any ad-hoc process termination
- **NEVER** spawn `run.py` in background with `&` or `nohup`

**Why:** Ad-hoc kills leave zombie werkzeug workers. Direct `run.py` starts inherit stale file descriptors and crash with `OSError: Socket operation on non-socket`. The restart script handles all of this correctly.

### Application URL

**The application URL is `https://smac.griffin-blenny.ts.net:5055` (configured in `config.yaml` as `server.application_url`).**

- **NEVER** use `localhost`, `127.0.0.1`, or `http://` to access the dashboard, check health, take screenshots, or open in a browser
- **ALWAYS** use `https://smac.griffin-blenny.ts.net:5055` for: health checks (`curl -sk https://smac.griffin-blenny.ts.net:5055/health`), browser/agent-browser connections, screenshot verification, any HTTP request to the dashboard
- The ONLY exception is Claude Code hook endpoints (`/hook/*`) which fire from the local machine via `hooks.endpoint_url` in config.yaml — that is a separate config and does not affect dashboard access

**Why:** The server uses TLS via Tailscale certificates. `localhost` bypasses TLS, fails certificate validation, and breaks agent-browser connections.

## Architecture

Flask application factory (`app.py`) with:

- **Event-driven hooks:** Claude Code fires lifecycle hooks (8 event types) -> Flask receives and processes state transitions
- **Persistence:** PostgreSQL via Flask-SQLAlchemy with Alembic migrations
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
claude-headspace start              # Start monitored session (bridge enabled by default)
claude-headspace start --no-bridge  # Start without tmux bridge
./restart_server.sh                  # Start or restart the server (ONLY way — see Critical Rules above)
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
+-- config.yaml                      # All configuration (server, DB, OpenRouter, headspace, etc.)
+-- pyproject.toml                   # Build config & dependencies
+-- restart_server.sh                # Server restart script
+-- tailwind.config.js               # Tailwind CSS configuration
+-- src/claude_headspace/
|   +-- app.py                       # Flask app factory
|   +-- config.py                    # Config loading (YAML + env overrides)
|   +-- database.py                  # SQLAlchemy init
|   +-- models/                      # 10 domain models (project, agent, task, turn, event, etc.)
|   +-- routes/                      # 22 Flask blueprints (dashboard, hooks, sse, projects, etc.)
|   +-- services/                    # 40 service modules (see Key Services below)
+-- tests/
|   +-- conftest.py                  # Root fixtures (app, client, _force_test_database)
|   +-- services/                    # Service unit tests (~40 files)
|   +-- routes/                      # Route tests (~25 files)
|   +-- integration/                 # Real PostgreSQL tests (~7 files, factory-boy)
|   +-- e2e/                         # Playwright browser tests
+-- migrations/versions/             # Alembic migration scripts
+-- templates/                       # Jinja2 templates (base.html, dashboard.html, partials/)
+-- static/
|   +-- css/src/input.css            # Tailwind source (-> compiled to css/main.css)
|   +-- js/                          # Vanilla JS modules (SSE, dashboard, etc.)
+-- bin/                             # Scripts (hooks installer, launcher, watcher)
+-- docs/                            # Architecture docs, PRDs, help topics, roadmaps
+-- openspec/                        # OpenSpec change management (specs + changes)
+-- orch/                            # PRD orchestration (Ruby)
+-- .claude/                         # Claude Code settings, rules, skills
```

## Configuration

All configuration is in `config.yaml`. Sections: `server`, `logging`, `database`, `claude`, `file_watcher`, `event_system`, `sse`, `hooks`, `tmux_bridge`, `notifications`, `activity`, `openrouter` (models, rate_limits, cache, retry, priority_scoring, pricing), `dashboard`, `reaper`, `headspace` (thresholds, flow_detection), `commander`, `archive`.

Key things to know:

- Server runs on port 5055
- Requires `OPENROUTER_API_KEY` in `.env` for LLM features
- Database settings construct the PostgreSQL connection URL
- `notifications.enabled` controls macOS notifications (requires `terminal-notifier` via Homebrew)

## Claude Code Hooks

8 lifecycle hooks fire from Claude Code to Flask endpoints (via `hooks.endpoint_url` in config.yaml):

`session-start`, `session-end`, `stop`, `notification`, `user-prompt-submit`, `pre-tool-use`, `post-tool-use`, `permission-request`

Setup: Run `bin/install-hooks.sh`. Hook commands must use absolute paths.

See `docs/architecture/claude-code-hooks.md` for details.

## Key Services

Services are registered in `app.extensions` and accessed via `app.extensions["service_name"]`.

### Hook & State Management

- **HookReceiver** (`hook_receiver.py`) -- processes 8 Claude Code lifecycle hooks, manages state transitions via TaskLifecycleManager, broadcasts SSE events, triggers notifications and summarisation post-commit
- **TaskLifecycleManager** (`task_lifecycle.py`) -- manages task creation, 5-state transitions, turn processing with intent detection, queues pending summarisation requests for async execution
- **StateMachine** (`state_machine.py`) -- pure stateless validation of `(from_state, actor, intent) -> to_state` transitions
- **IntentDetector** (`intent_detector.py`) -- multi-stage pipeline: regex pattern matching (70+ question patterns, completion patterns, end-of-task patterns) with optional LLM fallback for ambiguous cases
- **SessionCorrelator** (`session_correlator.py`) -- maps Claude Code sessions to Agent records via 5-strategy cascade: memory cache, DB lookup, headspace UUID, working directory, or new agent creation
- **SessionRegistry** (`session_registry.py`) -- in-memory registry of active sessions for fast lookup
- **HookLifecycleBridge** (`hook_lifecycle_bridge.py`) -- translates hook events into task lifecycle actions
- **TranscriptReader** (`transcript_reader.py`) -- reads and parses Claude Code transcript files
- **TranscriptReconciler** (`transcript_reconciler.py`) -- reconciles JSONL transcript entries against database Turn records; corrects Turn timestamps from approximate (server time) to accurate (JSONL conversation time); creates Turns for events missed by hooks; broadcasts SSE corrections
- **PermissionSummarizer** (`permission_summarizer.py`) -- summarises permission request details for display

### Intelligence Layer

- **InferenceService** (`inference_service.py`) -- orchestrates LLM calls via OpenRouter with content-based caching (5-min TTL), rate limiting (30 calls/min, 10k tokens/min), cost tracking, and model selection by level (turn/task/project/objective)
- **InferenceCache** (`inference_cache.py`) -- content-based caching for inference results with configurable TTL
- **InferenceRateLimiter** (`inference_rate_limiter.py`) -- sliding window rate limiter for calls/min and tokens/min
- **OpenRouterClient** (`openrouter_client.py`) -- HTTP client for OpenRouter API with retry and error handling
- **SummarisationService** (`summarisation_service.py`) -- generates AI summaries for turns (1-2 sentences) and tasks (2-3 sentences); includes frustration detection for USER turns (0-10 score persisted to turn.frustration_score)
- **PriorityScoringService** (`priority_scoring.py`) -- batch scores all active agents 0-100 based on objective/waypoint alignment, agent state, and recency; debounced (5 seconds)
- **ProgressSummaryService** (`progress_summary.py`) -- generates LLM-powered project-level progress analysis from git commit history via GitAnalyzer; supports scope-based filtering (since_last, last_n, time_based)
- **BrainRebootService** (`brain_reboot.py`) -- orchestrates brain reboot generation: combines waypoint content with progress summary, exports to project filesystem
- **PromptRegistry** (`prompt_registry.py`) -- centralised registry of all LLM prompt templates

### Monitoring & Lifecycle

- **HeadspaceMonitor** (`headspace_monitor.py`) -- tracks rolling frustration averages (10-turn, 30-min, 3-hr windows), detects flow state, raises traffic-light alerts (green/yellow/red), persists HeadspaceSnapshot records
- **AgentReaper** (`agent_reaper.py`) -- background thread that cleans up inactive agents (5-min timeout by default)
- **ActivityAggregator** (`activity_aggregator.py`) -- background thread that computes hourly activity metrics at agent, project, and system-wide scope
- **StalenessService** (`staleness.py`) -- detects stale PROCESSING state (>10 min) for display-only TIMED_OUT indicator
- **CommanderAvailability** (`commander_availability.py`) -- background thread monitoring tmux pane availability for each agent

### Communication

- **Broadcaster** (`broadcaster.py`) -- SSE event distribution with client filters, queue-based delivery, heartbeat, max 100 connections
- **CardState** (`card_state.py`) -- computes dashboard card JSON for agents and broadcasts card_refresh SSE events
- **EventWriter** (`event_writer.py`) -- async audit logging to PostgreSQL with retry, independent SQLAlchemy engine
- **NotificationService** (`notification_service.py`) -- macOS notifications via terminal-notifier with per-agent rate limiting
- **TmuxBridge** (`tmux_bridge.py`) -- sends text responses to Claude Code sessions via tmux send-keys

### Infrastructure

- **FileWatcher** (`file_watcher.py`) -- hybrid watchdog + polling monitor for `.jsonl` transcript files; feeds the TranscriptReconciler with JSONL entries containing actual conversation timestamps for Phase 2 reconciliation
- **ConfigEditor** (`config_editor.py`) -- reads, validates, merges, and saves config.yaml
- **ArchiveService** (`archive_service.py`) -- archives waypoints and other artifacts with timestamped versions
- **WaypointEditor** (`waypoint_editor.py`) -- loads, saves, and archives project waypoint files
- **GitMetadata/GitAnalyzer** -- git repo info extraction and commit history analysis
- **ProjectDecoder** (`project_decoder.py`) -- encodes/decodes project paths to/from Claude Code folder names
- **ITermFocus** (`iterm_focus.py`) -- AppleScript-based iTerm2 window/pane focus
- **EventSchemas** (`event_schemas.py`) -- schema definitions for event payloads
- **JSONLParser** (`jsonl_parser.py`) -- parser for Claude Code `.jsonl` files
- **ProcessMonitor** (`process_monitor.py`) -- monitors Claude Code process status
- **PathConstants** (`path_constants.py`) -- centralised path definitions for Claude Code directories

## Data Models

| Model | Purpose | Key Fields |
|-------|---------|------------|
| **Project** | Monitored codebase | name, slug, path, github_repo, current_branch, description, inference_paused |
| **Agent** | Claude Code session | session_uuid, claude_session_id, priority_score, priority_reason, iterm_pane_id, tmux_pane_id, transcript_path, started_at, last_seen_at, ended_at, priority_updated_at |
| **Task** | Unit of work (5-state) | state, instruction, completion_summary, started_at, completed_at |
| **Turn** | Individual exchange | actor (USER/AGENT), intent, text, summary, frustration_score |
| **Event** | Audit trail | event_type, payload (JSONB), project/agent/task/turn refs |
| **InferenceCall** | LLM call log | model, input/output tokens, cost, latency, level, cached, input_hash, purpose, input_text, error_message, project_id, agent_id, task_id, turn_id |
| **Objective** | Global priority context | current_text, constraints, priority_enabled |
| **ObjectiveHistory** | Objective change log | text, constraints, started_at, ended_at |
| **ActivityMetric** | Hourly activity data | bucket_start, turn_count, avg_turn_time, active_agents, scope (agent/project/overall), avg_frustration, max_frustration |
| **HeadspaceSnapshot** | Monitoring state | frustration_rolling_10/30min/3hr, state (green/yellow/red), is_flow_state, turn_rate_per_hour, flow_duration_minutes, last_alert_at |

**Task States:** `IDLE -> COMMANDED -> PROCESSING -> AWAITING_INPUT -> COMPLETE`

**Turn Actors:** `USER`, `AGENT`

**Turn Intents:** `COMMAND`, `ANSWER`, `QUESTION`, `COMPLETION`, `PROGRESS`, `END_OF_TASK`

**Event Types:** `SESSION_REGISTERED`, `SESSION_ENDED`, `TURN_DETECTED`, `STATE_TRANSITION`, `OBJECTIVE_CHANGED`, `NOTIFICATION_SENT`, `HOOK_RECEIVED` (legacy), `HOOK_SESSION_START`, `HOOK_SESSION_END`, `HOOK_USER_PROMPT`, `HOOK_STOP`, `HOOK_NOTIFICATION`, `HOOK_POST_TOOL_USE`, `QUESTION_DETECTED`

**Inference Levels:** `TURN`, `TASK`, `PROJECT`, `OBJECTIVE`

## API Endpoints

Routes are organised into 22 blueprints in `src/claude_headspace/routes/`. Key groups:

- **Dashboard:** `/`, `/dashboard`, `/api/events/stream` (SSE)
- **Hooks:** `/hook/{session-start,session-end,stop,notification,user-prompt-submit,pre-tool-use,post-tool-use,permission-request,status}`
- **Projects:** `/projects`, `/api/projects/<id>` (CRUD + settings, metadata detection, waypoint, progress-summary, brain-reboot, archives)
- **Intelligence:** `/api/inference/*`, `/api/summarise/*`, `/api/priority/*`
- **Agents:** `/api/sessions/*`, `/api/focus/*`, `/api/agents/*/dismiss`, `/api/respond/*`
- **Headspace:** `/api/headspace/*`, `/api/metrics/*`, `/activity`
- **Other:** `/objective`, `/config`, `/logging`, `/health`, `/help`

Discover specific endpoints by reading the relevant route file in `src/claude_headspace/routes/`.

## Notes for AI Assistants

### Auto-Commit After Plan Execution

After finishing execution of a plan (e.g., implementing tasks from `/opsx:apply`, completing a unit of work from orchestration, or finishing any multi-step implementation), automatically run `/commit-push` to stage, commit, and push all changes to the current branch. Do not ask for confirmation.

This applies when you finish implementing all tasks from a plan/spec or complete a significant unit of work. Does **not** apply for research/exploration, when user says not to commit, or when work isn't complete.

### Development Tips

- **Run targeted tests:** Run only tests relevant to your change. Do NOT run the full suite unless explicitly asked. See `.claude/rules/ai-guardrails.md` for testing rules.
- **Service injection:** Access services via `app.extensions["service_name"]`
- **State transitions:** Use the state machine via `TaskLifecycleManager`
- **Migrations:** Run `flask db upgrade` after model changes
- **LLM features:** Set `OPENROUTER_API_KEY` in `.env`
- **Tailwind CSS:** Source is `static/css/src/input.css`, output is `static/css/main.css`. Use `npx tailwindcss` (v3), NOT `npx @tailwindcss/cli` (v4).
- The frontend uses vanilla JS with Tailwind CSS -- no framework dependencies

### Testing

Test database safety rules and testing policies are in `.claude/rules/ai-guardrails.md`. Key points:

- Tests MUST use `_test` databases only (enforced by `_force_test_database` fixture)
- 4-tier architecture: unit (`tests/services/`), route (`tests/routes/`), integration (`tests/integration/`), E2E (`tests/e2e/`)
- Integration tests use factory-boy (`tests/integration/factories.py`) -- see `docs/testing/integration-testing-guide.md`
- Run targeted tests by default, full suite only when asked

### Git Workflow

- Feature branches are created FROM `development`
- PRs target `development` branch
- `main` is the stable/release branch
- See `.claude/rules/orchestration.md` for PRD orchestration details
