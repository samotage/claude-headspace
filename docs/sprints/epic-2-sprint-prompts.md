# Epic 2 Sprint Prompts for PRD Workshop

**Epic:** Epic 2 — UI Polish & Documentation  
**Reference:** [`docs/roadmap/claude_headspace_v3.1_epic2_detailed_roadmap.md`](../roadmap/claude_headspace_v3.1_epic2_detailed_roadmap.md)

---

## Context Documents

| Document                                                                              | Purpose                                                               |
| ------------------------------------------------------------------------------------- | --------------------------------------------------------------------- |
| [Epic 2 Detailed Roadmap](../roadmap/claude_headspace_v3.1_epic2_detailed_roadmap.md) | Primary reference for sprint scope, deliverables, acceptance criteria |
| [Conceptual Overview](../application/claude_headspace_v3.1_conceptual_overview.md)    | Domain concepts (waypoint, progress_summary, brain_reboot)            |
| [Overarching Roadmap](../roadmap/claude_headspace_v3.1_overarching_roadmap.md)        | Epic 2 goals, success criteria, dependencies                          |
| [Epic 1 Detailed Roadmap](../roadmap/claude_headspace_v3.1_epic1_detailed_roadmap.md) | Context on existing infrastructure (dashboard, SSE, tabs)             |

---

## Sprint Prompts

### Epic 2 Sprint 1: Config UI Tab

**PRD:** `docs/prds/ui/e2-s1-config-ui-prd.md`

> Create a PRD for the Config UI subsystem. Reference Sprint 1 (E2-S1) in the [Epic 2 Detailed Roadmap](../roadmap/claude_headspace_v3.1_epic2_detailed_roadmap.md#sprint-1-config-ui-tab-e2-s1).
>
> **Deliverables:**
>
> - Config tab HTML template (`templates/config.html`)
> - Form-based UI for editing all `config.yaml` sections: server, database, file_watcher, sse, claude
> - YAML parsing and serialization service (`src/services/config_editor.py`)
> - Server-side validation (type checking, required fields, value ranges)
> - Password field masking with reveal toggle
> - Success/error feedback via toast notifications
> - Refresh mechanism for applying config changes
>
> **API Endpoints:**
>
> - GET `/api/config` — retrieve current configuration
> - POST `/api/config` — save updated configuration
>
> **Integration Points:**
>
> - Uses Epic 1 tab navigation pattern from dashboard
> - Uses Epic 1 toast notification pattern for feedback
>
> **Technical Decisions to Address:**
>
> - Form-based editor (recommended) vs raw YAML editor
> - Which config sections to expose (all vs subset)
> - Config reload mechanism (manual refresh button recommended)
> - Handling of comments in YAML file (may be lost on save)

Review conceptual design and guidance at:

- docs/application/claude_headspace_v3.1_conceptual_overview.md

And also the roadmap artifacts:

- docs/roadmap/claude_headspace_v3.1_epic2_detailed_roadmap.md
- docs/roadmap/claude_headspace_v3.1_overarching_roadmap.md

---

### Epic 2 Sprint 2: Waypoint Editor

**PRD:** `docs/prds/ui/e2-s2-waypoint-editor-prd.md`

> Create a PRD for the Waypoint Editor subsystem. Reference Sprint 2 (E2-S2) in the [Epic 2 Detailed Roadmap](../roadmap/claude_headspace_v3.1_epic2_detailed_roadmap.md#sprint-2-waypoint-editing-ui-e2-s2) and the waypoint definition in the [Conceptual Overview](../application/claude_headspace_v3.1_conceptual_overview.md#62-artifact-definitions).
>
> **Deliverables:**
>
> - Waypoint editor UI (tab or modal)
> - Project selector dropdown populated from Epic 1 Project model
> - Markdown textarea with preview toggle
> - Load waypoint from project's `docs/brain_reboot/waypoint.md`
> - Save waypoint to project directory
> - Archive previous version to `archive/waypoint_YYYY-MM-DD.md` on save
> - Create `docs/brain_reboot/` directory structure if missing
> - Create waypoint with template if file doesn't exist
>
> **API Endpoints:**
>
> - GET `/api/projects/<id>/waypoint` — retrieve waypoint content for project
> - POST `/api/projects/<id>/waypoint` — save waypoint content for project
>
> **Waypoint Template (from Conceptual Overview):**
>
> ```markdown
> # Waypoint
>
> ## Next Up
>
> <!-- Immediate next steps -->
>
> ## Upcoming
>
> <!-- Coming soon -->
>
> ## Later
>
> <!-- Future work -->
>
> ## Not Now
>
> <!-- Parked/deprioritised -->
> ```
>
> **Integration Points:**
>
> - Uses Epic 1 Project model for project list
> - Uses editing patterns established in E2-S1 (Config UI)
>
> **Technical Decisions to Address:**
>
> - Editor type: plain textarea with preview (recommended) vs rich editor
> - Conflict detection if waypoint edited externally
> - File permission error handling for project directories

Review conceptual design and guidance at:

- docs/application/claude_headspace_v3.1_conceptual_overview.md (Section 6: Repo Artifacts)

And also the roadmap artifacts:

- docs/roadmap/claude_headspace_v3.1_epic2_detailed_roadmap.md
- docs/roadmap/claude_headspace_v3.1_overarching_roadmap.md

---

### Epic 2 Sprint 3: Help/Documentation System

**PRD:** `docs/prds/ui/e2-s3-help-system-prd.md`

> Create a PRD for the Help System subsystem. Reference Sprint 3 (E2-S3) in the [Epic 2 Detailed Roadmap](../roadmap/claude_headspace_v3.1_epic2_detailed_roadmap.md#sprint-3-helpdocumentation-system-e2-s3).
>
> **Deliverables:**
>
> - Help modal partial (`templates/partials/_help_modal.html`)
> - Keyboard shortcut: `?` to open help modal
> - Markdown documentation source files in `docs/help/` directory
> - Client-side full-text search (lunr.js or similar)
> - Table of contents navigation
> - Close modal on Escape key or click outside
>
> **Documentation Topics to Create:**
>
> - `docs/help/index.md` — table of contents
> - `docs/help/getting-started.md` — quick start guide
> - `docs/help/dashboard.md` — dashboard overview and usage
> - `docs/help/objective.md` — setting and managing objectives
> - `docs/help/configuration.md` — config.yaml options
> - `docs/help/waypoints.md` — waypoint editing and brain_reboot
> - `docs/help/troubleshooting.md` — common issues and solutions
>
> **API Endpoints:**
>
> - GET `/api/help/search?q=<query>` — search help documentation (optional, can be client-side only)
>
> **Integration Points:**
>
> - Modal overlays on existing Epic 1 dashboard
> - Keyboard event listener on document
>
> **Technical Decisions to Address:**
>
> - Help location: modal overlay (recommended) vs dedicated tab
> - Search implementation: client-side lunr.js (recommended) vs server-side
> - Documentation maintenance strategy

Review conceptual design and guidance at:

- docs/application/claude_headspace_v3.1_conceptual_overview.md

And also the roadmap artifacts:

- docs/roadmap/claude_headspace_v3.1_epic2_detailed_roadmap.md
- docs/roadmap/claude_headspace_v3.1_overarching_roadmap.md

---

### Epic 2 Sprint 4: macOS Notifications

**PRD:** `docs/prds/notifications/e2-s4-macos-notifications-prd.md`

> Create a PRD for the macOS Notifications subsystem. Reference Sprint 4 (E2-S4) in the [Epic 2 Detailed Roadmap](../roadmap/claude_headspace_v3.1_epic2_detailed_roadmap.md#sprint-4-macos-notifications-e2-s4).
>
> **Deliverables:**
>
> - Notification service (`src/services/notification_service.py`)
> - terminal-notifier integration via subprocess call
> - Trigger notifications on events: `task_complete`, `awaiting_input`
> - Notification preferences UI (settings panel or preferences modal)
> - Rate limiting: 5-second cooldown per agent to prevent spam
> - Click action: focus browser dashboard and highlight relevant agent
> - Detection of terminal-notifier installation with setup guidance
>
> **API Endpoints:**
>
> - GET `/api/notifications/preferences` — retrieve notification preferences
> - PUT `/api/notifications/preferences` — update notification preferences
>
> **Config.yaml Addition:**
>
> ```yaml
> notifications:
>   enabled: true
>   sound: true
>   events:
>     task_complete: true
>     awaiting_input: true
>   rate_limit_seconds: 5
> ```
>
> **Integration Points:**
>
> - Subscribes to Epic 1 SSE event stream for task state changes
> - Uses Epic 1 task state machine events (`task_complete`, `awaiting_input`)
> - Preferences stored in config.yaml (managed by E2-S1 Config UI)
>
> **Technical Decisions to Address:**
>
> - Notification library: terminal-notifier (Homebrew, recommended) vs native NSUserNotification
> - Click action: focus dashboard with agent highlight (recommended) vs focus iTerm directly
> - Rate limiting strategy: per-agent cooldown (recommended)
> - Sound options: default macOS sound vs silent

Review conceptual design and guidance at:

- docs/application/claude_headspace_v3.1_conceptual_overview.md

And also the roadmap artifacts:

- docs/roadmap/claude_headspace_v3.1_epic2_detailed_roadmap.md
- docs/roadmap/claude_headspace_v3.1_overarching_roadmap.md

---

## Usage

1. Copy the prompt for the target sprint
2. Run `/10: prd-workshop` (or your PRD creation workflow)
3. Paste the prompt when asked for PRD requirements
4. The PRD will be generated in the specified location
5. Reference the linked roadmap sections for additional detail if needed
