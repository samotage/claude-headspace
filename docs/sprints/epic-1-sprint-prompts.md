# Epic 1 Sprint Prompts for PRD Workshop

**Project:** Claude Headspace v3.1  
**Epic:** Epic 1 — Core Foundation + Event-Driven Hooks  
**Date:** 2026-01-29  
**Purpose:** These prompts are designed for use with the PRD workshop to generate detailed Product Requirements Documents for each sprint in Epic 1.

---

## How to Use These Prompts

Each prompt below corresponds to one sprint from the Epic 1 detailed roadmap. Use these prompts with the `/10: prd-workshop` command to generate PRDs that will feed into the orchestration system.

**Workflow:**

1. Copy the prompt for the sprint you want to work on
2. Run `/10: prd-workshop` in Claude Code
3. Paste the prompt when asked
4. Review and refine the generated PRD
5. Add to queue with `/10: queue-add`
6. Process with `/20: prd-orchestrate`

---

## Epic 1 Sprint 1: Project Bootstrap

### Subsystem: flask-bootstrap

**Prompt:**

Create a PRD for the Flask application bootstrap subsystem.

CONTEXT:
Refer to @docs/application/claude_headspace_v3.1_conceptual_overview.md for the full system design, domain model, and terminology.
Refer to @docs/application/claude_headspace_v3.1_epic1_guidance.md for Epic 1 architecture principles, tech stack decisions, and UI specifications.
Refer to @docs/roadmap/claude_headspace_v3.1_epic1_detailed_roadmap.md Sprint 1 section for detailed requirements.

OBJECTIVE:
Build a runnable Flask application using the application factory pattern with proper configuration loading, error handling, and logging.

REQUIREMENTS:

- Python project structure with pyproject.toml and src/ layout
- Flask application factory pattern
- Configuration loading from config.yaml with environment variable overrides
- Health check endpoint at /health
- Error handlers for 404 and 500 errors
- Logging configuration (console + file output)
- Development vs production mode support
- Base HTML template structure ready for Tailwind CSS

TECHNICAL CONSTRAINTS:

- Must use Flask (not FastAPI or other frameworks)
- Must support YAML configuration
- Must be testable (application factory enables test isolation)
- Configuration schema should match config.yaml structure in Epic 1 guidance

SUCCESS CRITERIA:

- `flask run` starts the server successfully
- Server responds to health check at /health with 200 OK
- Configuration loads from config.yaml
- Environment variables can override config values
- Errors return proper error pages
- Logs are written to console and file
- Base HTML renders with dark theme structure

DELIVERABLES:

- src/**init**.py
- src/app.py (application factory)
- src/config.py (config loader)
- config.yaml (template)
- .env.example
- pyproject.toml or requirements.txt
- Basic test suite

OUTPUT LOCATION:
docs/prds/flask/e1-s1-flask-bootstrap-prd.md

---

### Subsystem: database-setup

**Prompt:**

Create a PRD for the database setup and migration subsystem.

CONTEXT:
Refer to @docs/application/claude_headspace_v3.1_conceptual_overview.md for the domain model structure.
Refer to @docs/application/claude_headspace_v3.1_epic1_guidance.md for architecture decisions (Postgres, not SQLite).
Refer to @docs/roadmap/claude_headspace_v3.1_epic1_detailed_roadmap.md Sprint 1 section for detailed requirements.

OBJECTIVE:
Establish Postgres database connection with migration support using Flask-Migrate.

REQUIREMENTS:

- Postgres connection using credentials from config.yaml
- SQLAlchemy ORM configuration
- Flask-Migrate integration
- Database initialization script
- Connection pooling configuration
- Migration commands (init, migrate, upgrade, downgrade)
- Connection error handling with graceful degradation

TECHNICAL CONSTRAINTS:

- Must use Postgres (local installation, not Docker in Epic 1)
- Must use Flask-Migrate (wrapper around Alembic)
- Connection string format: postgresql://user:password@host:port/database
- Pool size configurable via config.yaml
- Must support connection testing before server starts

DATABASE CONFIGURATION SCHEMA:

```yaml
database:
  host: localhost
  port: 5432
  name: claude_headspace
  user: postgres
  password: ""
  pool_size: 10
```

SUCCESS CRITERIA:

- Application connects to Postgres on startup
- Test query succeeds (e.g., SELECT 1)
- Migration commands work: flask db init, flask db migrate, flask db upgrade
- Connection errors logged with clear messages
- Connection pooling works (multiple concurrent requests)
- Database initialization script creates database if not exists

DELIVERABLES:

- src/database.py (SQLAlchemy setup)
- migrations/ directory structure
- Database initialization script
- Migration documentation
- Connection testing utility

OUTPUT LOCATION:
docs/prds/core/e1-s1-database-setup-prd.md

---

## Epic 1 Sprint 2: Domain Models & Database Schema

### Subsystem: domain-models

**Prompt:**

Create a PRD for the complete domain model implementation with database schema.

CONTEXT:
Refer to @docs/application/claude_headspace_v3.1_conceptual_overview.md Section 5 (Core Domain Model) for the complete data structure.
Refer to @docs/application/claude_headspace_v3.1_conceptual_overview.md Section 4 (State Model) for the Task/Turn state machine logic.
Refer to @docs/roadmap/claude_headspace_v3.1_epic1_detailed_roadmap.md Sprint 2 section for detailed requirements and schema definitions.

OBJECTIVE:
Implement all core domain models (Objective, Project, Agent, Task, Turn, Event) with proper relationships, validations, and state enums.

REQUIREMENTS:

1. OBJECTIVE MODEL
   - current_text (required)
   - constraints (optional)
   - set_at (timestamp)
   - Relationship: has_many ObjectiveHistory

2. OBJECTIVE HISTORY MODEL
   - objective_id (foreign key)
   - text (required)
   - constraints (optional)
   - started_at (timestamp)
   - ended_at (timestamp, nullable)

3. PROJECT MODEL
   - name (required)
   - path (required, unique)
   - github_repo (optional)
   - current_branch (optional)
   - created_at (timestamp)
   - Relationship: has_many Agents

4. AGENT MODEL
   - session_uuid (required, unique)
   - project_id (foreign key)
   - iterm_pane_id (optional, for AppleScript)
   - claude_session_id (optional, for hook correlation)
   - started_at (timestamp)
   - last_seen_at (timestamp)
   - last_hook_event_at (timestamp, nullable)
   - is_active (boolean)
   - Relationship: has_many Tasks

5. TASK MODEL
   - agent_id (foreign key)
   - state (enum: idle, commanded, processing, awaiting_input, complete)
   - started_at (timestamp)
   - completed_at (timestamp, nullable)
   - Relationship: has_many Turns

6. TURN MODEL
   - task_id (foreign key)
   - actor (enum: user, agent)
   - text (required)
   - intent (enum: command, answer, question, completion, progress)
   - timestamp (timestamp)

7. EVENT MODEL (audit log)
   - id (primary key)
   - timestamp (timestamp, indexed)
   - project_id (foreign key, nullable)
   - agent_id (foreign key, nullable)
   - task_id (foreign key, nullable)
   - turn_id (foreign key, nullable)
   - event_type (string, indexed)
   - payload (JSON)

TECHNICAL CONSTRAINTS:

- Use SQLAlchemy ORM
- Define enums using SQLAlchemy Enum type
- Foreign keys must have proper cascade rules
- Indexes on frequently queried fields (timestamps, state, event_type)
- Validation rules enforced at model level
- Support for querying current state (e.g., agent.current_task)

STATE ENUM VALUES:

- Task.state: idle | commanded | processing | awaiting_input | complete
- Turn.actor: user | agent
- Turn.intent: command | answer | question | completion | progress

EVENT TYPES (initial set):

- session_discovered
- session_inactive
- turn_detected
- state_transition
- task_started
- task_completed

SUCCESS CRITERIA:

- All models can be created via SQLAlchemy
- Database migrations run cleanly
- Foreign key relationships enforced
- Enum fields validate correctly (reject invalid values)
- Can create: Objective with history, Project, Agent, Task with Turns, Events
- Query patterns work: get agent's current task, get tasks for project, get events by type
- Cascade deletes work as expected (document cascade rules)
- Model validations prevent invalid data

DELIVERABLES:

- src/models/**init**.py
- src/models/objective.py
- src/models/project.py
- src/models/agent.py
- src/models/task.py
- src/models/turn.py
- src/models/event.py
- Database migration files
- Model relationship diagram (optional, markdown)
- Query pattern documentation

OUTPUT LOCATION:
docs/prds/core/e1-s2-domain-models-prd.md

---

## Epic 1 Sprint 3: File Watcher & Event System

### Subsystem: file-watcher

**Prompt:**

Create a PRD for the file watcher subsystem that monitors Claude Code jsonl files.

CONTEXT:
Refer to @docs/application/claude_headspace_v3.1_conceptual_overview.md Section 2 (System Integration) for Claude Code integration details.
Refer to @docs/application/claude_headspace_v3.1_epic1_guidance.md for auto-discovery architecture principles.
Refer to @docs/roadmap/claude_headspace_v3.1_epic1_detailed_roadmap.md Sprint 3 section for detailed requirements.

OBJECTIVE:
Watch Claude Code jsonl files for changes, parse them, and detect new sessions and turns.

REQUIREMENTS:

1. WATCHDOG INTEGRATION
   - Monitor ~/.claude/projects/ recursively
   - Detect new jsonl files (new sessions)
   - Detect file modifications (new turns)
   - Debouncing strategy for high-frequency changes
   - Event batching to reduce processing overhead

2. JSONL PARSER
   - Parse Claude Code jsonl format (line-by-line)
   - Handle malformed lines gracefully
   - Extract turn information: actor, text, timestamp
   - Detect turn intent patterns (initial regex-based)
   - Store file offset to track last-read position

3. SESSION DISCOVERY
   - Detect new jsonl files
   - Generate or extract session UUID
   - Extract project path from folder name (decode `-` to `/`)
   - Create Agent record if not exists
   - Mark session as active

4. TURN DETECTION
   - Read new lines from jsonl files
   - Parse line format
   - Create Turn records
   - Emit turn_detected event
   - Update Agent.last_seen_at timestamp

5. PROJECT AUTO-DISCOVERY
   - Decode project path from folder name
   - Example: `-Users-samotage-dev-otagelabs-claude-headspace` → `/Users/samotage/dev/otagelabs/claude_headspace`
   - Handle edge cases: spaces, unicode, special characters
   - Verify project path exists on filesystem

6. GIT METADATA EXTRACTION
   - Run git commands in project directory
   - Extract: repo URL, current branch, recent commits
   - Cache results (avoid git calls on every event)
   - Handle non-git directories gracefully

TECHNICAL CONSTRAINTS:

- Use watchdog library for filesystem monitoring
- Line-by-line parsing (not full-file reads)
- Store file offset in memory (or database for persistence)
- Git metadata cached per project with TTL (e.g., 60 seconds)
- Error handling: parsing failures should not crash watcher

JSONL FORMAT EXAMPLE:

```json
{"type":"user_message","text":"Create a health check endpoint","timestamp":"2026-01-29T10:30:00Z"}
{"type":"assistant_message","text":"I'll create a health check endpoint for you...","timestamp":"2026-01-29T10:30:15Z"}
```

SESSION DISCOVERY FLOW:

1. Watchdog detects new file: ~/.claude/projects/-Users-...-project/abc123.jsonl
2. Extract session_uuid: abc123
3. Decode project path from folder name
4. Create Agent record with session_uuid and project_id
5. Emit session_discovered event

TURN DETECTION FLOW:

1. Watchdog detects file modification
2. Read new lines from last offset
3. Parse each line as Turn
4. Create Turn record
5. Emit turn_detected event
6. Update Agent.last_seen_at

SUCCESS CRITERIA:

- Start watcher, start Claude Code session → session discovered
- Issue command in Claude Code → turn detected within 2 seconds
- Turn records created with correct actor, text, intent
- Multiple sessions tracked concurrently without interference
- Project path decoded correctly from folder names
- Git metadata extracted and cached
- Parsing errors logged but don't crash watcher
- Events written to database via Event model
- Watcher recovers from crashes (if using supervisor)

DELIVERABLES:

- src/services/file_watcher.py (Watchdog setup)
- src/services/jsonl_parser.py (parsing logic)
- src/services/project_discovery.py (path decoding)
- src/services/git_metadata.py (git integration)
- Watcher startup script
- Test suite with sample jsonl files
- Documentation: jsonl format, session discovery flow

OUTPUT LOCATION:
docs/prds/events/e1-s3-file-watcher-prd.md

---

### Subsystem: event-system

**Prompt:**

Create a PRD for the event system that writes events to Postgres and runs as a background process.

CONTEXT:
Refer to @docs/application/claude_headspace_v3.1_conceptual_overview.md for event-driven architecture principles.
Refer to @docs/application/claude_headspace_v3.1_epic1_guidance.md Section "Event-Driven Design" for the event flow.
Refer to @docs/roadmap/claude_headspace_v3.1_epic1_detailed_roadmap.md Sprint 3 section for detailed requirements.

OBJECTIVE:
Provide a reliable event writer service and background watcher process with supervision.

REQUIREMENTS:

1. EVENT WRITER SERVICE
   - Write events to Postgres atomically
   - Event schema: timestamp, project_id, agent_id, event_type, payload (JSON)
   - Support bulk writes (batch events for performance)
   - Error handling: retry logic with exponential backoff
   - Logging: log all events written

2. EVENT TYPES TAXONOMY
   - session_discovered: New Claude Code session detected
   - session_inactive: Session marked inactive (timeout or explicit end)
   - turn_detected: New turn parsed from jsonl
   - state_transition: Task state changed
   - task_started: New task initiated
   - task_completed: Task finished
   - (Extensible for future event types)

3. EVENT PAYLOAD SCHEMA
   - Consistent JSON structure per event type
   - Example for turn_detected:
     ```json
     {
       "session_uuid": "abc123",
       "turn_id": 42,
       "actor": "user",
       "intent": "command",
       "text_preview": "Create a health check..."
     }
     ```

4. BACKGROUND WATCHER PROCESS
   - Separate process from Flask application
   - Integrates file_watcher service
   - Runs continuously (daemon mode)
   - Graceful shutdown on SIGTERM
   - Health check mechanism (e.g., write heartbeat to file/database)

5. PROCESS SUPERVISION
   - Auto-restart on crash
   - Options: supervisord, systemd, or custom wrapper
   - Logging: capture stdout/stderr
   - PID file management
   - Startup/shutdown scripts

TECHNICAL CONSTRAINTS:

- Background process must not block Flask application
- Event writes must be atomic (use transactions)
- Bulk writes should batch up to 100 events or 1 second timeout
- Retry logic: 3 attempts with exponential backoff (1s, 2s, 4s)
- Supervision: prefer supervisord for macOS compatibility
- Process must release database connections on shutdown

EVENT WRITER FLOW:

1. File watcher detects change
2. Call event_writer.write(event_type, project_id, agent_id, payload)
3. Event writer creates Event record
4. Commit transaction
5. On success: return
6. On failure: retry with backoff, then log error

BACKGROUND PROCESS FLOW:

1. Load configuration
2. Connect to database
3. Initialize file watcher
4. Start watchdog observer
5. Run event loop
6. On SIGTERM: stop observer, close database, exit gracefully

SUCCESS CRITERIA:

- Events written to Postgres successfully
- Background process runs continuously without manual intervention
- Process restarts automatically on crash (if supervised)
- Event types documented and consistent
- Payloads well-formed and queryable
- Bulk writes improve performance (test with 1000+ events)
- Graceful shutdown closes resources cleanly
- No memory leaks over long runs (24+ hours)

DELIVERABLES:

- src/services/event_writer.py (event writing logic)
- bin/watcher.py (background process entry point)
- supervisord.conf or systemd unit file
- Startup/shutdown scripts
- Event type documentation
- Payload schema documentation
- Test suite: unit tests for event_writer, integration test for watcher

OUTPUT LOCATION:
docs/prds/events/e1-s3-event-system-prd.md

---

## Epic 1 Sprint 4: Task/Turn State Machine

### Subsystem: state-machine

**Prompt:**

Create a PRD for the Task/Turn state machine that governs state transitions.

CONTEXT:
Refer to @docs/application/claude_headspace_v3.1_conceptual_overview.md Section 4 (State Model) for the complete state machine definition and turn intent mapping.
Refer to @docs/roadmap/claude_headspace_v3.1_epic1_detailed_roadmap.md Sprint 4 section for detailed requirements and state transition rules.

OBJECTIVE:
Implement the 5-state task model with turn intent detection and state transition validation.

REQUIREMENTS:

1. TASK STATE MACHINE
   - States: idle → commanded → processing → awaiting_input/complete → idle
   - State transitions triggered by turn intent
   - Validation: reject invalid transitions
   - Logging: log all state transitions as events

2. TURN INTENT DETECTION (REGEX-BASED)
   - command: User starts with command-like text
     - Patterns: "^(Create|Add|Fix|Update|Delete|Build|Implement|Write)\\b"
   - answer: User responds to previous question
     - Context-based: last turn was agent question
   - question: Agent ends with "?" or asks for input
     - Patterns: "\\?$|Would you like|Should I|Can I|Do you want"
   - completion: Agent signals task done
     - Patterns: "\\b(Done|Completed|Finished|Ready)\\b"
   - progress: Agent reports intermediate progress
     - Patterns: "\\b(Working on|Processing|I'm|Currently|In progress)\\b"

3. STATE TRANSITION VALIDATOR
   - Valid transition matrix (see turn intent to task state mapping in conceptual overview)
   - Reject invalid transitions with error log
   - Return transition result: success | invalid | error

4. TASK LIFECYCLE MANAGEMENT
   - Task starts: user turn with intent=command creates new Task in commanded state
   - Task progresses: agent turns transition state based on intent
   - Task completes: agent turn with intent=completion transitions to complete, then idle
   - Task reset: complete → idle (ready for next task)

5. AGENT STATE DERIVATION
   - Agent.state = current_task.state
   - If no active task, Agent.state = idle
   - Query method: agent.get_current_task()

6. UNIT TESTS FOR STATE MACHINE
   - Test all valid transitions (happy path)
   - Test invalid transitions (expect rejection)
   - Test edge cases: agent crashes mid-task, user force-quits
   - Test intent detection accuracy with sample turns

TECHNICAL CONSTRAINTS:

- Intent detection: regex-based in Epic 1 (LLM-based in Epic 3)
- State transitions must emit state_transition events
- Transitions must be atomic (database transaction)
- Intent detection should be fast (<10ms per turn)
- State machine should be testable in isolation (unit tests)

STATE TRANSITION MATRIX:
| Current State | Turn Actor | Turn Intent | New State |
|----------------|------------|-------------|----------------|
| idle | user | command | commanded |
| commanded | agent | progress | processing |
| commanded | agent | question | awaiting_input |
| commanded | agent | completion | complete |
| processing | agent | progress | processing |
| processing | agent | question | awaiting_input |
| processing | agent | completion | complete |
| awaiting_input | user | answer | processing |
| complete | - | - | idle (task ends) |

TASK LIFECYCLE EXAMPLE:

```
1. User: "Create a health check endpoint"
   → Turn: { actor: user, intent: command }
   → Task: state = commanded

2. Agent: "I'll create a health check endpoint..."
   → Turn: { actor: agent, intent: progress }
   → Task: state = processing

3. Agent: "Should I add a database check too?"
   → Turn: { actor: agent, intent: question }
   → Task: state = awaiting_input

4. User: "Yes, add database check"
   → Turn: { actor: user, intent: answer }
   → Task: state = processing

5. Agent: "Done! Health check endpoint created with database check."
   → Turn: { actor: agent, intent: completion }
   → Task: state = complete → idle
```

SUCCESS CRITERIA:

- All valid transitions succeed
- Invalid transitions rejected with error log
- Task lifecycle correct: command → ... → completion
- Agent state derived correctly from current task
- Intent detection accurate: >90% on test cases (100 sample turns)
- State transitions logged as events
- Unit tests pass (100% coverage on state machine logic)
- Edge cases handled: agent crash → task stays in last state, marked as stale

DELIVERABLES:

- src/services/state_machine.py (state machine logic)
- src/services/intent_detector.py (regex-based detection)
- tests/test_state_machine.py (comprehensive unit tests)
- State transition diagram (markdown or image)
- Intent detection pattern documentation
- Test dataset: 100 sample turns with expected intents

OUTPUT LOCATION:
docs/prds/state/e1-s4-state-machine-prd.md

---

## Epic 1 Sprint 5: SSE & Real-time Updates

### Subsystem: sse-system

**Prompt:**

Create a PRD for the Server-Sent Events (SSE) system for real-time browser updates.

CONTEXT:
Refer to @docs/application/claude_headspace_v3.1_conceptual_overview.md Section 2 (System Integration) for SSE integration details.
Refer to @docs/application/claude_headspace_v3.1_epic1_guidance.md for HTMX integration requirements.
Refer to @docs/roadmap/claude_headspace_v3.1_epic1_detailed_roadmap.md Sprint 5 section for detailed requirements.

OBJECTIVE:
Implement SSE endpoint and event broadcaster to push real-time updates to the dashboard.

REQUIREMENTS:

1. SSE ENDPOINT IN FLASK
   - Route: GET /api/events
   - Streams events to connected clients
   - Content-Type: text/event-stream
   - Keeps connection alive with heartbeats
   - Supports multiple concurrent clients

2. EVENT BROADCASTER SERVICE
   - In-memory queue for Epic 1 (Redis pub/sub in Epic 2+)
   - Broadcast events to all connected SSE clients
   - Event format: SSE protocol (data: {...}\n\n)
   - Event types: state_change, task_update, agent_update, objective_change
   - Non-blocking: don't wait for slow clients

3. HTMX SSE INTEGRATION
   - Use HTMX sse extension
   - Subscribe to event stream on page load
   - Trigger UI updates on received events
   - Handle reconnection automatically

4. RECONNECTION HANDLING
   - Automatic reconnect on disconnect
   - Exponential backoff strategy (1s, 2s, 4s, 8s, max 30s)
   - Client-side retry logic
   - Last-Event-ID support (optional for Epic 1)

5. EVENT FILTERING
   - Clients can subscribe to specific event types (optional for Epic 1)
   - Query parameter: /api/events?types=state_change,task_update
   - Server-side filtering before broadcast

6. HEARTBEAT MECHANISM
   - Send keepalive comment every 30 seconds
   - Format: `: heartbeat\n\n`
   - Prevents proxy/firewall timeouts
   - Helps detect disconnected clients

TECHNICAL CONSTRAINTS:

- SSE is HTTP/1.1 only (not WebSocket)
- Must handle client disconnects gracefully
- In-memory broadcaster sufficient for Epic 1 (single Flask process)
- For production: consider Redis pub/sub for multi-process support
- Event payload must be JSON-serializable
- Heartbeat interval: 30 seconds recommended

SSE EVENT FORMAT:

```
event: state_change
data: {"agent_id": "abc123", "old_state": "processing", "new_state": "idle"}

event: task_update
data: {"task_id": 42, "summary": "Created health check endpoint"}

: heartbeat
```

HTMX SSE SETUP (FRONTEND):

```html
<div hx-ext="sse" sse-connect="/api/events">
  <div sse-swap="state_change" hx-swap="innerHTML">
    <!-- Content updated on state_change events -->
  </div>
</div>
```

BROADCASTER FLOW:

1. Event occurs (e.g., task state change)
2. State machine calls broadcaster.broadcast('state_change', payload)
3. Broadcaster formats as SSE: event: state_change\ndata: {...}\n\n
4. Broadcaster sends to all connected clients
5. Clients receive and trigger HTMX updates

SSE ENDPOINT FLOW:

1. Client connects to /api/events
2. Server adds client to broadcaster's subscriber list
3. Server sends initial connection event (optional)
4. Server sends heartbeat every 30 seconds
5. On event: server sends formatted SSE message
6. On disconnect: server removes client from list

SUCCESS CRITERIA:

- SSE endpoint streams events to connected clients
- Multiple clients receive same events (broadcast works)
- Disconnected clients reconnect automatically
- Heartbeats keep connections alive (test with 5+ minute idle)
- No memory leaks from stale connections (test with 100+ clients)
- Event filtering works (if implemented)
- HTMX SSE integration triggers UI updates
- Browser shows real-time updates with <1 second latency

DELIVERABLES:

- src/routes/sse.py (SSE endpoint)
- src/services/broadcaster.py (event broadcaster)
- templates/base.html (HTMX SSE setup)
- static/js/sse.js (optional: custom reconnection logic)
- Test suite: integration test with mock clients
- Documentation: SSE event format, HTMX integration

OUTPUT LOCATION:
docs/prds/api/e1-s5-sse-system-prd.md

---

## Epic 1 Sprint 6: Dashboard UI

### Subsystem: dashboard-ui

**Prompt:**

Create a PRD for the dashboard UI implementation with Kanban layout and real-time updates.

CONTEXT:
Refer to @docs/application/claude_headspace_v3.1_conceptual_overview.md for the full dashboard concept.
Refer to @docs/application/claude_headspace_v3.1_epic1_guidance.md Section "UI Specification" for complete dashboard wireframes and design specs.
Refer to @docs/roadmap/claude_headspace_v3.1_epic1_detailed_roadmap.md Sprint 6 section for detailed requirements.

OBJECTIVE:
Build a fully functional dashboard matching the v2 design with Kanban-style agent cards and real-time SSE updates.

REQUIREMENTS:

1. HEADER BAR
   - Application title: "CLAUDE >\_headspace"
   - Navigation tabs: dashboard | objective | logging | config | help
   - Status counts: INPUT NEEDED (n) | WORKING (n) | IDLE (n)
   - Hooks/polling indicator: "HOOKS enabled" or "POLLING only"

2. RECOMMENDED NEXT PANEL
   - Highlights highest priority agent needing attention
   - Shows: session ID, state, task summary, priority score
   - Click to focus iTerm window (Sprint 10 integration)
   - Priority badge: [score] in top-right

3. SORT CONTROLS
   - Two sort modes: "By Project" | "By Priority"
   - Default: By Project
   - Toggle button or radio buttons
   - Client-side sorting (JavaScript)

4. PROJECT GROUPS (WHEN SORTED BY PROJECT)
   - Traffic light indicator: ● ● ● (red/yellow/green)
   - Project name
   - Active agent count
   - Collapsible waypoint section (future: edit inline)
   - Projects sorted alphabetically

5. AGENT CARDS
   - Layout: Terminal aesthetic with line numbers
   - Header line: status badge, session ID (truncated), polling indicator, uptime, "Headspace" button
   - State bar: colour-coded (idle=grey, commanded=yellow, processing=blue, awaiting_input=orange, complete=green)
   - Task summary: text preview (first 100 chars)
   - Priority score: [score] with explanation
   - Click card → focus iTerm window (Sprint 10)

6. AGENT CARD DETAIL FIELDS
   - Status: ACTIVE | IDLE
   - Session ID: truncated UUID (e.g., #2e3fe060)
   - Polling: ● POLL or ● HOOKS
   - Uptime: "up 32h 38m"
   - State bar: visual indicator with text
   - Task: summary text or "No active task"
   - Priority: [score] // explanation

7. COLOUR CODING
   - idle: Grey (#6B7280)
   - commanded: Yellow (#FBBF24)
   - processing: Blue (#3B82F6)
   - awaiting_input: Orange (#F97316)
   - complete: Green (#10B981)
   - Traffic lights: Red (#EF4444), Yellow (#FBBF24), Green (#10B981)

8. HTMX INTERACTIVITY
   - Click agent card → POST /api/focus/<agent_id>
   - Sort toggle → client-side reorder (JavaScript)
   - Collapse/expand project sections → local state (JavaScript)
   - SSE updates → swap content via hx-swap

9. SSE INTEGRATION
   - Subscribe to event stream on page load
   - Event types: state_change, task_update, agent_update
   - Swap strategy: innerHTML for agent cards, targeted swaps
   - Reconnect automatically on disconnect

10. TAILWIND CSS STYLING
    - Dark theme: background #1F2937, text #F9FAFB
    - Terminal aesthetic: monospace font, dark colours
    - Card styling: border, shadow, hover effects
    - Responsive layout: desktop and tablet

TECHNICAL CONSTRAINTS:

- Use Tailwind CSS for styling (no custom CSS if possible)
- HTMX for interactivity (no React/Vue)
- SSE for real-time updates
- Sort logic: client-side JavaScript
- Traffic light logic: based on agent states in project
  - Red: any agent in awaiting_input
  - Yellow: any agent in processing/commanded
  - Green: all agents idle
- Mobile responsiveness: basic support (Epic 1), full support (Epic 2)

DASHBOARD API ENDPOINTS:

- GET /api/dashboard → JSON: projects, agents, tasks, objective
- POST /api/focus/<agent_id> → focus iTerm window (Sprint 10)

TRAFFIC LIGHT LOGIC:

```python
def get_traffic_light(agents):
    if any(a.state == 'awaiting_input' for a in agents):
        return 'red'
    if any(a.state in ['processing', 'commanded'] for a in agents):
        return 'yellow'
    return 'green'
```

AGENT CARD HTML STRUCTURE (example):

```html
<div class="agent-card" data-agent-id="abc123">
  <div class="card-header">
    <span class="status">ACTIVE</span>
    <span class="session-id">#2e3fe060</span>
    <span class="poll-indicator">● POLL</span>
    <span class="uptime">up 32h 38m</span>
    <button class="focus-btn">Headspace</button>
  </div>
  <div class="state-bar state-processing">Processing...</div>
  <div class="task-summary">
    Creating health check endpoint with database connection test
  </div>
  <div class="priority">[60] // Default priority (no LLM result)</div>
</div>
```

SUCCESS CRITERIA:

- Dashboard displays all projects, agents, tasks
- Status counts accurate (INPUT NEEDED, WORKING, IDLE)
- Recommended next panel highlights highest priority agent
- Sort by project groups agents correctly
- Sort by priority orders agents by score
- Agent cards show: state, task summary, priority, uptime
- State bars colour-coded correctly
- Traffic light indicators reflect project status
- HTMX click events work (e.g., expand/collapse)
- SSE updates refresh dashboard in real-time (<1 second latency)
- Responsive layout works on desktop and tablet (basic)
- Dark theme aesthetic matches v2 design

DELIVERABLES:

- templates/dashboard.html (main template)
- templates/components/ (reusable card components)
- static/css/dashboard.css (Tailwind components if needed)
- static/js/dashboard.js (HTMX + sorting logic)
- src/routes/dashboard.py (API endpoints)
- Test suite: integration tests for API, UI smoke tests
- Documentation: component structure, SSE events

OUTPUT LOCATION:
docs/prds/ui/e1-s6-dashboard-ui-prd.md

---

## Epic 1 Sprint 7: Objective Tab

### Subsystem: objective-tab

**Prompt:**

Create a PRD for the objective tab with form, auto-save, and history display.

CONTEXT:
Refer to @docs/application/claude_headspace_v3.1_conceptual_overview.md Section 1 for objective concept and domain model.
Refer to @docs/application/claude_headspace_v3.1_epic1_guidance.md Section "UI Specification" for objective tab wireframe.
Refer to @docs/roadmap/claude_headspace_v3.1_epic1_detailed_roadmap.md Sprint 7 section for detailed requirements.

OBJECTIVE:
Implement objective setting with auto-save and history tracking.

REQUIREMENTS:

1. OBJECTIVE FORM
   - Text input: "What's your objective right now?"
   - Textarea: "Constraints (optional)"
   - Auto-save on change (debounced)
   - Placeholder text with examples
   - Character limit: 500 for objective, 1000 for constraints

2. AUTO-SAVE LOGIC
   - Debounce interval: 2-3 seconds after last keystroke
   - Save to Postgres: Objective table
   - Visual indicator: "Saving..." / "Saved" message
   - Error handling: show error if save fails

3. OBJECTIVE HISTORY DISPLAY
   - List previous objectives with timestamps
   - Format: "Set on [date/time]: [text]"
   - Show recent 10, paginate if more
   - Collapsible section: "Recent Objective History"

4. DATABASE STORAGE
   - Objective table: current_text, constraints, set_at
   - ObjectiveHistory table: text, constraints, started_at, ended_at
   - On new objective: move current to history (set ended_at), create new

5. API ENDPOINTS
   - GET /api/objective → current objective + recent history
   - POST /api/objective → save new objective

6. SHARED STATE
   - Multiple users see same objective (single instance)
   - Concurrent edits: last write wins (no conflict resolution in Epic 1)

TECHNICAL CONSTRAINTS:

- Auto-save debounce: 2-3 seconds recommended
- History limit: show recent 10, paginate if more (Epic 2)
- Character limits enforced client-side and server-side
- Objective is global singleton (not per-project in Epic 1)
- Database transaction: atomic update (current → history, new → current)

AUTO-SAVE FLOW:

1. User types in objective input
2. Debounce timer starts (reset on each keystroke)
3. After 2-3 seconds of inactivity, trigger save
4. POST /api/objective with { text, constraints }
5. Server: move current objective to history, save new objective
6. Response: success or error
7. Client: show "Saved" message or error

OBJECTIVE TAB LAYOUT (from guidance doc):

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        Current Objective                                │
│                                                                         │
│   Set your current headspace to help prioritize across projects.        │
│                                                                         │
│   ┌─────────────────────────────────────────────────────────────────┐   │
│   │ What's your objective right now?                                │   │
│   │                                                                 │   │
│   │ e.g., Ship the new feature before EOD                          │   │
│   └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│   ┌─────────────────────────────────────────────────────────────────┐   │
│   │ Constraints (optional)                                          │   │
│   │                                                                 │   │
│   │ e.g., Limited time, need to avoid breaking changes             │   │
│   └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│   Changes save automatically                                            │
│                                                                         │
│   ─────────────────────────────────────────────────────────────────     │
│                                                                         │
│   RECENT OBJECTIVE HISTORY                                              │
│                                                                         │
│   No objective history yet.                                             │
└─────────────────────────────────────────────────────────────────────────┘
```

SUCCESS CRITERIA:

- Can type objective text, auto-saves after debounce (2-3 seconds)
- Can add optional constraints
- Changes persist across page reloads
- Objective history shows previous objectives with timestamps
- API endpoints return correct data
- Multiple users see same objective (shared state)
- Save indicator shows "Saving..." then "Saved"
- Error handling: show message if save fails
- Character limits enforced (500/1000)

DELIVERABLES:

- templates/objective.html (objective tab template)
- static/js/objective.js (auto-save logic with debounce)
- src/routes/objective.py (API endpoints)
- Database migration: create ObjectiveHistory table if not exists
- Test suite: unit tests for API, integration test for auto-save
- Documentation: auto-save behavior, history display

OUTPUT LOCATION:
docs/prds/ui/e1-s7-objective-tab-prd.md

---

## Epic 1 Sprint 8: Logging Tab

### Subsystem: logging-tab

**Prompt:**

Create a PRD for the logging tab with event display and filtering.

CONTEXT:
Refer to @docs/application/claude_headspace_v3.1_conceptual_overview.md for event logging concept.
Refer to @docs/application/claude_headspace_v3.1_epic1_guidance.md Section "UI Specification" for logging tab requirements.
Refer to @docs/roadmap/claude_headspace_v3.1_epic1_detailed_roadmap.md Sprint 8 section for detailed requirements.

OBJECTIVE:
Display event log with filtering and real-time updates via SSE.

REQUIREMENTS:

1. EVENT LOG TABLE
   - Columns: Timestamp, Project, Agent, Event Type, Details
   - Format timestamp: relative (e.g., "2 minutes ago") and absolute on hover
   - Truncate details: show first 100 chars, expand inline on click
   - Color-code event types (optional)

2. FILTERS
   - Project: dropdown with all projects + "All Projects"
   - Agent: dropdown with all agents + "All Agents" (disabled if All Projects)
   - Event Type: dropdown with all types + "All Event Types"
   - Apply filters on change (no submit button)
   - Server-side filtering (query parameters)

3. REAL-TIME UPDATES VIA SSE
   - Subscribe to event stream on page load
   - New events appear at top of log automatically
   - SSE event type: event_log_update
   - Use HTMX sse-swap to prepend new events

4. PAGINATION
   - Show 100 events per page
   - "Load More" button at bottom
   - Server-side pagination: query param ?page=1
   - Disable pagination if filters applied (show all matching)

5. EVENT DETAIL EXPANSION
   - Initially show first 100 chars of details
   - Click event row → expand details inline
   - Show full payload JSON (formatted)
   - Toggle: expand/collapse

6. API ENDPOINT
   - GET /api/events
   - Query params: project_id, agent_id, event_type, page, limit
   - Response: { events: [...], total_count: n, page: 1 }

TECHNICAL CONSTRAINTS:

- Server-side filtering (not client-side)
- Pagination: 100 events per page recommended
- Real-time updates: prepend new events (not full reload)
- Event details: JSON payload formatted with indentation
- Performance: optimize query with indexes on timestamp, project_id, agent_id, event_type
- Handle large logs: test with 10,000+ events

EVENT LOG TABLE LAYOUT:

```
┌───────────────────────────────────────────────────────────────────────────┐
│ LOGGING                                                                   │
├───────────────────────────────────────────────────────────────────────────┤
│ Filters:  [All Projects ▼] [All Agents ▼] [All Event Types ▼]            │
├───────────────────────────────────────────────────────────────────────────┤
│ Timestamp          │ Project        │ Agent    │ Event Type     │ Details │
├───────────────────────────────────────────────────────────────────────────┤
│ 2 min ago          │ claude_headspace│ #2e3fe   │ turn_detected  │ User... │
│ 5 min ago          │ raglue         │ #abc123  │ state_transition│ idle...│
│ ...                │ ...            │ ...      │ ...            │ ...     │
└───────────────────────────────────────────────────────────────────────────┘
│                          [Load More]                                      │
└───────────────────────────────────────────────────────────────────────────┘
```

FILTER QUERY LOGIC:

```python
def get_events(project_id=None, agent_id=None, event_type=None, page=1, limit=100):
    query = Event.query
    if project_id:
        query = query.filter_by(project_id=project_id)
    if agent_id:
        query = query.filter_by(agent_id=agent_id)
    if event_type:
        query = query.filter_by(event_type=event_type)

    total = query.count()
    events = query.order_by(Event.timestamp.desc()).offset((page-1)*limit).limit(limit).all()
    return events, total
```

SSE INTEGRATION:

```html
<div hx-ext="sse" sse-connect="/api/events-stream">
  <div id="event-log" sse-swap="event_log_update" hx-swap="afterbegin">
    <!-- New events prepended here -->
  </div>
</div>
```

SUCCESS CRITERIA:

- Event log displays all events with columns: timestamp, project, agent, event type, details
- Can filter by project, agent, event type
- Filters apply correctly (matching events shown)
- New events appear automatically via SSE (prepended to top)
- Pagination works (can navigate pages)
- Event details expandable inline (show full JSON payload)
- Performance acceptable with 10,000+ events (query time <500ms)
- Relative timestamps update dynamically (e.g., "2 min ago" → "3 min ago")
- No full page reload on filter change (use HTMX)

DELIVERABLES:

- templates/logging.html (logging tab template)
- static/js/logging.js (filter logic, timestamp updates, expand/collapse)
- src/routes/logging.py (API endpoint with filtering)
- Database indexes on Event table (timestamp, project_id, agent_id, event_type)
- Test suite: integration test for filtering, performance test with 10k events
- Documentation: filter logic, SSE integration

OUTPUT LOCATION:
docs/prds/ui/e1-s8-logging-tab-prd.md

---

## Epic 1 Sprint 9: Launcher Script

### Subsystem: launcher-script

**Prompt:**

Create a PRD for the CLI launcher script to start monitored Claude Code sessions.

CONTEXT:
Refer to @docs/application/claude_headspace_v3.1_conceptual_overview.md Section 2 for iTerm2 integration and session monitoring.
Refer to @docs/application/claude_headspace_v3.1_epic1_guidance.md Section "Launcher Script" for requirements.
Refer to @docs/roadmap/claude_headspace_v3.1_epic1_detailed_roadmap.md Sprint 9 section for detailed requirements.

OBJECTIVE:
Build a CLI tool to launch Claude Code sessions with registration to Claude Headspace.

REQUIREMENTS:

1. CLI TOOL: claude-headspace
   - Subcommand: start
   - Usage: cd /path/to/project && claude-headspace start
   - Options:
     - --project-name (optional, auto-detect from pwd)
     - --session-uuid (optional, auto-generate if not provided)

2. SESSION UUID GENERATION
   - Use UUID4 format
   - Store in environment variable: CLAUDE_SESSION_UUID
   - Pass to Claude Code via environment

3. PROJECT DETECTION
   - Detect project from current working directory (pwd)
   - Validate: directory exists and is a git repo (optional check)
   - Extract project name from directory name or git remote

4. ITERM2 PANE ID CAPTURE
   - Use AppleScript to get current iTerm2 pane ID
   - AppleScript: `tell application "iTerm" to id of current session of current window`
   - Store pane ID for later focus (Sprint 10)

5. SESSION REGISTRATION
   - HTTP POST to /api/register-session
   - Payload: { session_uuid, project_path, iterm_pane_id }
   - Response: success or error
   - Retry logic: 3 attempts with 1s delay

6. ENVIRONMENT VARIABLE SETUP
   - Set CLAUDE_HEADSPACE_URL (default: http://localhost:5000)
   - Set CLAUDE_SESSION_UUID
   - Pass to Claude Code session

7. LAUNCH CLAUDE CLI
   - Execute: claude
   - Inherit environment variables
   - Interactive mode (not detached)

8. CLEANUP ON EXIT
   - Trap EXIT signal
   - HTTP POST to /api/unregister-session
   - Payload: { session_uuid }
   - Mark session as inactive in database

TECHNICAL CONSTRAINTS:

- Script language: Python (use argparse for CLI) or Bash
- Recommend Python for cross-platform portability
- iTerm2 pane ID capture: requires iTerm2 (not other terminals in Epic 1)
- Session registration: requires Claude Headspace server running
- Error handling: show clear error messages, exit codes
- Registration failure: warn but proceed (graceful degradation)

CLI USAGE EXAMPLE:

```bash
cd ~/dev/my-project
claude-headspace start
# Launches Claude Code with monitoring enabled
```

SESSION REGISTRATION FLOW:

1. User runs `claude-headspace start` in project directory
2. Script detects project path from pwd
3. Script generates session UUID
4. Script captures iTerm2 pane ID via AppleScript
5. Script POSTs to /api/register-session
6. Server creates Agent record
7. Script sets environment variables
8. Script launches `claude` CLI
9. User exits Claude Code
10. Cleanup: script POSTs to /api/unregister-session
11. Server marks Agent as inactive

API ENDPOINTS:

- POST /api/register-session
  - Body: { session_uuid, project_path, iterm_pane_id }
  - Response: { success: true, agent_id: "..." }
- POST /api/unregister-session
  - Body: { session_uuid }
  - Response: { success: true }

APPLESCRIPT EXAMPLE (iTerm pane ID):

```applescript
tell application "iTerm"
    tell current session of current window
        return id
    end tell
end tell
```

SUCCESS CRITERIA:

- `claude-headspace start` launches Claude Code successfully
- Session UUID generated and stored
- Project detected correctly from pwd
- iTerm pane ID captured
- Session registered with Claude Headspace (visible in dashboard)
- Environment variables set correctly
- Claude Code session inherits environment
- Session marked inactive on exit
- Error handling shows clear messages (e.g., "Server not running", "Not in iTerm2")
- Graceful degradation: if registration fails, warn but proceed with Claude Code launch

DELIVERABLES:

- bin/claude-headspace (CLI script)
- src/services/session_registration.py (API for registration endpoints)
- src/routes/session.py (session registration routes)
- Installation instructions (add to PATH)
- Test suite: integration test (mock server, test registration flow)
- Documentation: CLI usage, environment variables

OUTPUT LOCATION:
docs/prds/scripts/e1-s9-launcher-script-prd.md

---

## Epic 1 Sprint 10: AppleScript Integration

### Subsystem: applescript-integration

**Prompt:**

Create a PRD for macOS AppleScript integration to focus iTerm2 windows and send system notifications.

CONTEXT:
Refer to @docs/application/claude_headspace_v3.1_conceptual_overview.md Section 2 for macOS integration requirements.
Refer to @docs/application/claude_headspace_v3.1_epic1_guidance.md Section "macOS Integration (AppleScript)" for detailed specs.
Refer to @docs/roadmap/claude_headspace_v3.1_epic1_detailed_roadmap.md Sprint 10 section for detailed requirements.

OBJECTIVE:
Enable click-to-focus for iTerm2 windows from dashboard and send macOS system notifications.

REQUIREMENTS:

1. APPLESCRIPT TO FOCUS ITERM2 PANE
   - Input: iTerm2 pane ID (from Agent record)
   - AppleScript command: activate iTerm, focus pane by ID
   - Error handling: pane not found, iTerm not running, permission denied

2. API ENDPOINT
   - POST /api/focus/<agent_id>
   - Lookup Agent by agent_id
   - Extract iterm_pane_id
   - Execute AppleScript
   - Response: success or error

3. DASHBOARD INTEGRATION
   - Wire up agent card click → POST /api/focus/<agent_id>
   - Use HTMX: hx-post="/api/focus/<agent_id>" hx-trigger="click"
   - Visual feedback: button hover effect, loading spinner (optional)

4. PERMISSION ERROR HANDLING
   - Detect macOS privacy controls blocking AppleScript
   - Error message: "Grant automation permission in System Preferences → Privacy & Security → Automation"
   - Link to instructions (optional)

5. FALLBACK BEHAVIOR
   - If focus fails: show session path in modal or message
   - User can manually switch to session

6. TERMINAL DETECTION
   - Epic 1: iTerm2 only
   - Future: detect WezTerm, Terminal.app, etc.

7. SYSTEM NOTIFICATIONS
   - Trigger on events: task_completed, awaiting_input
   - Notification format: "Agent #abc123 completed task" or "Agent #abc123 needs input"
   - Use osascript with display notification
   - Notification action: click to focus iTerm window (optional)

TECHNICAL CONSTRAINTS:

- iTerm2 required (not other terminals in Epic 1)
- macOS only (Linux/Windows not supported)
- AppleScript execution: use Python subprocess to run osascript
- Permission check: detect "not authorized" error, show actionable message
- Focus latency: target <500ms

APPLESCRIPT FOCUS COMMAND:

```applescript
tell application "iTerm"
    activate
    tell current window
        tell session id "{pane_id}"
            select
        end tell
    end tell
end tell
```

PYTHON EXECUTION:

```python
import subprocess

def focus_iterm_pane(pane_id):
    script = f'''
    tell application "iTerm"
        activate
        tell current window
            tell session id "{pane_id}"
                select
            end tell
        end tell
    end tell
    '''
    try:
        subprocess.run(['osascript', '-e', script], check=True, capture_output=True)
        return True
    except subprocess.CalledProcessError as e:
        if 'not authorized' in e.stderr.decode():
            raise PermissionError('AppleScript automation not authorized')
        raise
```

SYSTEM NOTIFICATION COMMAND:

```applescript
display notification "Agent #abc123 completed task" with title "Claude Headspace"
```

API ENDPOINT FLOW:

1. Client clicks agent card
2. HTMX POSTs to /api/focus/<agent_id>
3. Server looks up Agent by agent_id
4. Server extracts iterm_pane_id
5. Server executes AppleScript to focus pane
6. Server returns success or error
7. Client shows feedback (success: no UI change, error: show message)

SUCCESS CRITERIA:

- Click agent card → iTerm window focuses
- Correct pane activated (not just iTerm window)
- Permission errors detected, actionable message shown
- Fallback shows session path if focus fails
- Works on macOS Monterey, Ventura, Sonoma
- Focus latency <500ms
- System notifications triggered on task_completed and awaiting_input events
- Notification format clear and actionable
- Notifications appear in macOS notification center

DELIVERABLES:

- src/services/iterm_focus.py (AppleScript wrapper)
- src/services/macos_notifications.py (notification wrapper)
- src/routes/focus.py (API endpoint)
- static/js/dashboard.js (click handler wiring)
- Permission setup documentation (System Preferences steps)
- Test suite: integration test (mock AppleScript execution)
- Documentation: iTerm2 setup, permission requirements

OUTPUT LOCATION:
docs/prds/scripts/e1-s10-applescript-integration-prd.md

---

## Epic 1 Sprint 11: Claude Code Hooks Integration

### Subsystem: hook-receiver

**Prompt:**

Create a PRD for the Claude Code hooks integration system for event-driven state updates.

CONTEXT:
Refer to @docs/architecture/claude-code-hooks.md for complete hook architecture, event flow, and technical specifications.
Refer to @docs/application/claude_headspace_v3.1_conceptual_overview.md for state machine and domain model.
Refer to @docs/roadmap/claude_headspace_v3.1_epic1_detailed_roadmap.md Sprint 11 section for comprehensive requirements.

OBJECTIVE:
Receive lifecycle events directly from Claude Code via hooks for instant, high-confidence state updates (<100ms latency vs ~2s polling).

REQUIREMENTS:

1. HOOK RECEIVER SERVICE (src/services/hook_receiver.py)
   - process_event(event_type, payload): Main entry point for hook events
   - correlate_session(claude_session_id, cwd): Match Claude session ID to agent via working directory
   - map_event_to_state(event_type, current_state): Map hook events to state transitions
   - Integration with state machine and event bus

2. HOOK API ROUTES (src/routes/hooks.py)
   - POST /hook/session-start → Create agent if not exists, set IDLE
   - POST /hook/session-end → Mark agent inactive
   - POST /hook/stop → Primary completion signal: PROCESSING → IDLE
   - POST /hook/notification → Timestamp update only (no state change)
   - POST /hook/user-prompt-submit → IDLE → PROCESSING
   - GET /hook/status → Hook receiver status, last event times

3. HOOK CONFIGURATION (src/models/config.py)
   - HookConfig model with fields:
     - enabled: bool (default True)
     - port: int | None (None = use main Flask port)
     - fallback_polling: bool (default True)
     - polling_interval_with_hooks: int (60 seconds)
     - session_timeout: int (300 seconds)

4. SESSION CORRELATION
   - Map Claude $CLAUDE_SESSION_ID to agents via working directory matching
   - Cache correlations for performance (in-memory dict)
   - Handle mismatches: Claude session ≠ terminal pane ID
   - Create new agent if session not found

5. HOOK NOTIFICATION SCRIPT (bin/notify-headspace.sh)
   - Bash script that POSTs to hook endpoints
   - Uses Claude env vars: $CLAUDE_SESSION_ID, $CLAUDE_WORKING_DIRECTORY
   - Timeout: 1s connect timeout, 2s max time
   - Silent failures: exit 0 even if curl fails (don't block Claude Code)

6. CLAUDE CODE SETTINGS TEMPLATE (docs/claude-code-hooks-settings.json)
   - JSON for ~/.claude/settings.json with all hook configurations
   - Absolute paths required (not ~ or $HOME)
   - All 5 hooks: session-start, session-end, stop, notification, user-prompt-submit

7. INSTALLATION SCRIPT (bin/install-hooks.sh)
   - Copy notify-headspace.sh to ~/.claude/hooks/
   - Merge settings template into ~/.claude/settings.json
   - Set executable permissions (chmod +x)
   - Validate paths are absolute
   - Backup existing settings before merge

8. HOOK STATUS DASHBOARD UI
   - Badge: "Hooks: enabled" vs "Polling only"
   - Last hook event time per agent
   - Fallback indicator when polling takes over (>300s silence)

9. HYBRID MODE LOGIC
   - Hooks primary, polling secondary
   - Polling interval: 60s when hooks active, 2s when hooks silent >300s
   - Reconciliation: polling catches missed hook events
   - Deduplication: same event from hooks and polling handled once

10. GRACEFUL DEGRADATION
    - Hooks not installed → polling works normally
    - Hook endpoint down → events logged, polling continues
    - Hook script fails → Claude Code session unaffected

TECHNICAL CONSTRAINTS:

- Hook authentication: none (local only, trust localhost) — Epic 1, add in Epic 2
- Session correlation: working directory matching (Claude session ID ≠ terminal pane ID)
- Hybrid mode polling: 60s when hooks active, 2s fallback after 300s silence
- Hook timeout: 1s connect, 2s max time (don't block Claude Code)
- Error handling: silent failures in hook script (exit 0 always)
- Confidence level: hooks = 1.0, polling = 0.8

HOOK EVENT TO STATE MAPPING:
| Hook Event | Current State | New State | Confidence |
|--------------------|---------------|------------|------------|
| SessionStart | - | IDLE | 1.0 |
| UserPromptSubmit | IDLE | PROCESSING | 1.0 |
| Stop | PROCESSING | IDLE | 1.0 |
| Notification | any | (no change)| - |
| SessionEnd | any | ENDED | 1.0 |

HYBRID MODE LOGIC:

```python
def get_polling_interval(agent):
    if agent.last_hook_event_at:
        seconds_since = (now() - agent.last_hook_event_at).total_seconds()
        if seconds_since > 300:  # 5 minutes
            return 2  # fallback to fast polling
        return 60  # hooks active, slow polling
    return 2  # no hooks, fast polling
```

SESSION CORRELATION LOGIC:

```python
def correlate_session(claude_session_id, cwd):
    # 1. Check cache
    if claude_session_id in correlation_cache:
        return correlation_cache[claude_session_id]

    # 2. Match by working directory
    for agent in agents:
        if agent.project.path == cwd:
            correlation_cache[claude_session_id] = agent
            return agent

    # 3. Create new agent
    project = Project.get_or_create(path=cwd)
    agent = Agent.create(project=project, claude_session_id=claude_session_id)
    correlation_cache[claude_session_id] = agent
    return agent
```

HOOK NOTIFICATION SCRIPT (bin/notify-headspace.sh):

```bash
#!/bin/bash
EVENT_TYPE=$1
CLAUDE_SESSION_ID=${CLAUDE_SESSION_ID:-"unknown"}
CLAUDE_WORKING_DIRECTORY=${CLAUDE_WORKING_DIRECTORY:-$(pwd)}

curl --connect-timeout 1 --max-time 2 -s -X POST \
  http://localhost:5000/hook/$EVENT_TYPE \
  -H "Content-Type: application/json" \
  -d "{\"session_id\":\"$CLAUDE_SESSION_ID\",\"cwd\":\"$CLAUDE_WORKING_DIRECTORY\"}" \
  2>/dev/null

exit 0  # always exit successfully
```

CLAUDE CODE SETTINGS TEMPLATE (docs/claude-code-hooks-settings.json):

```json
{
  "hooks": {
    "session-start": "/absolute/path/to/notify-headspace.sh session-start",
    "session-end": "/absolute/path/to/notify-headspace.sh session-end",
    "stop": "/absolute/path/to/notify-headspace.sh stop",
    "notification": "/absolute/path/to/notify-headspace.sh notification",
    "user-prompt-submit": "/absolute/path/to/notify-headspace.sh user-prompt-submit"
  }
}
```

EVENT FLOW:

```
Claude Code → Hook Script → HTTP POST → HookReceiver.process_event()
                                                     ↓
                                         correlate_session()
                                                     ↓
                                         map_event_to_state()
                                                     ↓
                                         StateMachine.transition()
                                                     ↓
                                         EventBus.broadcast()
                                                     ↓
                                         SSE → Dashboard Update
```

SUCCESS CRITERIA:

- HookReceiver service processes all hook events correctly
- Hook endpoints receive events from Claude Code
- Hook events update Agent/Task/Turn state with confidence=1.0
- State updates faster than polling (<100ms vs ~2 seconds)
- Hook status dashboard shows "Hooks: enabled" and last event times
- Graceful degradation: hooks silent >300s → revert to 2s polling
- Session correlation matches Claude sessions to agents via working directory
- Hybrid mode polling adjusts interval based on hook activity (60s with hooks, 2s without)
- Installation script works on clean macOS setup:
  - ~/.claude/hooks/notify-headspace.sh created and executable
  - ~/.claude/settings.json updated with hook configuration
  - Absolute paths used (not ~ or $HOME)
- Hook script handles timeouts and failures gracefully (silent failures, exit 0)
- Documentation clear and complete (setup instructions, troubleshooting)
- End-to-end test: start Claude Code → hooks fire → state transitions → polling adjusts

DELIVERABLES:

- src/services/hook_receiver.py (core service)
- src/routes/hooks.py (API endpoints)
- src/models/config.py (HookConfig model)
- bin/notify-headspace.sh (hook script)
- bin/install-hooks.sh (installation script)
- docs/claude-code-hooks-settings.json (settings template)
- docs/hooks-setup.md (setup guide and troubleshooting)
- templates/dashboard.html (add hook status badge)
- Test suite: unit tests for correlation, integration test for hook flow
- Documentation: architecture, event flow, setup instructions

OUTPUT LOCATION:
docs/prds/events/e1-s11-hook-receiver-prd.md

---

## Summary

These 11 prompts cover all sprints in Epic 1. Each prompt:

- References the appropriate design documents (@docs/application/, @docs/architecture/, @docs/roadmap/)
- Provides complete context for the PRD workshop
- Includes detailed requirements, constraints, and success criteria
- Specifies deliverables and output location
- Is ready to use with `/10: prd-workshop`

**Usage Pattern:**

1. Copy the prompt for the sprint
2. Run `/10: prd-workshop`
3. Paste the prompt
4. Review generated PRD
5. Add to queue: `/10: queue-add`
6. Process: `/20: prd-orchestrate`

**Sprint Order:**
Follow the dependency graph from the detailed roadmap:

- Phase 1: Sprints 1-2 (Foundation)
- Phase 2: Sprints 3-5 (Event System + State Machine + SSE)
- Phase 3: Sprints 6-8 (UI Features)
- Phase 4: Sprints 9-11 (Integration)

---

**End of Epic 1 Sprint Prompts**
