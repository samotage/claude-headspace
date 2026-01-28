# Epic 1 Detailed Roadmap: Core Foundation + Event-Driven Hooks

**Project:** Claude Headspace v3.1  
**Epic:** Epic 1 — Core Foundation + Event-Driven Hooks  
**Author:** PM Agent (John)  
**Status:** Roadmap — Baseline for PRD Generation  
**Date:** 2026-01-28

---

## Executive Summary

This document serves as the **high-level roadmap and baseline** for Epic 1 implementation. It breaks Epic 1 into 13 logical sprints (1 sprint = 1 PRD = 1 OpenSpec change), identifies subsystems that require OpenSpec PRDs, and provides the foundation for generating detailed Product Requirements Documents for each subsystem.

**Epic 1 Goal:** Establish the foundational event-driven architecture and prove the Task/Turn state machine works with a functional dashboard. Integrate Claude Code hooks for instant, high-confidence state updates.

**The Differentiator:** Claude Headspace's core value proposition is **not** "view Claude Code sessions" (generic) or simple process monitoring. It is:

- **5-state task model** with turn-level granularity (not just idle/busy)
- **Dual event sources:** Claude Code hooks (instant) + terminal polling (fallback)
- **Cross-project objective alignment** (not just per-project tracking)
- **Click-to-focus iTerm integration** (not just links)
- **Event-driven from day one** (not polling-first architecture)

**Success Criteria:**

- Launch 2-3 iTerm2 sessions with Claude Code, issue commands in each
- Dashboard reflects correct Task/Turn states in real-time (<1 second latency)
- Click agent cards → iTerm window focuses correctly
- Hook events update agent state instantly (<100ms from Claude Code)
- Can set objective and view history
- Event log viewable with filtering

**Architectural Foundation:** Event-driven architecture with Postgres event log, 5-state task model, dual event sources (hooks + polling), SSE real-time updates. See detailed decisions in conceptual overview and Claude Code hooks architecture (`docs/architecture/claude-code-hooks.md`).

---

## Epic 1 Story Mapping

| Story ID | Story Name                                  | Subsystem                 | PRD Directory | Sprint | Priority |
| -------- | ------------------------------------------- | ------------------------- | ------------- | ------ | -------- |
| E1-S1    | Flask application factory and configuration | `flask-bootstrap`         | flask/        | 1      | P0       |
| E1-S2    | Database connection and migrations          | `database-setup`          | core/         | 2      | P0       |
| E1-S3    | Domain models track agents, tasks, turns    | `domain-models`           | core/         | 3      | P0       |
| E1-S4    | Watch Claude Code sessions for changes      | `file-watcher`            | events/       | 4      | P0       |
| E1-S5    | Event system writes to Postgres             | `event-system`            | events/       | 5      | P0       |
| E1-S6    | Task state machine transitions correctly    | `state-machine`           | state/        | 6      | P0       |
| E1-S7    | Server-sent events for real-time updates    | `sse-system`              | api/          | 7      | P0       |
| E1-S8    | Dashboard UI with agent cards               | `dashboard-ui`            | ui/           | 8      | P0       |
| E1-S9    | Set and view objectives                     | `objective-tab`           | ui/           | 9      | P0       |
| E1-S10   | View and filter event logs                  | `logging-tab`             | ui/           | 10     | P0       |
| E1-S11   | Launch monitored Claude Code sessions       | `launcher-script`         | scripts/      | 11     | P0       |
| E1-S12   | Click agent card to focus iTerm window      | `applescript-integration` | scripts/      | 12     | P0       |
| E1-S13   | Receive hook events from Claude Code        | `hook-receiver`           | events/       | 13     | P0       |

---

## Sprint Breakdown

### Sprint 1: Flask Bootstrap

**Goal:** Runnable Flask application with configuration and health check.

**Duration:** 1 week  
**Dependencies:** None

**Deliverables:**

- Python project structure (`pyproject.toml`, `src/` layout)
- Flask application factory pattern
- Configuration loading from `config.yaml`
- Environment variable overrides (`.env`)
- Basic health check endpoint (`/health`)
- Error handlers (404, 500)
- Logging configuration
- Development server startup script
- Tailwind CSS build pipeline
- Base HTML template with dark terminal aesthetic

**Subsystem Requiring PRD:**

1. `flask-bootstrap` — Flask app factory, config, health check

**PRD Location:** `docs/prds/flask/e1-s1-flask-bootstrap-prd.md`

**Stories:**

- E1-S1: Flask application factory and configuration

**Technical Decisions Required:**

- Tailwind integration: CDN vs build pipeline — **recommend build pipeline for customization**
- Config format: YAML structure for application settings
- Environment variable overrides (.env support)
- Development vs production modes

**Risks:**

- Tailwind CSS build pipeline adding complexity
- Config.yaml schema changes breaking existing setups (mitigate: versioning)

**Acceptance Criteria:**

- `flask run` starts server successfully
- Health check endpoint returns 200 OK
- Base HTML page renders with dark theme styles
- Config loaded from `config.yaml`
- Environment variables override config
- Errors return proper error pages

---

### Sprint 2: Database Setup

**Goal:** Postgres database connection, SQLAlchemy integration, and Flask-Migrate for migrations.

**Duration:** 1 week  
**Dependencies:** Sprint 1 complete (Flask app exists)

**Deliverables:**

- Postgres connection configuration
- SQLAlchemy setup and integration
- Flask-Migrate integration
- Migration commands (`flask db init`, `flask db migrate`, `flask db upgrade`)
- Database initialization script
- Connection pooling configuration
- Config.yaml schema for database settings

**Subsystem Requiring PRD:**

2. `database-setup` — Postgres connection, migrations, config.yaml schema

**PRD Location:** `docs/prds/core/e1-s2-database-setup-prd.md`

**Stories:**

- E1-S2: Database connection and migrations

**Technical Decisions Required:**

- Migration tool: Alembic vs Flask-Migrate — **recommend Flask-Migrate**
- Config format: YAML fields for database connection (host, port, user, password)
- Connection pooling settings

**Risks:**

- Postgres installation issues on developer machines
- Connection errors not handled gracefully

**Acceptance Criteria:**

- Connect to Postgres successfully
- Run migrations successfully (`flask db upgrade`)
- Query database successfully
- Connection pooling works
- Errors logged and handled

---

### Sprint 3: Domain Models & Database Schema

**Goal:** Database schema for core domain model (Objective, Project, Agent, Task, Turn, Event).

**Duration:** 1-2 weeks  
**Dependencies:** Sprint 2 complete (database connection exists)

**Deliverables:**

- `Objective` model with history tracking
- `Project` model (auto-discovered from filesystem)
- `Agent` model (linked to Claude Code sessions)
- `Task` model with 5-state machine fields
- `Turn` model with actor/intent/text fields
- `Event` log model for audit trail
- Database migrations for all models
- Model validations and relationships (foreign keys, constraints)
- SQLAlchemy ORM configuration
- Basic CRUD operations for each model

**Subsystem Requiring PRD:**

3. `domain-models` — All models, relationships, migrations, validation rules

**PRD Location:** `docs/prds/core/e1-s3-domain-models-prd.md`

**Stories:**

- E1-S3: Domain models track agents, tasks, turns

**Technical Decisions Required:**

- State enum values for Task (idle, commanded, processing, awaiting_input, complete)
- Intent enum values for Turn (command, answer, question, completion, progress)
- Actor enum values for Turn (user, agent)
- Event type taxonomy (session_start, turn_detected, state_transition, etc.)
- Objective history tracking: separate table vs JSONB column — **recommend separate table**
- Session UUID generation strategy

**Risks:**

- Model relationships becoming too complex (circular dependencies)
- Migration conflicts if schema changes during development
- Foreign key cascades causing unintended data loss
- Enum values being too rigid (hard to extend)

**Acceptance Criteria:**

- All models can be created via SQLAlchemy
- Database migrations run cleanly
- Foreign key relationships enforced
- Enum fields validate correctly
- Can create: Objective with history, Project, Agent, Task with Turns, Events
- Query patterns work (e.g., "get current task for agent")

---

### Sprint 4: File Watcher

**Goal:** Watch Claude Code jsonl files for session and turn detection.

**Duration:** 1-2 weeks  
**Dependencies:** Sprint 3 complete (Event model exists)

**Deliverables:**

- Watchdog integration for monitoring `~/.claude/projects/`
- Claude Code jsonl parser (understand line-by-line format)
- Session discovery (detect new jsonl files)
- Turn detection (parse new lines in jsonl)
- Project auto-discovery from folder names (decode path from folder name)
- Git metadata extraction (repo URL, branch, recent commits)

**Subsystem Requiring PRD:**

4. `file-watcher` — Watchdog setup, jsonl parsing, session/turn detection

**PRD Location:** `docs/prds/events/e1-s4-file-watcher-prd.md`

**Stories:**

- E1-S4: Watch Claude Code sessions for changes

**Technical Decisions Required:**

- Watchdog event handling strategy (debouncing, batching)
- jsonl parsing: line-by-line vs full-file read — **recommend line-by-line**
- Project path decoding from folder name (handle special chars)
- Git metadata caching strategy (avoid git calls on every event)
- Session inactivity timeout (how long before marking session inactive)

**Risks:**

- Watchdog missing events on high-frequency changes
- jsonl parsing failures on malformed files
- Git metadata extraction being slow (blocking event processing)
- Path decoding failing on edge cases (spaces, unicode)

**Acceptance Criteria:**

- Start watcher, start Claude Code session → session discovered
- Issue command in Claude Code → turn detected
- Multiple sessions tracked concurrently
- Project metadata extracted from git
- Parsing errors logged, not crashing

---

### Sprint 5: Event System

**Goal:** Write events to Postgres with background process.

**Duration:** 1 week  
**Dependencies:** Sprint 4 complete (file watcher detecting events)

**Deliverables:**

- Event writer service (write to Postgres)
- Background watcher process
- Event types taxonomy
- Event payload schema
- Process supervision (auto-restart)

**Subsystem Requiring PRD:**

5. `event-system` — Event writer, background process, event types

**PRD Location:** `docs/prds/events/e1-s5-event-system-prd.md`

**Stories:**

- E1-S5: Event system writes to Postgres

**Technical Decisions Required:**

- Background process: separate script vs Flask background thread — **recommend separate process**
- Event types taxonomy (session_discovered, turn_detected, etc.)
- Event payload schema (JSON structure)
- Process supervision strategy

**Risks:**

- Background process crashing without recovery
- Event writes failing silently

**Acceptance Criteria:**

- Events written to Postgres successfully
- Background process runs continuously
- Process restarts on crash
- Event types consistent
- Payloads well-formed

---

### Sprint 6: Task/Turn State Machine

**Goal:** Events correctly update Task and Turn state based on 5-state model.

**Duration:** 1 week  
**Dependencies:** Sprint 5 complete (events flowing)

**Deliverables:**

- Task state transition logic (idle → commanded → processing → awaiting_input/complete)
- Turn intent detection (parse turn content to determine intent)
- State transition validator (enforce valid transitions)
- Task lifecycle management (start on command, end on completion)
- Agent state derivation (agent.state = current_task.state)
- Unit tests for state machine (all valid/invalid transitions)
- State transition event logging

**Subsystem Requiring PRD:**

6. `state-machine` — Task state logic, turn intent mapping, validators, lifecycle

**PRD Location:** `docs/prds/state/e1-s6-state-machine-prd.md`

**Stories:**

- E1-S6: Task state machine transitions correctly

**Technical Decisions Required:**

- Turn intent detection: regex-based vs LLM-based — **recommend regex for Epic 1, LLM in Epic 3**
- Intent detection patterns (what patterns indicate "question" vs "completion"?)
- State transition rules (which transitions are valid)
- Edge case handling: agent crashes mid-task → what state?
- Task completion detection: explicit marker vs timeout

**Risks:**

- Intent detection being unreliable (misclassifying turns)
- State machine becoming stuck due to invalid transitions
- Edge cases not covered (e.g., user force-quits Claude Code)
- Regex patterns being too brittle

**Acceptance Criteria:**

- User issues command → Task created in `commanded` state
- Agent starts responding → Task transitions to `processing`
- Agent asks question → Task transitions to `awaiting_input`
- User answers → Task transitions back to `processing`
- Agent completes → Task transitions to `complete`, then `idle`
- Invalid transitions rejected with error log
- Unit tests cover all state transitions (happy path + edge cases)

---

### Sprint 7: SSE & Real-time Updates

**Goal:** Push updates to browser in real-time via Server-Sent Events.

**Duration:** 1 week  
**Dependencies:** Sprint 6 complete (state machine working)

**Deliverables:**

- SSE endpoint in Flask (`/api/events`)
- Event broadcaster service (broadcast events to all connected clients)
- HTMX SSE integration in frontend
- Reconnection handling (automatic reconnect on disconnect)
- Event filtering (clients can subscribe to specific event types)
- Heartbeat/keepalive mechanism

**Subsystem Requiring PRD:**

7. `sse-system` — SSE endpoint, broadcaster, HTMX integration, reconnection

**PRD Location:** `docs/prds/api/e1-s7-sse-system-prd.md`

**Stories:**

- E1-S7: Server-sent events for real-time updates

**Technical Decisions Required:**

- SSE implementation: Flask-SSE vs custom — **recommend custom for control**
- Event broadcasting: in-memory queue vs Redis pub/sub — **recommend in-memory for Epic 1**
- Reconnection strategy: exponential backoff vs fixed interval
- Event filtering: client-side vs server-side
- Heartbeat interval (30s recommended)

**Risks:**

- SSE connections timing out on some proxies/firewalls
- Memory leaks from stale connections
- Broadcasting to many clients causing performance issues
- Reconnection storms (all clients reconnect simultaneously)

**Acceptance Criteria:**

- SSE endpoint streams events to connected clients
- Browser receives events in real-time (<1 second latency)
- Disconnected clients reconnect automatically
- Multiple clients receive same events (broadcast works)
- No memory leaks from long-running connections
- Heartbeat keeps connection alive

---

### Sprint 8: Dashboard UI

**Goal:** Functional dashboard matching v2 design with Kanban layout.

**Duration:** 2 weeks  
**Dependencies:** Sprint 7 complete (SSE working)

**Deliverables:**

- Dashboard HTML template with Tailwind CSS
- Header bar with status counts (INPUT NEEDED, WORKING, IDLE)
- Recommended next panel (highlights top priority agent)
- Sort controls (by project, by priority)
- Project groups with traffic light indicators
- Agent cards with full detail (state, task, priority, uptime)
- Colour-coded state bars (idle/commanded/processing/awaiting_input/complete)
- HTMX for interactivity (click events, sorting)
- SSE updates triggering UI refreshes
- Collapsible project sections

**Subsystem Requiring PRD:**

8. `dashboard-ui` — Dashboard HTML/CSS/JS, Kanban layout, HTMX interactivity

**PRD Location:** `docs/prds/ui/e1-s8-dashboard-ui-prd.md`

**Stories:**

- E1-S8: Dashboard UI with agent cards

**Technical Decisions Required:**

- Agent card layout: fixed height vs dynamic
- Priority score display: numeric vs visual (progress bar)
- Traffic light logic: based on agent states or tasks
- Sort order: client-side vs server-side — **recommend client-side**
- Mobile responsiveness: full support vs desktop-only — **recommend responsive**

**Risks:**

- UI complexity causing slow initial render
- SSE updates causing UI flicker (too frequent updates)
- Sort/filter performance on large agent lists (20+ agents)
- Tailwind CSS bundle size being too large

**Acceptance Criteria:**

- Dashboard displays all projects, agents, tasks
- Status counts accurate (INPUT NEEDED, WORKING, IDLE)
- Recommended next panel highlights highest priority agent
- Sort by project groups agents correctly
- Sort by priority orders agents by score
- Agent cards show: state, task summary, priority, uptime
- State bars colour-coded correctly
- HTMX click events work (e.g., expand/collapse projects)
- SSE updates refresh dashboard in real-time
- Responsive layout works on desktop and tablet

---

### Sprint 9: Objective Tab

**Goal:** Set and view objective with history.

**Duration:** 1 week  
**Dependencies:** Sprint 3 complete (Objective model exists), Sprint 8 complete (tab navigation exists)

**Deliverables:**

- Objective tab HTML template
- Objective form (text input + constraints textarea)
- Auto-save on change (debounced)
- Objective history display (list of previous objectives)
- Store in Postgres (Objective + ObjectiveHistory tables)
- API endpoints: GET/POST `/api/objective`, GET `/api/objective/history`

**Subsystem Requiring PRD:**

9. `objective-tab` — Objective form, auto-save, history display, API

**PRD Location:** `docs/prds/ui/e1-s9-objective-tab-prd.md`

**Stories:**

- E1-S9: Set and view objectives

**Technical Decisions Required:**

- Auto-save debounce interval (2-3 seconds recommended)
- History limit: show all vs paginate — **recommend show recent 10, paginate rest**
- Objective format: plain text vs structured fields
- Constraints field: optional or required — **recommend optional**

**Risks:**

- Auto-save causing too many database writes
- Objective changes not persisting due to debounce issues
- History becoming too large (storage bloat)

**Acceptance Criteria:**

- Can type objective text, auto-saves after debounce
- Can add optional constraints
- Changes persist across page reloads
- Objective history shows previous objectives with timestamps
- API endpoints return correct data
- Multiple users see same objective (shared state)

---

### Sprint 10: Logging Tab

**Goal:** Viewable event log with filtering.

**Duration:** 1 week  
**Dependencies:** Sprint 5 complete (events logged), Sprint 8 complete (tab navigation)

**Deliverables:**

- Logging tab HTML template
- Event log table (timestamp, project, agent, event type, details)
- Filters: project, agent, event type
- Real-time updates via SSE (new events appear automatically)
- Pagination or virtual scroll for large logs
- API endpoint: GET `/api/events` with query params

**Subsystem Requiring PRD:**

10. `logging-tab` — Event log display, filters, pagination, SSE integration

**PRD Location:** `docs/prds/ui/e1-s10-logging-tab-prd.md`

**Stories:**

- E1-S10: View and filter event logs

**Technical Decisions Required:**

- Display limit: pagination vs virtual scroll vs infinite scroll — **recommend pagination**
- Filter logic: client-side vs server-side — **recommend server-side**
- Event detail display: inline vs modal — **recommend inline expandable**
- Date range filter: optional or required — **recommend optional**

**Risks:**

- Event log becoming too large (performance issues)
- Filters not working correctly (missing events)
- SSE updates causing table to jump (scroll position issues)

**Acceptance Criteria:**

- Event log displays all events with columns: timestamp, project, agent, event type, details
- Can filter by project, agent, event type
- Filters apply correctly (matching events shown)
- New events appear automatically via SSE
- Pagination works (can navigate pages)
- Event details expandable inline
- Performance acceptable with 10,000+ events

---

### Sprint 11: Launcher Script

**Goal:** CLI tool to launch monitored Claude Code sessions.

**Duration:** 1 week  
**Dependencies:** Sprint 3 complete (Agent model), Sprint 4 complete (session discovery)

**Deliverables:**

- `claude-headspace` CLI script (Python or Bash)
- `start` command: launches Claude Code with monitoring
- Session UUID generation
- Project detection from current working directory
- iTerm2 pane ID capture (for later AppleScript focus)
- Register session with application (HTTP POST or file-based)
- Set environment variable for hooks (CLAUDE_HEADSPACE_URL)
- Launch `claude` CLI
- Cleanup on exit (mark session inactive)

**Subsystem Requiring PRD:**

11. `launcher-script` — CLI tool, session registration, iTerm pane capture, cleanup

**PRD Location:** `docs/prds/scripts/e1-s11-launcher-script-prd.md`

**Stories:**

- E1-S11: Launch monitored Claude Code sessions

**Technical Decisions Required:**

- Script language: Python vs Bash — **recommend Python for portability**
- Session registration: HTTP POST vs file write — **recommend HTTP POST**
- iTerm pane ID capture method (AppleScript vs tmux)
- Session UUID format (UUID4 recommended)
- Environment variable naming

**Risks:**

- iTerm pane ID capture failing on edge cases
- Session registration failing (network issues, server down)
- Script not handling errors gracefully (Claude Code crashes)
- Cleanup not running on unexpected exit

**Acceptance Criteria:**

- `claude-headspace start` launches Claude Code successfully
- Session UUID generated and stored
- Project detected from `pwd`
- iTerm pane ID captured
- Session registered with application (visible in dashboard)
- Environment variable set for hooks
- Session marked inactive on exit
- Error handling shows clear messages

---

### Sprint 12: AppleScript Integration

**Goal:** macOS integration for iTerm focus.

**Duration:** 1 week  
**Dependencies:** Sprint 11 complete (pane IDs captured), Sprint 8 complete (agent cards)

**Deliverables:**

- AppleScript to focus iTerm2 pane by ID
- API endpoint: POST `/api/focus/<agent_id>`
- Wire up agent card click → API call → iTerm focus
- Error handling for permission issues
- Fallback: show session path if focus fails
- iTerm2 vs WezTerm support (detect which is installed)

**Subsystem Requiring PRD:**

12. `applescript-integration` — AppleScript focus, API endpoint, permission handling

**PRD Location:** `docs/prds/scripts/e1-s12-applescript-integration-prd.md`

**Stories:**

- E1-S12: Click agent card to focus iTerm window

**Technical Decisions Required:**

- Terminal detection: iTerm2 vs WezTerm vs both — **recommend detect installed terminal**
- Permission error handling: show modal vs inline message
- Fallback behavior: show path vs do nothing
- Multi-terminal support: Epic 1 or future — **recommend iTerm2 only in Epic 1**

**Risks:**

- macOS privacy controls blocking AppleScript automation
- iTerm2 pane IDs changing (breaking focus)
- Permission prompts confusing users
- AppleScript being too slow (>1 second delay)

**Acceptance Criteria:**

- Click agent card → iTerm window focuses
- Correct pane activated (not just iTerm window)
- Permission errors detected, show actionable message
- Fallback shows session path if focus fails
- Works on macOS Monterey, Ventura, Sonoma
- Focus latency <500ms

---

### Sprint 13: Claude Code Hooks Integration

**Goal:** Receive lifecycle events directly from Claude Code via hooks for instant, high-confidence state updates.

**Duration:** 1-2 weeks  
**Dependencies:** Sprint 6 complete (state machine), Sprint 8 complete (dashboard)

**Deliverables:**

- **HookReceiver service** (`src/services/hook_receiver.py`):
  - `process_event()` — Main entry point for hook events
  - `correlate_session()` — Match Claude session ID to agent via working directory
  - `map_event_to_state()` — Map hook events to state transitions
- **Hook API routes** (`src/routes/hooks.py`):
  - POST `/hook/session-start` — Session started → Create agent, set IDLE
  - POST `/hook/session-end` — Session ended → Mark agent inactive
  - POST `/hook/stop` — Agent turn completes → PROCESSING → IDLE
  - POST `/hook/notification` — Various events → Timestamp update only
  - POST `/hook/user-prompt-submit` — User submits prompt → IDLE → PROCESSING
  - GET `/hook/status` — Hook receiver status, last event times
- **Hook configuration** (`src/models/config.py`):
  - `HookConfig` model with enabled, polling fallback, session timeout
  - Hybrid mode: hooks primary, polling fallback (60s when hooks active)
- **Session correlation**:
  - Map Claude `$CLAUDE_SESSION_ID` to agents via working directory
  - Handle mismatches (Claude session ≠ terminal pane ID)
- **Hook notification script** (`bin/notify-headspace.sh`):
  - Bash script that POSTs to hook endpoints
  - Uses `$CLAUDE_SESSION_ID`, `$CLAUDE_WORKING_DIRECTORY` env vars
  - Timeout/retry logic (1s connect timeout, 2s max time)
  - Silent failures (exits 0 even if curl fails)
- **Claude Code settings template** (`docs/claude-code-hooks-settings.json`):
  - JSON for `~/.claude/settings.json` with all hook configurations
  - Absolute paths (not ~ or $HOME)
- **Installation script** (`bin/install-hooks.sh`):
  - Copies `notify-headspace.sh` to `~/.claude/hooks/`
  - Merges settings template into `~/.claude/settings.json`
  - Sets executable permissions
- **Hook status dashboard** (add to main dashboard):
  - Show "Hooks: enabled" vs "Polling only"
  - Last hook event time per agent
  - Fallback indicator (when polling takes over)

**Subsystem Requiring PRD:**

13. `hook-receiver` — Hook receiver service, API routes, session correlation, hybrid mode

**PRD Location:** `docs/prds/events/e1-s13-hook-receiver-prd.md`

**Stories:**

- E1-S13: Receive hook events from Claude Code

**Technical Decisions Required:**

- Hook authentication: none (local only, trust localhost) — **recommend no auth for Epic 1, add in Epic 2**
- Session correlation: working directory matching — **decided in architecture doc**
- Hybrid mode polling interval: 60 seconds when hooks active — **decided**
- Fallback detection: revert to 2-second polling after 300s hook silence — **decided**
- Hook timeout: 1s connect, 2s max time — **decided**
- Error handling: silent failures in hook script — **decided**

**Architecture Details:**

**Event Flow:**

```
Claude Code → Hook Script → HTTP POST → HookReceiver → State Transition
                                                      → SSE Broadcast
                                                      → Event Log
```

**Hook Event to State Mapping:**

| Hook Event       | Current State | New State   | Confidence |
| ---------------- | ------------- | ----------- | ---------- |
| SessionStart     | -             | IDLE        | 1.0        |
| UserPromptSubmit | IDLE          | PROCESSING  | 1.0        |
| Stop             | PROCESSING    | IDLE        | 1.0        |
| Notification     | any           | (no change) | -          |
| SessionEnd       | any           | ENDED       | 1.0        |

**Hybrid Mode:**

1. **Hooks active:** Polling interval = 60 seconds (reconciliation only)
2. **Hooks silent >300s:** Revert to 2-second polling
3. **Hooks resume:** Return to 60-second polling
4. **Polling always runs:** Safety net for missed events

**Session Correlation Logic:**

```python
# Claude session ID ≠ terminal pane ID
# Use working directory to match
def correlate_session(claude_session_id, cwd):
    # 1. Check cache
    if claude_session_id in cache:
        return cache[claude_session_id]

    # 2. Match by working directory
    for agent in agents:
        if agent.cwd == cwd:
            cache[claude_session_id] = agent
            return agent

    # 3. Create new agent
    agent = create_agent(cwd=cwd)
    cache[claude_session_id] = agent
    return agent
```

**Risks:**

- Hooks not installed (degraded to polling-only mode)
- Hook authentication being too complex (users skip setup) — **mitigated: no auth in Epic 1**
- Hook events missing (network issues, server down) — **mitigated: hybrid mode with fallback**
- Hook event order issues (out-of-order delivery) — **mitigated: state machine validates transitions**
- Session correlation failures (multiple agents in same directory) — **mitigated: last-matched wins**
- Installation script errors (path issues, permissions) — **mitigated: clear error messages**

**Acceptance Criteria:**

- HookReceiver service processes all hook events correctly
- Hook endpoints receive events from Claude Code
- Hook events update Agent/Task/Turn state with confidence=1.0
- State updates faster than polling (<100ms vs ~2 seconds)
- Hook status dashboard shows "Hooks: enabled" and last event times
- Graceful degradation: hooks silent >300s → revert to 2s polling
- Session correlation matches Claude sessions to agents via working directory
- Hybrid mode polling adjusts interval based on hook activity
- Installation script works on clean macOS setup:
  - `~/.claude/hooks/notify-headspace.sh` created and executable
  - `~/.claude/settings.json` updated with hook configuration
  - Absolute paths used (not ~ or $HOME)
- Hook script handles timeouts and failures gracefully (silent failures)
- Documentation clear and complete
- End-to-end test: start Claude Code → hooks fire → state transitions → polling adjusts

---

## Subsystems Requiring OpenSpec PRDs

The following 13 subsystems need detailed PRDs created via OpenSpec. Each PRD will be generated as a separate change proposal and validated before implementation.

### PRD Directory Structure

```
docs/prds/
├── api/          # API and transport layer (SSE, endpoints)
├── core/         # Core infrastructure (database, models)
├── events/       # Event system (watchers, hooks, event bus)
├── flask/        # Flask-specific (bootstrap, app factory)
├── scripts/      # CLI tools and integrations
├── state/        # State management (state machine, transitions)
└── ui/           # User interface components
```

### 1. Flask Bootstrap

**Subsystem ID:** `flask-bootstrap`  
**Sprint:** Sprint 1  
**Priority:** P0  
**PRD Location:** `docs/prds/flask/e1-s1-flask-bootstrap-prd.md`

**Scope:**

- Flask application factory pattern
- Configuration loading from `config.yaml`
- Environment variable overrides (`.env`)
- Health check endpoint
- Error handlers (404, 500)
- Logging configuration
- Development vs production modes

**Key Requirements:**

- Must use application factory pattern (testable)
- Must load config from `config.yaml` with env overrides
- Must provide health check endpoint for monitoring
- Must configure logging (console + file)
- Must handle errors gracefully

**OpenSpec Spec:** `openspec/specs/e1-s1-flask-bootstrap/spec.md`

**Related Files:**

- `src/__init__.py`
- `src/app.py` (application factory)
- `src/config.py` (config loader)
- `config.yaml` (template)
- `.env.example`

**Data Model Changes:** None

**Dependencies:** None

**Acceptance Tests:**

- `flask run` starts server successfully
- Health check returns 200 OK
- Config loaded from `config.yaml`
- Environment variables override config
- Errors return proper error pages

---

### 2. Database Setup

**Subsystem ID:** `database-setup`  
**Sprint:** Sprint 2  
**Priority:** P0  
**PRD Location:** `docs/prds/core/e1-s2-database-setup-prd.md`

**Scope:**

- Postgres connection configuration
- SQLAlchemy setup
- Flask-Migrate integration
- Migration commands
- Database initialization script
- Connection pooling

**Key Requirements:**

- Must connect to Postgres using config.yaml settings
- Must use SQLAlchemy ORM
- Must use Flask-Migrate for migrations
- Must provide migration commands (init, migrate, upgrade)
- Must handle connection errors gracefully

**OpenSpec Spec:** `openspec/specs/e1-s2-database-setup/spec.md`

**Related Files:**

- `src/database.py` (SQLAlchemy setup)
- `migrations/` (Flask-Migrate directory)
- `config.yaml` (database section)

**Data Model Changes:**

```yaml
database:
  host: localhost
  port: 5432
  name: claude_headspace
  user: postgres
  password: ""
  pool_size: 10
```

**Dependencies:** Postgres installed

**Acceptance Tests:**

- Connect to Postgres successfully
- Run migrations successfully
- Query database successfully
- Connection pooling works
- Errors logged and handled

---

### 3. Domain Models

**Subsystem ID:** `domain-models`  
**Sprint:** Sprint 3  
**Priority:** P0  
**PRD Location:** `docs/prds/core/e1-s3-domain-models-prd.md`

**Scope:**

- `Objective` model with history
- `ObjectiveHistory` model
- `Project` model
- `Agent` model
- `Task` model with state enum
- `Turn` model with actor/intent enums
- `Event` log model
- Database migrations for all models
- Model relationships (foreign keys)
- Validation rules

**Key Requirements:**

- Must define all core domain models
- Must use enums for state, intent, actor
- Must enforce foreign key relationships
- Must validate required fields
- Must support querying current state (e.g., agent's current task)

**OpenSpec Spec:** `openspec/specs/e1-s3-domain-models/spec.md`

**Related Files:**

- `src/models/__init__.py`
- `src/models/objective.py`
- `src/models/project.py`
- `src/models/agent.py`
- `src/models/task.py`
- `src/models/turn.py`
- `src/models/event.py`
- `migrations/versions/*.py`

**Data Model Changes:**

```python
# Objective
objectives
  id, current_text, constraints, set_at

objective_history
  id, objective_id, text, constraints, started_at, ended_at

# Projects
projects
  id, name, path, github_repo, current_branch, created_at

# Agents
agents
  id, session_uuid, project_id, iterm_pane_id, started_at, last_seen_at, is_active

# Tasks
tasks
  id, agent_id, state (enum), started_at, completed_at

# Turns
turns
  id, task_id, actor (enum), text, intent (enum), timestamp

# Events
events
  id, timestamp, project_id, agent_id, task_id, turn_id, event_type, payload (JSON)
```

**Dependencies:** Sprint 2 complete (database setup)

**Acceptance Tests:**

- Create all models successfully
- Foreign keys enforced
- Enums validate correctly
- Query patterns work (current task, recent turns)

---

### 4. File Watcher

**Subsystem ID:** `file-watcher`  
**Sprint:** Sprint 4  
**Priority:** P0  
**PRD Location:** `docs/prds/events/e1-s4-file-watcher-prd.md`

**Scope:**

- Watchdog integration for `~/.claude/projects/`
- Claude Code jsonl parser
- Session discovery (detect new files)
- Turn detection (parse new lines)
- Project path decoding from folder names
- Git metadata extraction

**Key Requirements:**

- Must watch `~/.claude/projects/` recursively
- Must detect new jsonl files (new sessions)
- Must detect new lines in jsonl files (new turns)
- Must decode project path from folder name
- Must extract git metadata (repo, branch)
- Must handle parsing errors gracefully

**OpenSpec Spec:** `openspec/specs/e1-s4-file-watcher/spec.md`

**Related Files:**

- `src/services/file_watcher.py`
- `src/services/jsonl_parser.py`
- `src/services/git_metadata.py`
- `src/services/project_discovery.py`

**Data Model Changes:** None (uses existing models)

**Dependencies:** Sprint 3 complete (models exist)

**Acceptance Tests:**

- Start watcher, create jsonl file → session discovered
- Append line to jsonl → turn detected
- Project path decoded correctly from folder name
- Git metadata extracted correctly
- Parsing errors logged, not crashing

---

### 5. Event System

**Subsystem ID:** `event-system`  
**Sprint:** Sprint 5  
**Priority:** P0  
**PRD Location:** `docs/prds/events/e1-s5-event-system-prd.md`

**Scope:**

- Event writer service (write to Postgres)
- Background watcher process
- Event types taxonomy
- Event payload schema
- Process supervision (auto-restart)

**Key Requirements:**

- Must write events to Postgres atomically
- Must run as background process (separate from Flask)
- Must define event types (session_discovered, turn_detected, etc.)
- Must structure event payloads consistently (JSON)
- Must auto-restart on crash

**OpenSpec Spec:** `openspec/specs/e1-s5-event-system/spec.md`

**Related Files:**

- `src/services/event_writer.py`
- `bin/watcher.py` (background process)
- `supervisord.conf` or `systemd` unit file

**Data Model Changes:** None (uses Event model from Sprint 3)

**Dependencies:** Sprint 4 complete (file watcher detecting events)

**Acceptance Tests:**

- Events written to Postgres successfully
- Background process runs continuously
- Process restarts on crash
- Event types consistent
- Payloads well-formed

---

### 6. State Machine

**Subsystem ID:** `state-machine`  
**Sprint:** Sprint 6  
**Priority:** P0  
**PRD Location:** `docs/prds/state/e1-s6-state-machine-prd.md`

**Scope:**

- Task state transition logic
- Turn intent detection (regex-based)
- State transition validator
- Task lifecycle management
- Agent state derivation
- Unit tests for all transitions

**Key Requirements:**

- Must implement 5-state model (idle → commanded → processing → awaiting_input/complete)
- Must detect turn intent from content (command, answer, question, completion, progress)
- Must validate state transitions (reject invalid)
- Must create tasks on command, complete on completion
- Must derive agent state from current task
- Must have comprehensive unit tests

**OpenSpec Spec:** `openspec/specs/e1-s6-state-machine/spec.md`

**Related Files:**

- `src/services/state_machine.py`
- `src/services/intent_detector.py`
- `tests/test_state_machine.py`

**Data Model Changes:** None (uses Task/Turn models)

**Dependencies:** Sprint 5 complete (events flowing)

**Acceptance Tests:**

- All valid transitions succeed
- Invalid transitions rejected
- Task lifecycle correct (start, transitions, end)
- Agent state derived correctly
- Intent detection accurate (>90% on test cases)
- Unit tests pass

---

### 7. SSE System

**Subsystem ID:** `sse-system`  
**Sprint:** Sprint 7  
**Priority:** P0  
**PRD Location:** `docs/prds/api/e1-s7-sse-system-prd.md`

**Scope:**

- SSE endpoint in Flask
- Event broadcaster service
- HTMX SSE integration
- Reconnection handling
- Event filtering
- Heartbeat mechanism

**Key Requirements:**

- Must provide SSE endpoint (`/api/events`)
- Must broadcast events to all connected clients
- Must integrate with HTMX for frontend updates
- Must handle reconnections gracefully
- Must support event filtering (client subscribes to types)
- Must send heartbeats to keep connections alive

**OpenSpec Spec:** `openspec/specs/e1-s7-sse-system/spec.md`

**Related Files:**

- `src/routes/sse.py` (SSE endpoint)
- `src/services/broadcaster.py`
- `templates/base.html` (HTMX SSE setup)
- `static/js/sse.js`

**Data Model Changes:** None

**Dependencies:** Sprint 6 complete (state machine)

**Acceptance Tests:**

- SSE endpoint streams events
- Multiple clients receive broadcasts
- Reconnections work automatically
- Event filtering works
- Heartbeats keep connection alive
- No memory leaks

---

### 8. Dashboard UI

**Subsystem ID:** `dashboard-ui`  
**Sprint:** Sprint 8  
**Priority:** P0  
**PRD Location:** `docs/prds/ui/e1-s8-dashboard-ui-prd.md`

**Scope:**

- Dashboard HTML template
- Tailwind CSS styling (dark theme)
- Header bar with status counts
- Recommended next panel
- Sort controls
- Project groups with traffic lights
- Agent cards with full detail
- HTMX interactivity
- SSE integration for real-time updates

**Key Requirements:**

- Must display all projects, agents, tasks
- Must show status counts (INPUT NEEDED, WORKING, IDLE)
- Must highlight recommended next agent
- Must support sorting (by project, by priority)
- Must show traffic light indicators per project
- Must display agent cards with state, task, priority, uptime
- Must colour-code state bars
- Must update in real-time via SSE

**OpenSpec Spec:** `openspec/specs/e1-s8-dashboard-ui/spec.md`

**Related Files:**

- `templates/dashboard.html`
- `static/css/dashboard.css` (Tailwind components)
- `static/js/dashboard.js` (HTMX + interactions)
- `src/routes/dashboard.py` (API endpoints)

**Data Model Changes:** None

**Dependencies:** Sprint 7 complete (SSE system)

**Acceptance Tests:**

- Dashboard renders all projects/agents
- Status counts accurate
- Recommended next highlights top agent
- Sorting works (by project, priority)
- Traffic lights show correct status
- Agent cards display all fields correctly
- State bars colour-coded
- Real-time updates work via SSE
- Responsive on desktop and tablet

---

### 9. Objective Tab

**Subsystem ID:** `objective-tab`  
**Sprint:** Sprint 9  
**Priority:** P0  
**PRD Location:** `docs/prds/ui/e1-s9-objective-tab-prd.md`

**Scope:**

- Objective tab HTML template
- Objective form (text + constraints)
- Auto-save logic (debounced)
- Objective history display
- API endpoints (GET/POST `/api/objective`, GET `/api/objective/history`)

**Key Requirements:**

- Must provide form for editing objective
- Must auto-save changes after debounce (2-3 seconds)
- Must display objective history with timestamps
- Must persist to Postgres (Objective + ObjectiveHistory)
- Must work with multiple concurrent users (shared state)

**OpenSpec Spec:** `openspec/specs/e1-s9-objective-tab/spec.md`

**Related Files:**

- `templates/objective.html`
- `static/js/objective.js` (auto-save logic)
- `src/routes/objective.py` (API endpoints)

**Data Model Changes:** None (uses Objective model from Sprint 3)

**Dependencies:** Sprint 3 complete (Objective model), Sprint 8 complete (tab navigation)

**Acceptance Tests:**

- Can edit objective text
- Auto-save triggers after debounce
- Changes persist across reloads
- History displays previous objectives
- Multiple users see same objective

---

### 10. Logging Tab

**Subsystem ID:** `logging-tab`  
**Sprint:** Sprint 10  
**Priority:** P0  
**PRD Location:** `docs/prds/ui/e1-s10-logging-tab-prd.md`

**Scope:**

- Logging tab HTML template
- Event log table display
- Filters (project, agent, event type)
- Real-time updates via SSE
- Pagination
- API endpoint (GET `/api/events`)

**Key Requirements:**

- Must display event log with columns: timestamp, project, agent, event type, details
- Must support filters (project, agent, event type)
- Must paginate for large logs
- Must update in real-time via SSE
- Must expand event details inline

**OpenSpec Spec:** `openspec/specs/e1-s10-logging-tab/spec.md`

**Related Files:**

- `templates/logging.html`
- `static/js/logging.js` (filters + SSE)
- `src/routes/logging.py` (API endpoint)

**Data Model Changes:** None (uses Event model)

**Dependencies:** Sprint 5 complete (events logged), Sprint 8 complete (tab navigation)

**Acceptance Tests:**

- Event log displays all events
- Filters work correctly
- Pagination works
- Real-time updates via SSE
- Event details expandable
- Performance acceptable with 10k+ events

---

### 11. Launcher Script

**Subsystem ID:** `launcher-script`  
**Sprint:** Sprint 11  
**Priority:** P0  
**PRD Location:** `docs/prds/scripts/e1-s11-launcher-script-prd.md`

**Scope:**

- `claude-headspace` CLI script
- `start` command
- Session UUID generation
- Project detection from `pwd`
- iTerm pane ID capture
- Session registration (HTTP POST)
- Environment variable setup
- Claude CLI launch
- Cleanup on exit

**Key Requirements:**

- Must launch Claude Code with monitoring enabled
- Must generate session UUID
- Must detect project from current directory
- Must capture iTerm pane ID for later focus
- Must register session with application (HTTP POST)
- Must set environment variable for hooks
- Must mark session inactive on exit

**OpenSpec Spec:** `openspec/specs/e1-s11-launcher-script/spec.md`

**Related Files:**

- `bin/claude-headspace` (CLI script)
- `src/services/session_registration.py` (API for registration)

**Data Model Changes:** None (uses Agent model)

**Dependencies:** Sprint 3 complete (Agent model), Sprint 4 complete (session discovery)

**Acceptance Tests:**

- `claude-headspace start` launches Claude Code
- Session UUID generated
- Project detected correctly
- iTerm pane ID captured
- Session registered (visible in dashboard)
- Environment variable set
- Cleanup runs on exit

---

### 12. AppleScript Integration

**Subsystem ID:** `applescript-integration`  
**Sprint:** Sprint 12  
**Priority:** P0  
**PRD Location:** `docs/prds/scripts/e1-s12-applescript-integration-prd.md`

**Scope:**

- AppleScript to focus iTerm pane by ID
- API endpoint (POST `/api/focus/<agent_id>`)
- Agent card click → API call wiring
- Permission error handling
- Fallback: show session path
- Terminal detection (iTerm vs WezTerm)

**Key Requirements:**

- Must focus iTerm window when agent card clicked
- Must activate correct pane (not just window)
- Must detect permission errors and show message
- Must provide fallback if focus fails
- Must support iTerm2 (WezTerm in future)

**OpenSpec Spec:** `openspec/specs/e1-s12-applescript-integration/spec.md`

**Related Files:**

- `src/services/iterm_focus.py` (AppleScript wrapper)
- `src/routes/focus.py` (API endpoint)
- `static/js/dashboard.js` (click handler)

**Data Model Changes:** None

**Dependencies:** Sprint 11 complete (pane IDs captured), Sprint 8 complete (agent cards)

**Acceptance Tests:**

- Click agent card → iTerm focuses
- Correct pane activated
- Permission errors detected, message shown
- Fallback shows session path
- Works on macOS Monterey+
- Focus latency <500ms

---

### 13. Hook Receiver

**Subsystem ID:** `hook-receiver`  
**Sprint:** Sprint 13  
**Priority:** P0  
**PRD Location:** `docs/prds/events/e1-s13-hook-receiver-prd.md`

**Scope:**

- **HookReceiver service** (`src/services/hook_receiver.py`):
  - Event processing with confidence=1.0
  - Session correlation via working directory matching
  - Event-to-state mapping logic
  - Integration with GoverningAgent and EventBus
- **Hook API routes** (`src/routes/hooks.py`):
  - POST `/hook/session-start` → Create agent, IDLE
  - POST `/hook/session-end` → Mark inactive
  - POST `/hook/stop` → PROCESSING → IDLE (primary completion signal)
  - POST `/hook/notification` → Timestamp update
  - POST `/hook/user-prompt-submit` → IDLE → PROCESSING
  - GET `/hook/status` → Status and last event times
- **Hook configuration** (`src/models/config.py`):
  - `HookConfig` model: enabled, fallback_polling, polling_interval_with_hooks (60s), session_timeout (300s)
- **Hybrid mode logic**:
  - Hooks primary, polling secondary (60s interval when hooks active)
  - Fallback detection: revert to 2s polling after 300s hook silence
  - Reconciliation: polling catches missed hook events
- **Session correlation**:
  - Map Claude `$CLAUDE_SESSION_ID` to agents via `cwd` matching
  - Cache correlations for performance
  - Handle new sessions dynamically
- **Hook notification script** (`bin/notify-headspace.sh`):
  - Bash script with curl POST to hook endpoints
  - Uses Claude env vars: `$CLAUDE_SESSION_ID`, `$CLAUDE_WORKING_DIRECTORY`
  - Timeout: 1s connect, 2s max time
  - Silent failures (exit 0 always)
- **Claude Code settings template** (`docs/claude-code-hooks-settings.json`):
  - JSON with all 5 hook configurations
  - Absolute paths required (not ~ or $HOME)
- **Installation script** (`bin/install-hooks.sh`):
  - Copy script to `~/.claude/hooks/`
  - Merge settings into `~/.claude/settings.json`
  - Set executable permissions
  - Validate paths are absolute
- **Hook status dashboard UI**:
  - Show "Hooks: enabled" or "Polling only" badge
  - Last hook event time per agent
  - Fallback indicator when polling takes over
- **Documentation** (`docs/hooks-setup.md`):
  - Installation instructions
  - Verification checklist
  - Troubleshooting guide

**Key Requirements:**

- Must receive hook events from Claude Code with <100ms latency
- Must process events with confidence=1.0 (not inferred)
- Must correlate Claude session IDs to agents via working directory
- Must update Agent/Task/Turn state from hook events
- Must implement hybrid mode: hooks primary (60s polling), fallback (2s polling after 300s silence)
- Must provide hook status dashboard with last event times
- Must degrade gracefully if hooks not installed
- Must provide installation script that works on clean macOS
- Must use absolute paths in hook configuration
- Must handle hook failures silently (don't block Claude Code)

**OpenSpec Spec:** `openspec/specs/e1-s13-hook-receiver/spec.md`

**Related Files:**

- `src/services/hook_receiver.py` (core service)
- `src/routes/hooks.py` (API endpoints)
- `src/models/config.py` (HookConfig model)
- `src/services/governing_agent.py` (integrate HookReceiver)
- `src/services/agent_store.py` (session correlation)
- `src/app.py` (register hooks blueprint)
- `bin/notify-headspace.sh` (hook script)
- `bin/install-hooks.sh` (installation script)
- `docs/claude-code-hooks-settings.json` (settings template)
- `docs/hooks-setup.md` (setup guide)
- `templates/dashboard.html` (add hook status badge)

**Data Model Changes:**

```python
# Add to AppConfig
class HookConfig(BaseModel):
    enabled: bool = True
    port: int | None = None  # None = use main Flask port
    fallback_polling: bool = True
    polling_interval_with_hooks: int = 60  # seconds
    session_timeout: int = 300  # seconds

# Add to Agent model (for correlation cache)
class Agent:
    ...
    claude_session_id: str | None = None  # For correlation
    last_hook_event_at: datetime | None = None  # For fallback detection
```

**Hook Event Processing Flow:**

```
1. Hook fires in Claude Code
2. notify-headspace.sh POSTs to /hook/{event}
3. HookReceiver.process_event():
   a. Correlate session ID to agent (via cwd)
   b. Map event to state transition
   c. Apply transition with confidence=1.0
   d. Update last_hook_event_at
   e. Emit SSE event
   f. Log to Event table
4. Dashboard updates in real-time (<100ms)
```

**Hook Event to State Mapping:**

| Hook Event       | Current State | New State   | Action                     |
| ---------------- | ------------- | ----------- | -------------------------- |
| SessionStart     | -             | IDLE        | Create agent if not exists |
| UserPromptSubmit | IDLE          | PROCESSING  | Start task turn            |
| Stop             | PROCESSING    | IDLE        | Complete task turn         |
| Notification     | any           | (no change) | Update timestamp only      |
| SessionEnd       | any           | ENDED       | Mark agent inactive        |

**Dependencies:** Sprint 6 complete (state machine), Sprint 8 complete (dashboard), Sprint 4 complete (agent_store)

**Acceptance Tests:**

- **Hook reception:**
  - POST to `/hook/session-start` → agent created with state=IDLE
  - POST to `/hook/user-prompt-submit` → agent transitions to PROCESSING
  - POST to `/hook/stop` → agent transitions to IDLE
  - POST to `/hook/session-end` → agent marked inactive
  - GET `/hook/status` → returns last event times
- **Session correlation:**
  - Same Claude session ID maps to same agent
  - Different sessions in same directory handled correctly
  - New sessions auto-create agents
- **Hybrid mode:**
  - Hooks active → polling interval = 60s
  - Hooks silent >300s → polling interval = 2s
  - Hooks resume → polling interval = 60s
- **State updates:**
  - Hook events update state with confidence=1.0
  - State updates faster than polling (<100ms)
  - SSE broadcast triggers dashboard refresh
- **Installation:**
  - `bin/install-hooks.sh` creates `~/.claude/hooks/notify-headspace.sh`
  - Script is executable (`chmod +x`)
  - `~/.claude/settings.json` updated with hook configuration
  - Absolute paths validated (not ~ or $HOME)
- **UI:**
  - Dashboard shows "Hooks: enabled" badge when active
  - Last hook event time displayed per agent
  - Fallback indicator when polling takes over
- **Graceful degradation:**
  - Hooks not installed → polling works normally
  - Hook endpoint down → events logged, polling continues
  - Hook script fails → Claude Code session unaffected
- **End-to-end:**
  - Start Claude Code → SessionStart hook fires → agent appears in dashboard
  - Send prompt → UserPromptSubmit hook fires → state = PROCESSING
  - Claude responds → Stop hook fires → state = IDLE
  - Exit Claude → SessionEnd hook fires → agent inactive

---

## Sprint Dependencies & Critical Path

```
Sprint 1 (Flask Bootstrap)
    │
    └──▶ Sprint 2 (Database Setup)
            │
            └──▶ Sprint 3 (Domain Models)
                    │
                    ├──▶ Sprint 4 (File Watcher)
                    │       │
                    │       └──▶ Sprint 5 (Event System)
                    │               │
                    │               └──▶ Sprint 6 (State Machine)
                    │                       │
                    │                       └──▶ Sprint 7 (SSE)
                    │                               │
                    │                               └──▶ Sprint 8 (Dashboard UI)
                    │                                       │
                    │                                       ├──▶ Sprint 9 (Objective)
                    │                                       ├──▶ Sprint 10 (Logging)
                    │                                       └──▶ Sprint 13 (Hooks)
                    │
                    └──▶ Sprint 11 (Launcher)
                            │
                            └──▶ Sprint 12 (AppleScript)
                                    │
                                    └──▶ [Epic 1 Complete]
```

**Critical Path:** Sprint 1 → Sprint 2 → Sprint 3 → Sprint 4 → Sprint 5 → Sprint 6 → Sprint 7 → Sprint 8

**Parallel Tracks:**

- Sprint 9, 10, 13 can run in parallel after Sprint 8
- Sprint 11 can start after Sprint 3 (Agent model exists)
- Sprint 12 depends on Sprint 11 (needs pane IDs)

**Total Duration:** 13-15 weeks

---

## Technical Decisions Made

### Decision 1: Event-Driven Architecture

**Decision:** Build event-driven from day one (not polling-first).

**Rationale:** Events from Claude Code jsonl files are the source of truth. State machine reacts to events. Enables dual event sources (hooks + polling).

**Impact:**

- All state updates triggered by events
- Event log provides audit trail
- Easier to add hook events later
- More complex than simple polling, but more extensible

---

### Decision 2: 5-State Task Model

**Decision:** Use 5-state model (idle, commanded, processing, awaiting_input, complete) instead of 3-state.

**Rationale:**

- More granular visibility (know when agent is waiting vs working)
- Aligns with turn intents (command → commanded, question → awaiting_input)
- Enables better prioritisation (awaiting_input is high priority)

**Impact:**

- State machine more complex
- Intent detection critical
- Better UX in dashboard

---

### Decision 3: Turn-Level Granularity

**Decision:** Track every turn (user/agent exchange), not just task-level.

**Rationale:**

- Foundation for Epic 3 turn summarisation
- Enables fine-grained audit trail
- Better understanding of agent behavior (how many turns per task?)

**Impact:**

- More database writes (one per turn)
- Richer data for future features
- Slight performance overhead

---

### Decision 4: Dual Event Sources (Hooks + Polling)

**Decision:** Support both Claude Code hooks (instant) and jsonl polling (fallback).

**Rationale:**

- Hooks require user setup (may not adopt)
- Polling works without setup (graceful degradation)
- Hooks provide instant updates (<100ms vs ~2 seconds)
- Dual sources = best of both worlds

**Impact:**

- Two code paths for same events (hooks vs polling)
- Need deduplication logic (same event from both sources)
- More complex, but better UX

---

### Decision 5: Postgres (Not SQLite)

**Decision:** Use Postgres from day one (not SQLite).

**Rationale:**

- Better concurrency (multiple writers: watcher + Flask)
- Better performance for event logs (10k+ events)
- Production-ready (no migration needed later)

**Impact:**

- Setup complexity (users need Postgres installed)
- Mitigated by: clear setup docs, Docker Compose option

---

### Decision 6: Tailwind CSS

**Decision:** Use Tailwind CSS (not Bootstrap or custom CSS).

**Rationale:**

- Model knows Tailwind well
- Utility-first = faster development
- Dark theme easy to implement
- Modern, customizable

**Impact:**

- Build pipeline required (PostCSS)
- Larger CSS bundle (mitigate: purge unused)
- Faster development velocity

---

### Decision 7: HTMX (Not React/Vue)

**Decision:** Use HTMX for interactivity (not React/Vue).

**Rationale:**

- Server-rendered HTML (simpler, less JS)
- SSE integration built-in
- Proven in v2
- No build pipeline for JS

**Impact:**

- Limited to HTMX capabilities (no complex client-side state)
- Good for Epic 1 scope (dashboard, forms)
- May need React later for advanced features

---

### Decision 8: Flask-Migrate (Not Alembic Directly)

**Decision:** Use Flask-Migrate wrapper around Alembic.

**Rationale:**

- Flask integration (commands via Flask CLI)
- Easier for most users
- Still uses Alembic under the hood

**Impact:**

- Simpler commands (`flask db upgrade`)
- Flask dependency

---

## Open Questions

### 1. Session Inactivity Timeout

**Question:** How long before marking a session inactive?

**Options:**

- **Option A:** 5 minutes (aggressive, may false-positive on slow tasks)
- **Option B:** 15 minutes (balanced)
- **Option C:** 30 minutes (conservative, may leave stale sessions visible)

**Recommendation:** Start with 15 minutes, make configurable in `config.yaml`.

**Decision needed by:** Sprint 4 implementation

---

### 2. Intent Detection Patterns

**Question:** What regex patterns indicate each turn intent?

**Options:**

- **command:** User starts with command-like text (e.g., "Create a...", "Add a...", "Fix...")
- **question:** Agent ends with "?" or "Would you like...", "Should I..."
- **completion:** Agent says "Done", "Completed", "Finished", "Ready for..."
- **progress:** Agent says "I'm...", "Working on...", "Processing..."
- **answer:** User responds to previous question

**Recommendation:** Start with simple regex, iterate based on false positives/negatives.

**Decision needed by:** Sprint 6 implementation

---

### 3. Hook Authentication Method

**Question:** How should hooks authenticate requests?

**Options:**

- **Option A:** Shared secret in environment variable (simple, local-friendly)
- **Option B:** API key per user (more secure, more complex)
- **Option C:** None (local only, trust all requests)

**Recommendation:** Option A (shared secret) for Epic 1, Option B for production deployment.

**Decision needed by:** Sprint 13 implementation

---

## Risks & Mitigation

### Risk 1: State Machine Complexity

**Risk:** 5-state model with turn intent detection may be unreliable, causing incorrect state transitions.

**Impact:** High (breaks core feature — state tracking)

**Mitigation:**

- Comprehensive unit tests (all transitions, edge cases)
- Regex patterns tuned on real Claude Code sessions
- Fallback: LLM-based intent detection in Epic 3
- State transition validator (reject invalid transitions)

**Monitoring:** Track transition errors, alert if >5% of turns fail intent detection

---

### Risk 2: Hook Adoption

**Risk:** Users may not install hooks, degrading to polling-only mode.

**Impact:** Medium (instant updates are nice-to-have, not required)

**Mitigation:**

- Make hooks optional (graceful degradation)
- Clear value proposition (instant vs 2-second polling)
- Simple installation script (`bin/notify-headspace.sh`)
- Dashboard shows "Hooks enabled" vs "Polling" indicator

**Monitoring:** Track % of sessions using hooks vs polling

---

### Risk 3: iTerm Permission Issues

**Risk:** macOS privacy controls may block AppleScript, breaking click-to-focus.

**Impact:** Medium (click-to-focus is high-value feature)

**Mitigation:**

- Clear setup instructions (System Preferences → Privacy → Automation)
- Detect permission errors, show actionable message
- Fallback: show session path (user can manually switch)
- Test on multiple macOS versions

**Monitoring:** Track focus failures, alert if >10% fail

---

### Risk 4: Event Log Performance

**Risk:** Event log may grow large (10k+ events), causing slow queries and UI lag.

**Impact:** Medium (affects logging tab usability)

**Mitigation:**

- Database indexing on timestamp, project_id, agent_id, event_type
- Pagination (limit to 100 events per page)
- Server-side filtering (don't load all events into browser)
- Archive old events (move to separate table or delete after 90 days)

**Monitoring:** Track query times, alert if P95 >500ms

---

### Risk 5: Watchdog Missing Events

**Risk:** Watchdog may miss jsonl file changes on high-frequency updates or system load.

**Impact:** Medium (missing turns = incomplete state tracking)

**Mitigation:**

- Periodic full scan (every 30 seconds) in addition to watch events
- Compare jsonl line count to database turn count (detect missing turns)
- Log watchdog errors and missed events
- Test under load (multiple concurrent sessions)

**Monitoring:** Track missed turn count, alert if >1% missed

---

## Success Metrics

From Epic 1 Acceptance Criteria:

### Test Case 1: Basic Event Flow ✅

**Setup:** Start application, start Claude Code session via launcher.

**Success:**

- ✅ Session discovered and appears in dashboard
- ✅ Issue command → Task created in `commanded` state
- ✅ Agent responds → Task transitions to `processing`
- ✅ Agent completes → Task transitions to `complete`, then `idle`
- ✅ Dashboard updates in real-time (<1 second latency)

---

### Test Case 2: Multi-Session Concurrency ✅

**Setup:** Start 3 Claude Code sessions across 2 projects.

**Success:**

- ✅ All 3 sessions appear in dashboard
- ✅ Each session tracked independently
- ✅ Status counts accurate (INPUT NEEDED, WORKING, IDLE)
- ✅ Sort by project groups sessions correctly

---

### Test Case 3: Click-to-Focus ✅

**Setup:** 2 active Claude Code sessions in iTerm.

**Success:**

- ✅ Click agent card for session 1 → iTerm focuses session 1
- ✅ Click agent card for session 2 → iTerm focuses session 2
- ✅ Focus latency <500ms

---

### Test Case 4: Hook Events ✅

**Setup:** Claude Code sessions with hooks installed.

**Success:**

- ✅ Hook events received at endpoints
- ✅ State updates instantly (<100ms)
- ✅ Hook status dashboard shows last event times
- ✅ Faster than polling (2 seconds)

---

### Test Case 5: Objective Setting ✅

**Setup:** Navigate to objective tab.

**Success:**

- ✅ Set objective text → auto-saves after debounce
- ✅ Changes persist across page reload
- ✅ Objective history shows previous objectives

---

### Test Case 6: Event Filtering ✅

**Setup:** Generate multiple event types, navigate to logging tab.

**Success:**

- ✅ Event log displays all events
- ✅ Filter by project → only matching events shown
- ✅ Filter by event type → only matching events shown
- ✅ Real-time updates via SSE (new events appear automatically)

---

## If You Cannot Do This, You Have Not Built the Differentiator

**The differentiator is NOT:**

- ❌ "Monitor Claude Code sessions" (generic)
- ❌ "View terminal output" (trivial)
- ❌ "3-state model" (too coarse)

**The differentiator IS:**

- ✅ **5-state task model with turn-level granularity**
- ✅ **Dual event sources (hooks + polling) for instant updates**
- ✅ **Event-driven architecture (not polling-first)**
- ✅ **Click-to-focus iTerm integration**
- ✅ **Cross-project objective alignment**

---

## Recommended PRD Generation Order

Generate OpenSpec PRDs in implementation order with rationale:

### Phase 1: Foundation (Weeks 1-2)

1. **flask-bootstrap** (`docs/prds/flask/e1-s1-flask-bootstrap-prd.md`) — Application factory, config, health check
2. **database-setup** (`docs/prds/core/e1-s2-database-setup-prd.md`) — Postgres connection, migrations

**Rationale:** Must have runnable application before building features.

---

### Phase 2: Data Model (Weeks 3-4)

3. **domain-models** (`docs/prds/core/e1-s3-domain-models-prd.md`) — All models, relationships, migrations

**Rationale:** Data model is foundation for all features.

---

### Phase 3: Event System (Weeks 5-7)

4. **file-watcher** (`docs/prds/events/e1-s4-file-watcher-prd.md`) — Watchdog, jsonl parsing, session/turn detection
5. **event-system** (`docs/prds/events/e1-s5-event-system-prd.md`) — Event writer, background process

**Rationale:** Event flow must work before state machine can react.

---

### Phase 4: State Machine (Week 8)

6. **state-machine** (`docs/prds/state/e1-s6-state-machine-prd.md`) — Task state logic, turn intent mapping

**Rationale:** State machine is core logic, needs events flowing.

---

### Phase 5: Real-time UI (Weeks 9-11)

7. **sse-system** (`docs/prds/api/e1-s7-sse-system-prd.md`) — SSE endpoint, broadcaster, HTMX
8. **dashboard-ui** (`docs/prds/ui/e1-s8-dashboard-ui-prd.md`) — Dashboard layout, agent cards, real-time updates

**Rationale:** SSE must work before dashboard can update in real-time.

---

### Phase 6: User Features (Weeks 12-13)

9. **objective-tab** (`docs/prds/ui/e1-s9-objective-tab-prd.md`) — Objective form, auto-save, history
10. **logging-tab** (`docs/prds/ui/e1-s10-logging-tab-prd.md`) — Event log display, filters, pagination

**Rationale:** Dashboard exists, add supporting features.

---

### Phase 7: Integration (Weeks 14-15)

11. **launcher-script** (`docs/prds/scripts/e1-s11-launcher-script-prd.md`) — CLI tool, session registration
12. **applescript-integration** (`docs/prds/scripts/e1-s12-applescript-integration-prd.md`) — iTerm focus, API endpoint
13. **hook-receiver** (`docs/prds/events/e1-s13-hook-receiver-prd.md`) — Hook endpoints, event processing

**Rationale:** Integration features tie everything together.

---

## Document History

| Version | Date       | Author          | Changes                                                                                      |
| ------- | ---------- | --------------- | -------------------------------------------------------------------------------------------- |
| 1.0     | 2026-01-28 | PM Agent (John) | Initial detailed roadmap for Epic 1 (11 sprints)                                             |
| 1.1     | 2026-01-29 | PM Agent (John) | Restructured to 13 sprints (one PRD per sprint), added PRD directory structure and filenames |

---

**End of Epic 1 Detailed Roadmap**
