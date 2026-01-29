# Epic 1 Sprint Prompts for PRD Workshop

**Epic:** Epic 1 — Core Foundation + Event-Driven Hooks  
**Reference:** [`docs/roadmap/claude_headspace_v3.1_epic1_detailed_roadmap.md`](../roadmap/claude_headspace_v3.1_epic1_detailed_roadmap.md)

---

## Context Documents

| Document                                                                          | Purpose                                           |
| --------------------------------------------------------------------------------- | ------------------------------------------------- |
| [Conceptual Overview](../conceptual/claude_headspace_v3.1_conceptual_overview.md) | Core concepts, domain model, 5-state task model   |
| [Epic 1 Guidance](../conceptual/claude_headspace_v3.1_epic1_guidance.md)          | Implementation guidance, patterns, decisions      |
| [Claude Code Hooks Architecture](../architecture/claude-code-hooks.md)            | Hook integration, event flow, session correlation |
| [Overarching Roadmap](../roadmap/claude_headspace_v3.1_overarching_roadmap.md)    | Epic structure, project goals, success criteria   |

---

## Sprint Prompts

### Sprint 1: Flask Bootstrap

**PRD:** `docs/prds/flask/e1-s1-flask-bootstrap-prd.md`

> Create a PRD for the Flask bootstrap subsystem. Reference Sprint 1 in the [Epic 1 Detailed Roadmap](../roadmap/claude_headspace_v3.1_epic1_detailed_roadmap.md#sprint-1-flask-bootstrap). Include Flask application factory, config loading from `config.yaml`, environment variable overrides, health check endpoint, error handlers, logging, and Tailwind CSS build pipeline with dark terminal aesthetic.

---

### Sprint 2: Database Setup

**PRD:** `docs/prds/core/e1-s2-database-setup-prd.md`

> Create a PRD for the database setup subsystem. Reference Sprint 2 in the [Epic 1 Detailed Roadmap](../roadmap/claude_headspace_v3.1_epic1_detailed_roadmap.md#sprint-2-database-setup). Include Postgres connection, SQLAlchemy integration, Flask-Migrate, migration commands, connection pooling, and config.yaml schema for database settings.

---

### Sprint 3: Domain Models

**PRD:** `docs/prds/core/e1-s3-domain-models-prd.md`

> Create a PRD for the domain models subsystem. Reference Sprint 3 in the [Epic 1 Detailed Roadmap](../roadmap/claude_headspace_v3.1_epic1_detailed_roadmap.md#sprint-3-domain-models--database-schema) and the domain model in the [Conceptual Overview](../conceptual/claude_headspace_v3.1_conceptual_overview.md). Include Objective (with history), Project, Agent, Task (5-state), Turn (actor/intent), and Event models with relationships, migrations, and validation rules.

---

### Epic 1 Sprint 4: File Watcher

**PRD:** `docs/prds/events/e1-s4-file-watcher-prd.md`

> Create a PRD for the file watcher subsystem. Reference Sprint 4 in the [Epic 1 Detailed Roadmap](../roadmap/claude_headspace_v3.1_epic1_detailed_roadmap.md#sprint-4-file-watcher). Include Watchdog integration for `~/.claude/projects/`, Claude Code jsonl parsing, session discovery, turn detection, project path decoding from folder names, and git metadata extraction.

Review conceptual design and guidance at:
docs/conceptual/claude_headspace_v3.1_conceptual_overview.md
docs/conceptual/claude_headspace_v3.1_epic1_guidance.md

And also the Epic 1 roadmap artifacts:
docs/roadmap/claude_headspace_v3.1_epic1_detailed_roadmap.md
docs/roadmap/claude_headspace_v3.1_overarching_roadmap.md

---

### Epic 1 Sprint 5: Event System

**PRD:** `docs/prds/events/e1-s5-event-system-prd.md`

> Create a PRD for the event system subsystem. Reference Sprint 5 in the [Epic 1 Detailed Roadmap](../roadmap/claude_headspace_v3.1_epic1_detailed_roadmap.md#sprint-5-event-system). Include event writer service to Postgres, background watcher process, event types taxonomy, event payload schema, and process supervision with auto-restart.

Review conceptual design and guidance at:
docs/conceptual/claude_headspace_v3.1_conceptual_overview.md
docs/conceptual/claude_headspace_v3.1_epic1_guidance.md
docs/architecture/claude-code-hooks.md

And also the Epic 1 roadmap artifacts:
docs/roadmap/claude_headspace_v3.1_epic1_detailed_roadmap.md
docs/roadmap/claude_headspace_v3.1_overarching_roadmap.md

---

### Epic 1 Sprint 6: State Machine

**PRD:** `docs/prds/state/e1-s6-state-machine-prd.md`

> Create a PRD for the state machine subsystem. Reference Sprint 6 in the [Epic 1 Detailed Roadmap](../roadmap/claude_headspace_v3.1_epic1_detailed_roadmap.md#sprint-6-taskturn-state-machine) and the 5-state model in the [Conceptual Overview](../conceptual/claude_headspace_v3.1_conceptual_overview.md). Include Task state transitions (idle → commanded → processing → awaiting_input/complete), turn intent detection (regex-based), state transition validator, task lifecycle management, and agent state derivation.

Review conceptual design and guidance at:
docs/conceptual/claude_headspace_v3.1_conceptual_overview.md
docs/conceptual/claude_headspace_v3.1_epic1_guidance.md
docs/architecture/claude-code-hooks.md

And also the Epic 1 roadmap artifacts:
docs/roadmap/claude_headspace_v3.1_epic1_detailed_roadmap.md
docs/roadmap/claude_headspace_v3.1_overarching_roadmap.md

---

### Epic 1 Sprint 7: SSE System

**PRD:** `docs/prds/api/e1-s7-sse-system-prd.md`

> Create a PRD for the SSE system subsystem. Reference Sprint 7 in the [Epic 1 Detailed Roadmap](../roadmap/claude_headspace_v3.1_epic1_detailed_roadmap.md#sprint-7-sse--real-time-updates). Include SSE endpoint (`/api/events`), event broadcaster service, HTMX SSE integration, reconnection handling, event filtering, and heartbeat/keepalive mechanism.

Review conceptual design and guidance at:
docs/conceptual/claude_headspace_v3.1_conceptual_overview.md
docs/conceptual/claude_headspace_v3.1_epic1_guidance.md
docs/architecture/claude-code-hooks.md

And also the Epic 1 roadmap artifacts:
docs/roadmap/claude_headspace_v3.1_epic1_detailed_roadmap.md
docs/roadmap/claude_headspace_v3.1_overarching_roadmap.md

---

### Epic 1 Sprint 8: Dashboard UI

**PRD:** `docs/prds/ui/e1-s8-dashboard-ui-prd.md`

> Create a PRD for the dashboard UI subsystem. Reference Sprint 8 in the [Epic 1 Detailed Roadmap](../roadmap/claude_headspace_v3.1_epic1_detailed_roadmap.md#sprint-8-dashboard-ui) and the [Epic 1 Guidance](../conceptual/claude_headspace_v3.1_epic1_guidance.md). Include Kanban layout, header bar with status counts, recommended next panel, sort controls, project groups with traffic lights, agent cards with state/task/priority/uptime, colour-coded state bars, HTMX interactivity, and SSE real-time updates.

Review conceptual design and guidance at:
docs/conceptual/claude_headspace_v3.1_conceptual_overview.md
docs/conceptual/claude_headspace_v3.1_epic1_guidance.md
docs/architecture/claude-code-hooks.md

And also the Epic 1 roadmap artifacts:
docs/roadmap/claude_headspace_v3.1_epic1_detailed_roadmap.md
docs/roadmap/claude_headspace_v3.1_overarching_roadmap.md

---

### Epic 1 Sprint 9: Objective Tab

**PRD:** `docs/prds/ui/e1-s9-objective-tab-prd.md`

> Create a PRD for the objective tab subsystem. Reference Sprint 9 in the [Epic 1 Detailed Roadmap](../roadmap/claude_headspace_v3.1_epic1_detailed_roadmap.md#sprint-9-objective-tab). Include objective tab template, form (text + constraints), auto-save with debounce, objective history display, Postgres storage, and API endpoints (GET/POST `/api/objective`, GET `/api/objective/history`).

Review conceptual design and guidance at:
docs/conceptual/claude_headspace_v3.1_conceptual_overview.md
docs/conceptual/claude_headspace_v3.1_epic1_guidance.md
docs/architecture/claude-code-hooks.md

And also the Epic 1 roadmap artifacts:
docs/roadmap/claude_headspace_v3.1_epic1_detailed_roadmap.md
docs/roadmap/claude_headspace_v3.1_overarching_roadmap.md

---

### Epic 1 Sprint 10: Logging Tab

**PRD:** `docs/prds/ui/e1-s10-logging-tab-prd.md`

> Create a PRD for the logging tab subsystem. Reference Sprint 10 in the [Epic 1 Detailed Roadmap](../roadmap/claude_headspace_v3.1_epic1_detailed_roadmap.md#sprint-10-logging-tab). Include event log table (timestamp, project, agent, event type, details), filters (project, agent, event type), real-time updates via SSE, pagination, expandable event details, and API endpoint (GET `/api/events`).

Review conceptual design and guidance at:
docs/conceptual/claude_headspace_v3.1_conceptual_overview.md
docs/conceptual/claude_headspace_v3.1_epic1_guidance.md
docs/architecture/claude-code-hooks.md

And also the Epic 1 roadmap artifacts:
docs/roadmap/claude_headspace_v3.1_epic1_detailed_roadmap.md
docs/roadmap/claude_headspace_v3.1_overarching_roadmap.md

---

### Epic 1 Sprint 11: Launcher Script

**PRD:** `docs/prds/scripts/e1-s11-launcher-script-prd.md`

> Create a PRD for the launcher script subsystem. Reference Sprint 11 in the [Epic 1 Detailed Roadmap](../roadmap/claude_headspace_v3.1_epic1_detailed_roadmap.md#sprint-11-launcher-script). Include `claude-headspace` CLI (Python), `start` command, session UUID generation, project detection from pwd, iTerm pane ID capture, session registration via HTTP POST, environment variable setup for hooks, Claude CLI launch, and cleanup on exit.

Review conceptual design and guidance at:
docs/conceptual/claude_headspace_v3.1_conceptual_overview.md
docs/conceptual/claude_headspace_v3.1_epic1_guidance.md
docs/architecture/claude-code-hooks.md

And also the Epic 1 roadmap artifacts:
docs/roadmap/claude_headspace_v3.1_epic1_detailed_roadmap.md
docs/roadmap/claude_headspace_v3.1_overarching_roadmap.md

---

### Epic 1 Sprint 12: AppleScript Integration

**PRD:** `docs/prds/scripts/e1-s12-applescript-integration-prd.md`

> Create a PRD for the AppleScript integration subsystem. Reference Sprint 12 in the [Epic 1 Detailed Roadmap](../roadmap/claude_headspace_v3.1_epic1_detailed_roadmap.md#sprint-12-applescript-integration). Include AppleScript to focus iTerm pane by ID, API endpoint (POST `/api/focus/<agent_id>`), agent card click wiring, permission error handling, fallback (show session path), and iTerm2 terminal support.

Review conceptual design and guidance at:
docs/conceptual/claude_headspace_v3.1_conceptual_overview.md
docs/conceptual/claude_headspace_v3.1_epic1_guidance.md
docs/architecture/claude-code-hooks.md

And also the Epic 1 roadmap artifacts:
docs/roadmap/claude_headspace_v3.1_epic1_detailed_roadmap.md
docs/roadmap/claude_headspace_v3.1_overarching_roadmap.md

---

### Epic 1 Sprint 13: Hook Receiver

**PRD:** `docs/prds/events/e1-s13-hook-receiver-prd.md`

> Create a PRD for the hook receiver subsystem. Reference Sprint 13 in the [Epic 1 Detailed Roadmap](../roadmap/claude_headspace_v3.1_epic1_detailed_roadmap.md#sprint-13-claude-code-hooks-integration) and the [Claude Code Hooks Architecture](../architecture/claude-code-hooks.md). Include HookReceiver service, hook API routes (session-start, session-end, stop, notification, user-prompt-submit, status), hook configuration, hybrid mode (hooks + polling fallback), session correlation via working directory, hook notification script, installation script, and hook status dashboard indicator.

Review conceptual design and guidance at:
docs/conceptual/claude_headspace_v3.1_conceptual_overview.md
docs/conceptual/claude_headspace_v3.1_epic1_guidance.md
docs/architecture/claude-code-hooks.md

And also the Epic 1 roadmap artifacts:
docs/roadmap/claude_headspace_v3.1_epic1_detailed_roadmap.md
docs/roadmap/claude_headspace_v3.1_overarching_roadmap.md

---

## Usage

1. Copy the prompt for the target sprint
2. Run `/10: prd-workshop`
3. Paste the prompt when asked for PRD requirements
4. The PRD will be generated in the specified location
