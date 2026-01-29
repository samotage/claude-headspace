# Claude Headspace v3.1 - Epic 1: Core Foundation

**Date:** 28.1.26  
**Epic Goal:** Establish the foundational event-driven architecture and prove the Task/Turn state machine works with a functional dashboard.

**Acceptance Test:** Launch 2-3 iTerm2 sessions with Claude Code, issue commands in each, and watch the dashboard reflect correct Task/Turn states in real-time. Click agent cards to focus the correct iTerm window. Receive system notifications when tasks complete or input is needed.

---

## Reference Documents

- `claude_headspace_v3.1_conceptual_overview.md` - Full conceptual design with terminology, state model, and domain model

---

## Tech Stack

| Component | Choice | Notes |
|-----------|--------|-------|
| Language | Python | Fresh start, no v2 code |
| Web Framework | Flask | |
| Database | Postgres | Local installation, not Docker |
| CSS | Tailwind | Model knows it well |
| Interactivity | HTMX | Proven in v1 for SSE |
| Real-time | SSE | Server-Sent Events via HTMX |
| File Watching | watchdog | Watch `~/.claude/projects/` |
| macOS Integration | AppleScript | iTerm focus, system notifications |
| Config | YAML | `config.yaml` file |

---

## Architecture Principles

### Event-Driven Design

Logs are events. Events drive the application.

```
Claude Code jsonl files
        │
        ▼
    [Event]
        │
        ├──▶ Writes to Postgres (event log)
        ├──▶ Updates Task state
        ├──▶ Updates Turn records
        ├──▶ Triggers SSE push to UI
        └──▶ Triggers system notification (if applicable)
```

### Data Storage Separation

```
Application Domain (Postgres)          LLM Domain (text files)
──────────────────────────────        ─────────────────────────
Event log                              config.yaml
Task records                           waypoint.md (in target project)
Turn records                           progress_summary.md (in target project)
Objective + history                    brain_reboot outputs
Agent/Session state
InferenceCall logs (future)
```

**Rules:**
- Application logic reads/writes Postgres (deterministic, queryable)
- LLM reads/writes text files in defined locations
- LLM does NOT touch event log or state machine
- Clear boundary between domains

### Auto-Discovery

The application discovers everything from the filesystem - minimal manual configuration.

**Project Discovery:**
```
~/.claude/projects/
├── -Users-samotage-dev-otagelabs-claude-headspace/
│   └── {session-uuid}.jsonl
├── -Users-samotage-dev-otagelabs-raglue/
│   └── {session-uuid}.jsonl
└── ...
```

- Folder name encodes project path (`-` replaces `/`)
- jsonl files are session logs (one per Claude Code session = one agent)
- Project metadata derived from project path via git

**Project Self-Description (from project path):**

| Attribute | Source |
|-----------|--------|
| path | Derived from folder name |
| name | Derived from path or git remote |
| github_repo | `git remote get-url origin` |
| current_branch | `git branch --show-current` |
| recent_commits | `git log` |
| waypoint | `docs/brain_reboot/waypoint.md` |
| progress_summary | `docs/brain_reboot/progress_summary.md` |

---

## UI Specification

### Navigation Tabs

| Tab | Epic 1 | Purpose |
|-----|--------|---------|
| dashboard | ✅ | Kanban view of projects/agents/tasks |
| objective | ✅ | Set current objective + view history |
| logging | ✅ | View event logs |
| config | ❌ Epic 2 | UI for settings |
| help | ❌ Later | Documentation |

### Visual Design

Dark terminal aesthetic (preserve v2 look and feel).

### Dashboard Tab

**Header Bar:**
```
┌─────────────────────────────────────────────────────────────────────────┐
│ CLAUDE >_headspace   > dashboard  objective  logging  config  help      │
├─────────────────────────────────────────────────────────────────────────┤
│ INPUT NEEDED 0    WORKING 2    IDLE 7    HOOKS polling                  │
└─────────────────────────────────────────────────────────────────────────┘
```

- Status counts derived from agent states
- Navigation tabs
- Hooks/polling status indicator

**Recommended Next Panel:**
```
┌─────────────────────────────────────────────────────────────────────────┐
│ ★ RECOMMENDED NEXT                                            [60]      │
│                                                                         │
│ #98a62ee2  Unknown  [idle]                                              │
│ "Default priority (no LLM result)"                                      │
│ Click to focus iTerm window                                             │
└─────────────────────────────────────────────────────────────────────────┘
```

- Highlights highest priority agent needing attention
- Click to focus iTerm window
- Priority score badge

**Sort Controls:**
```
SORT:  [By Project]  [By Priority]
```

**Project Group:**
```
┌─────────────────────────────────────────────────────────────────────────┐
│ ● ● ●  project-name                                        9 active     │
├─────────────────────────────────────────────────────────────────────────┤
│ ▶ Waypoint                                                    [Edit]    │
└─────────────────────────────────────────────────────────────────────────┘
```

- Traffic light indicator (red/yellow/green based on state)
- Project name
- Active agent count
- Collapsible waypoint section

**Agent Card:**
```
┌─────────────────────────────────────────────────────────────────────────┐
│ 01  ● ACTIVE  #2e3fe060  ● POLL  up 32h 38m              [Headspace]    │
│ 02                                                                      │
│ 03  ┌─────────────────────────────────────────────────────────────────┐ │
│ 04  │ ✓ Task complete                                                 │ │
│ 05  └─────────────────────────────────────────────────────────────────┘ │
│     ✓ Task completed                                                    │
│     [60] // Default priority (no LLM result)                            │
└─────────────────────────────────────────────────────────────────────────┘
```

- Line numbers (terminal aesthetic)
- Status badge (ACTIVE/IDLE)
- Session ID (truncated UUID)
- Polling indicator
- Uptime
- "Headspace" button → focus iTerm window
- Current state bar (colour-coded)
- Task summary
- Priority score

**Agent States & Colours:**

| State | Colour | Display |
|-------|--------|---------|
| idle | Grey | "Idle - ready for task" |
| commanded | Yellow | "Command received" |
| processing | Blue | "Processing..." |
| awaiting_input | Orange | "Input needed" |
| complete | Green | "Task complete" |

### Objective Tab

```
┌─────────────────────────────────────────────────────────────────────────┐
│                                                                         │
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
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### Logging Tab

- Filterable event log
- Filter by: Project, Agent, Task, Event type
- Columns: Timestamp, Project, Agent, Event, Details
- Real-time updates via SSE

---

## Domain Model (Epic 1 Subset)

```
Objective
├── current_text
├── constraints (optional)
├── set_at: timestamp
└── history[]
    ├── text
    ├── constraints
    ├── started_at
    └── ended_at

Project (auto-discovered)
├── path
├── name
├── github_repo
├── current_branch
└── agents[]

Agent (auto-discovered from jsonl files)
├── session_uuid
├── project_id
├── iterm_pane_id (for AppleScript focus)
├── started_at
├── state (derived from current task)
└── tasks[]

Task
├── agent_id
├── state: idle | commanded | processing | awaiting_input | complete
├── started_at
├── completed_at
└── turns[]

Turn
├── task_id
├── actor: user | agent
├── text
├── intent: command | answer | question | completion | progress
└── timestamp

Event (log)
├── id
├── timestamp
├── project_id
├── agent_id
├── task_id (nullable)
├── turn_id (nullable)
├── event_type
└── payload (JSON)
```

---

## Launcher Script

A CLI tool to launch Claude Code sessions with registration to the application.

**Usage:**
```bash
cd /path/to/project
claude-headspace start
```

**Responsibilities:**
- Generate session UUID
- Detect project from current working directory
- Capture iTerm2 pane ID (for later AppleScript focus)
- Register session with Claude Headspace application
- Set environment variable for Claude Code hooks
- Launch `claude` CLI
- Notify application when session ends

**Reference:** See existing `dev-monitor` script from v2 for patterns.

---

## macOS Integration (AppleScript)

### Focus iTerm Window

When user clicks agent card or "Headspace" button:
- AppleScript activates iTerm2
- Focuses the specific pane/tab for that session

### System Notifications

Triggered on events:
- Task complete → "Agent #abc123 completed task"
- Input needed → "Agent #abc123 needs input"

Notifications appear in system tray, work across all workspaces.

---

## Config.yaml Structure

```yaml
# Database
database:
  host: localhost
  port: 5432
  name: claude_headspace
  user: postgres
  password: ""

# Claude integration
claude:
  projects_path: ~/.claude/projects

# Server
server:
  host: 127.0.0.1
  port: 5000

# Future (Epic 2+)
# openrouter:
#   api_key: sk-or-v1-...
#   model: anthropic/claude-3-haiku
#   compression_interval: 300
#
# notifications:
#   enabled: true
#
# session_summarization:
#   idle_timeout: 60
#
# brain_reboot:
#   stale_threshold: 4
```

---

## Sprint Breakdown

### Sprint 1: Project Bootstrap

**Goal:** Runnable Flask application with database connection.

- Python project structure (pyproject.toml, src layout)
- Flask application factory
- Postgres connection via config.yaml
- Database migrations setup (Alembic or Flask-Migrate)
- Basic health check endpoint
- Tailwind CSS build pipeline
- Base HTML template with dark theme

**Deliverable:** `flask run` starts server, connects to Postgres, serves styled page.

---

### Sprint 2: Domain Models & Database Schema

**Goal:** Database schema for core domain model.

- Objective model (with history)
- Project model
- Agent model
- Task model (with state machine)
- Turn model
- Event log model
- Database migrations

**Deliverable:** Models created, migrations run, can create/query records.

---

### Sprint 3: File Watcher & Event System

**Goal:** Watch Claude Code jsonl files and emit events.

- Watchdog setup to monitor `~/.claude/projects/`
- Parse jsonl file format
- Detect new sessions (new jsonl files)
- Detect new turns (jsonl file changes)
- Write events to Postgres
- Auto-discover projects from folder structure
- Extract project metadata from git

**Deliverable:** Start app, start Claude Code session, see events logged to database.

---

### Sprint 4: Task/Turn State Machine

**Goal:** Events correctly update Task and Turn state.

- Implement Task state transitions
- Map Turn intents to Task state changes
- Task lifecycle (command → ... → completion)
- Agent state derived from current task
- Unit tests for state machine

**Deliverable:** Events flow through, Task/Turn records reflect correct state.

---

### Sprint 5: SSE & Real-time Updates

**Goal:** Push updates to browser in real-time.

- SSE endpoint in Flask
- HTMX SSE integration
- Broadcast events to connected clients
- Reconnection handling

**Deliverable:** Browser receives real-time updates when events occur.

---

### Sprint 6: Dashboard UI

**Goal:** Functional dashboard matching v2 design.

- Header bar with status counts
- Recommended next panel
- Sort controls (by project, by priority)
- Project groups with traffic light indicators
- Agent cards with full detail
- Colour-coded state bars
- HTMX for interactivity
- SSE for real-time updates

**Deliverable:** Dashboard displays live state of all agents/tasks.

---

### Sprint 7: Objective Tab

**Goal:** Set and view objective with history.

- Objective form (text + constraints)
- Auto-save on change
- Objective history display
- Store in Postgres

**Deliverable:** Can set objective, see history, persists across restarts.

---

### Sprint 8: Logging Tab

**Goal:** Viewable event log with filtering.

- Event log display
- Filters: Project, Agent, Task, Event type
- Real-time updates via SSE
- Pagination or virtual scroll for large logs

**Deliverable:** Can view and filter all events.

---

### Sprint 9: Launcher Script

**Goal:** CLI tool to launch monitored Claude Code sessions.

- `claude-headspace start` command
- Session UUID generation
- Project detection from cwd
- iTerm2 pane ID capture
- Register session with application (HTTP or file-based)
- Environment variable for hooks
- Launch claude CLI
- Cleanup on exit

**Deliverable:** Launch sessions via script, they appear in dashboard.

---

### Sprint 10: AppleScript Integration

**Goal:** macOS integration for iTerm focus and notifications.

- AppleScript to focus iTerm2 pane by ID
- Wire up agent card click → focus iTerm
- AppleScript for system notifications
- Trigger notifications on task complete / input needed

**Deliverable:** Click agent card → iTerm focuses. Task events → system notification.

---

## Out of Scope (Future Epics)

- Inference calls (summarisation, prioritisation)
- Brain reboot / waypoint / progress_summary generation
- Config UI tab
- Help tab / documentation
- Priority scoring (beyond default)
- Hooks integration with Claude Code

---

## Acceptance Criteria for Epic 1

1. ✅ Application starts via `flask run` or similar
2. ✅ Connects to local Postgres
3. ✅ Reads config from `config.yaml`
4. ✅ Auto-discovers projects from `~/.claude/projects/`
5. ✅ Watches jsonl files for changes
6. ✅ Events logged to Postgres
7. ✅ Task/Turn state machine works correctly
8. ✅ Dashboard shows projects, agents, tasks in Kanban layout
9. ✅ Dashboard updates in real-time via SSE
10. ✅ Can set objective and view history
11. ✅ Can view and filter event logs
12. ✅ Launcher script starts monitored sessions
13. ✅ Click agent card focuses correct iTerm window
14. ✅ System notifications on task complete / input needed
