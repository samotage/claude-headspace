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
- LLM-powered turn/command summarisation, frustration detection, and cross-project priority scoring
- Headspace monitoring: frustration tracking, flow state detection, traffic-light alerting
- Brain reboot: generate waypoint + progress summary snapshots for project context resets
- Project management with inference pause controls, metadata detection, and per-project settings
- Activity metrics: hourly aggregation at agent, project, and system-wide scope
- Persona system: named agent identities with roles, skills, experience files, and org hierarchy
- Remote agents API: external applications create/monitor agents via REST with session token auth
- Embed chat widget: iframe-embeddable chat interface for remote agent interaction
- Voice bridge: voice-first API with semantic picker matching and response formatting
- Context monitoring: background polling of agent context window usage

## CRITICAL: PostgreSQL Only — No SQLite

**This is a PostgreSQL project. There is no SQLite anywhere in this codebase.**

- The database is PostgreSQL, configured via `config.yaml` (`database` section) or `DATABASE_URL` env var
- **NEVER** use SQLite connection strings, `sqlite:///` URIs, or in-memory SQLite databases
- **NEVER** create or reference `.db` files — if you see one, it is an accident (Flask-SQLAlchemy unwanted default)
- **NEVER** set `SQLALCHEMY_DATABASE_URI` to anything other than a `postgresql://` URL
- All migrations (`flask db upgrade`) target PostgreSQL. All SQL must be PostgreSQL-compatible
- Tests use `claude_headspace_test` (PostgreSQL) — see the `_force_test_database` fixture in `tests/conftest.py`

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
|  Hook Receiver -> Session Correlator -> Command Lifecycle  |
|       Intent Detector -> State Machine (5-state)           |
|                                                            |
|  Inference Service (OpenRouter)                            |
|    +-- Summarisation (turn/command + frustration scoring)  |
|    +-- Priority Scoring (agent ranking 0-100)           |
|    +-- Progress Summary (project-level analysis)        |
|    +-- Brain Reboot (waypoint + progress export)        |
|                                                         |
|  Headspace Monitor (frustration / flow / alerts)        |
|  Tmux Bridge (respond to agents via tmux send-keys)     |
|  Activity Aggregator (hourly metrics)                   |
|  Agent Reaper (cleanup inactive agents)                 |
|                                                         |
|  Persona System (roles, skills, org hierarchy, handoff) |
|  Remote Agents API (REST + session tokens + CORS)       |
|  Embed Chat Widget (iframe chat for remote agents)      |
|  Voice Bridge (voice-first API + picker matching)       |
|  Context Poller (background context window monitoring)  |
|                                                         |
|  Broadcaster -> SSE -> Dashboard (real-time updates)    |
|  Event Writer -> PostgreSQL (audit trail)               |
+---------------------------------------------------------+
```

## Tech Stack

- **Python:** 3.10+
- **Framework:** Flask 3.0+ with 26 blueprints
- **Database:** PostgreSQL via Flask-SQLAlchemy 3.1+ and Alembic (Flask-Migrate)
- **Build:** Hatchling (pyproject.toml)
- **Config:** PyYAML + python-dotenv
- **CSS:** Tailwind CSS 3.x (via Node.js: postcss, autoprefixer)
- **LLM:** OpenRouter API (Claude Haiku for turns/commands, Sonnet for project/objective)
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
flask persona register --name X --role Y  # Register a persona
flask persona list [--active] [--role Y]  # List personas
npx tailwindcss -i static/css/src/input.css -o static/css/main.css --watch  # Tailwind dev (v3)
pytest tests/services/test_foo.py    # Run targeted tests (preferred)
pytest tests/routes/ tests/services/ # Run relevant directories
pytest                               # Full suite -- only when asked
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
|   +-- models/                      # 15 domain models (see Data Models below)
|   +-- routes/                      # 26 Flask blueprints (see API Endpoints below)
|   +-- services/                    # ~60 service modules (see Key Services below)
|   +-- cli/                         # Flask CLI commands (persona, transcript)
+-- tests/
|   +-- conftest.py                  # Root fixtures (app, client, _force_test_database)
|   +-- services/                    # Service unit tests
|   +-- routes/                      # Route tests
|   +-- integration/                 # Real PostgreSQL tests (factory-boy)
|   +-- cli/                         # CLI command tests
|   +-- e2e/                         # Playwright browser tests
|   +-- agent_driven/                # Real Claude Code + tmux tests (excluded by default)
+-- data/                            # Persona assets (data/personas/{slug}/skill.md, experience.md)
+-- migrations/versions/             # Alembic migration scripts
+-- templates/                       # Jinja2 templates (base.html, dashboard.html, partials/)
|   +-- embed/                       # Embed chat widget template (chat.html)
+-- static/
|   +-- css/src/input.css            # Tailwind source (-> compiled to css/main.css)
|   +-- js/                          # Vanilla JS modules (25+ modules: SSE, dashboard, personas, etc.)
|   +-- embed/                       # Embed chat widget (embed-app.js, embed-sse.js, embed.css)
+-- uploads/                         # File upload storage (voice bridge)
+-- bin/                             # Scripts (hooks installer, launcher, watcher)
+-- docs/                            # Architecture docs, PRDs, help topics, roadmaps
+-- openspec/                        # OpenSpec change management (specs + changes)
+-- orch/                            # PRD orchestration (Ruby)
+-- .claude/                         # Claude Code settings, rules, skills, agents (personas)
```

## Configuration

All configuration is in `config.yaml`. Sections: `server`, `logging`, `database`, `claude`, `file_watcher`, `event_system`, `sse`, `hooks`, `tmux_bridge`, `notifications`, `activity`, `openrouter` (models, rate_limits, cache, retry, priority_scoring, pricing), `dashboard`, `reaper`, `headspace` (thresholds, flow_detection), `commander`, `archive`, `voice_bridge` (auth, rate_limit, verbosity), `remote_agents` (creation_timeout, allowed_origins, embed_defaults, feature_flags), `context_monitor` (poll_interval, warning/high thresholds).

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

- **HookReceiver** (`hook_receiver.py`) -- processes 8 Claude Code lifecycle hooks, manages state transitions via CommandLifecycleManager, broadcasts SSE events, triggers notifications and summarisation post-commit
- **CommandLifecycleManager** (`command_lifecycle.py`) -- manages command creation, 5-state transitions, turn processing with intent detection, queues pending summarisation requests for async execution
- **StateMachine** (`state_machine.py`) -- pure stateless validation of `(from_state, actor, intent) -> to_state` transitions
- **IntentDetector** (`intent_detector.py`) -- multi-stage pipeline: regex pattern matching (70+ question patterns, completion patterns, end-of-command patterns) with optional LLM fallback for ambiguous cases
- **SessionCorrelator** (`session_correlator.py`) -- maps Claude Code sessions to Agent records via 5-strategy cascade: memory cache, DB lookup, headspace UUID, working directory, or new agent creation
- **SessionRegistry** (`session_registry.py`) -- in-memory registry of active sessions for fast lookup
- **HookLifecycleBridge** (`hook_lifecycle_bridge.py`) -- translates hook events into command lifecycle actions
- **HookAgentState** (`hook_agent_state.py`) -- agent state transitions from hook events
- **HookDeferredStop** (`hook_deferred_stop.py`) -- deferred agent shutdown orchestration
- **HookExtractors** (`hook_extractors.py`) -- utility extractors for hook payload fields
- **TranscriptReader** (`transcript_reader.py`) -- reads and parses Claude Code transcript files
- **TranscriptReconciler** (`transcript_reconciler.py`) -- reconciles JSONL transcript entries against database Turn records; corrects Turn timestamps from approximate (server time) to accurate (JSONL conversation time); creates Turns for events missed by hooks; broadcasts SSE corrections
- **PermissionSummarizer** (`permission_summarizer.py`) -- summarises permission request details for display

### Intelligence Layer

- **InferenceService** (`inference_service.py`) -- orchestrates LLM calls via OpenRouter with content-based caching (5-min TTL), rate limiting (30 calls/min, 10k tokens/min), cost tracking, and model selection by level (turn/command/project/objective)
- **InferenceCache** (`inference_cache.py`) -- content-based caching for inference results with configurable TTL
- **InferenceRateLimiter** (`inference_rate_limiter.py`) -- sliding window rate limiter for calls/min and tokens/min
- **OpenRouterClient** (`openrouter_client.py`) -- HTTP client for OpenRouter API with retry and error handling
- **SummarisationService** (`summarisation_service.py`) -- generates AI summaries for turns (1-2 sentences) and commands (2-3 sentences); includes frustration detection for USER turns (0-10 score persisted to turn.frustration_score)
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
- **ContextPoller** (`context_poller.py`) -- background thread polling active agents' tmux statusline for context window usage; persists to Agent.context_* fields
- **ContextParser** (`context_parser.py`) -- parses Claude Code statusline context info (% used, remaining tokens)
- **TmuxWatchdog** (`tmux_watchdog.py`) -- background thread monitoring tmux pane availability
- **RevivalService** (`revival_service.py`) -- agent revival/recovery mechanisms

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

### Persona & Organisation

- **PersonaRegistration** (`persona_registration.py`) -- end-to-end persona creation: validation, role lookup/create, DB insert, filesystem asset setup (skill.md, experience.md)
- **PersonaAssets** (`persona_assets.py`) -- persona directory/file ops: read skills, read experience, check asset completeness
- **SkillInjector** (`skill_injector.py`) -- persona skill/experience priming via tmux; idempotent (enforced by `agent.prompt_injected_at` DB column)
- **HandoffExecutor** (`handoff_executor.py`) -- full handoff orchestration: validate preconditions, create DB record, shutdown agent, create successor
- **TeamContentDetector** (`team_content_detector.py`) -- detects team/org keywords in agent output to trigger persona/handoff features

### Remote Agents & Embed

- **RemoteAgentService** (`remote_agent_service.py`) -- blocking agent creation with readiness polling; wraps agent lifecycle with synchronous semantics for external APIs
- **SessionToken** (`session_token.py`) -- in-memory token store for remote agent auth; generates opaque tokens, validates per-agent scoping, thread-safe

### Voice Bridge

- **VoiceAuth** (`voice_auth.py`) -- token + rate limiting for voice bridge; localhost bypass option; sliding window rate limiter
- **VoiceFormatter** (`voice_formatter.py`) -- voice-friendly response formatting: status_line + results + next_action; 3 verbosity levels (concise/normal/detailed)

### File Upload

- **FileUpload** (`file_upload.py`) -- file upload validation, storage, serving, cleanup; magic byte validation; quota enforcement

## Data Models

| Model | Purpose | Key Fields |
|-------|---------|------------|
| **Project** | Monitored codebase | name, slug, path, github_repo, current_branch, description, inference_paused |
| **Agent** | Claude Code session | session_uuid, claude_session_id, priority_score, priority_reason, iterm_pane_id, tmux_pane_id, transcript_path, started_at, last_seen_at, ended_at, persona_id (FK), position_id (FK), previous_agent_id (self-ref FK), prompt_injected_at |
| **Command** | Unit of work (5-state) | state, instruction, completion_summary, started_at, completed_at |
| **Turn** | Individual exchange | actor (USER/AGENT), intent, text, summary, frustration_score |
| **Event** | Audit trail | event_type, payload (JSONB), project/agent/command/turn refs |
| **InferenceCall** | LLM call log | model, input/output tokens, cost, latency, level, cached, input_hash, purpose, input_text, error_message, project_id, agent_id, command_id, turn_id |
| **Objective** | Global priority context | current_text, constraints, priority_enabled |
| **ObjectiveHistory** | Objective change log | text, constraints, started_at, ended_at |
| **ActivityMetric** | Hourly activity data | bucket_start, turn_count, avg_turn_time, active_agents, scope (agent/project/overall), avg_frustration, max_frustration |
| **HeadspaceSnapshot** | Monitoring state | frustration_rolling_10/30min/3hr, state (green/yellow/red), is_flow_state, turn_rate_per_hour, flow_duration_minutes, last_alert_at |
| **Persona** | Named agent identity | name, slug (auto-generated), description, role_id (FK), active |
| **Role** | Agent specialisation | name (unique, lowercased), description |
| **Organisation** | Org grouping | name, description |
| **Position** | Org seat / hierarchy | title, organisation_id (FK), role_id (FK), level, reports_to_id (self-ref FK), escalates_to_id (self-ref FK) |
| **Handoff** | Agent context handoff | reason, file_path, injection_prompt, predecessor_agent_id (FK), successor_agent_id (FK) |

**Command States:** `IDLE -> COMMANDED -> PROCESSING -> AWAITING_INPUT -> COMPLETE`

**Turn Actors:** `USER`, `AGENT`

**Turn Intents:** `COMMAND`, `ANSWER`, `QUESTION`, `COMPLETION`, `PROGRESS`, `END_OF_COMMAND`

**Event Types:** `SESSION_REGISTERED`, `SESSION_ENDED`, `TURN_DETECTED`, `STATE_TRANSITION`, `OBJECTIVE_CHANGED`, `NOTIFICATION_SENT`, `HOOK_RECEIVED` (legacy), `HOOK_SESSION_START`, `HOOK_SESSION_END`, `HOOK_USER_PROMPT`, `HOOK_STOP`, `HOOK_NOTIFICATION`, `HOOK_POST_TOOL_USE`, `QUESTION_DETECTED`

**Inference Levels:** `TURN`, `COMMAND`, `PROJECT`, `OBJECTIVE`

## API Endpoints

Routes are organised into 26 blueprints in `src/claude_headspace/routes/`. Key groups:

- **Dashboard:** `/`, `/dashboard`, `/api/events/stream` (SSE)
- **Hooks:** `/hook/{session-start,session-end,stop,notification,user-prompt-submit,pre-tool-use,post-tool-use,permission-request,status}`
- **Projects:** `/projects`, `/api/projects/<id>` (CRUD + settings, metadata detection, waypoint, progress-summary, brain-reboot, archives)
- **Intelligence:** `/api/inference/*`, `/api/summarise/*`, `/api/priority/*`
- **Agents:** `/api/sessions/*`, `/api/focus/*`, `/api/agents/*/dismiss`, `/api/respond/*`
- **Headspace:** `/api/headspace/*`, `/api/metrics/*`, `/activity`
- **Personas:** `/personas`, `/personas/<slug>`, `/api/personas/register`, `/api/personas/<slug>/validate`
- **Remote Agents:** `/api/remote_agents/{create,<id>/alive,<id>/shutdown,openapi.yaml}`, `/embed/<agent_id>` (session token auth + CORS)
- **Voice Bridge:** `/api/voice_bridge/*` (Bearer token auth + localhost bypass)
- **Other:** `/objective`, `/config`, `/logging`, `/health`, `/help`

Discover specific endpoints by reading the relevant route file in `src/claude_headspace/routes/`.

## Notes for AI Assistants

### Auto-Commit After Plan Execution

After finishing execution of a plan (e.g., implementing tasks from `/opsx:apply`, completing a unit of work from orchestration, or finishing any multi-step implementation), automatically run `/commit-push` to stage, commit, and push all changes to the current branch. Do not ask for confirmation.

This applies when you finish implementing all tasks from a plan/spec or complete a significant unit of work. Does **not** apply for research/exploration, when user says not to commit, or when work isn't complete.

### Development Tips

- **Run targeted tests:** Run only tests relevant to your change. Do NOT run the full suite unless explicitly asked. See `.claude/rules/ai-guardrails.md` for testing rules.
- **Service injection:** Access services via `app.extensions["service_name"]`
- **State transitions:** Use the state machine via `CommandLifecycleManager`
- **Migrations:** Run `flask db upgrade` after model changes
- **LLM features:** Set `OPENROUTER_API_KEY` in `.env`
- **Tailwind CSS:** Source is `static/css/src/input.css`, output is `static/css/main.css`. Use `npx tailwindcss` (v3), NOT `npx @tailwindcss/cli` (v4).
- The frontend uses vanilla JS with Tailwind CSS -- no framework dependencies

### Testing

Test database safety rules and testing policies are in `.claude/rules/ai-guardrails.md`. Key points:

- Tests MUST use `_test` databases only (enforced by `_force_test_database` fixture)
- 6-tier architecture: unit (`tests/services/`), route (`tests/routes/`), CLI (`tests/cli/`), integration (`tests/integration/`), E2E (`tests/e2e/`, marker `e2e`), agent-driven (`tests/agent_driven/`, marker `agent_driven`)
- E2E and agent-driven tiers are excluded by default (`addopts` in pyproject.toml); run with `pytest -m e2e` or `pytest -m agent_driven`
- Integration tests use factory-boy (`tests/integration/factories.py`) -- see `docs/testing/integration-testing-guide.md`
- Run targeted tests by default, full suite only when asked

### Git Workflow

- Feature branches are created FROM `development`
- PRs target `development` branch
- `main` is the stable/release branch
- See `.claude/rules/orchestration.md` for PRD orchestration details
