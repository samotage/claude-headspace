# Epic 5 Detailed Roadmap: Voice Bridge & Project Enhancement

**Project:** Claude Headspace v3.1  
**Epic:** Epic 5 — Voice Bridge & Project Enhancement  
**Author:** PM Agent (John)  
**Status:** Roadmap — Baseline for PRD Generation  
**Date:** 2026-02-04

---

## Executive Summary

This document serves as the **high-level roadmap and baseline** for Epic 5 implementation. It breaks Epic 5 into 9 logical sprints (1 sprint = 1 PRD = 1 OpenSpec change), identifies subsystems that require OpenSpec PRDs, and provides the foundation for generating detailed Product Requirements Documents for each subsystem.

**Epic 5 Goal:** Enable remote session interaction via dashboard input, provide comprehensive project detail pages with hierarchical data exploration, improve frustration metrics display, restructure the dashboard for better usability, create a self-documenting configuration system, align the CLI with tmux bridge transport, and capture full command/output for mobile review.

**Epic 5 Value Proposition:**

- **Input Bridge** — Respond to Claude Code permission prompts directly from the dashboard without context-switching to iTerm
- **tmux Bridge** — Reliable transport layer using tmux send-keys (replaces non-functional commander socket)
- **Project Show Page** — Unified view of a project's full state (metadata, waypoint, brain reboot, progress summary) from a single page
- **Object Tree** — Drill into the complete hierarchy of agents, tasks, and turns with frustration score highlighting
- **Embedded Metrics** — Activity data scoped to a specific project with day/week/month navigation
- **Frustration Display** — Average-based frustration metrics and multi-window frustration state widget
- **Dashboard Restructure** — Agent hero identity system, task-based Kanban layout, and real-time activity metrics on the dashboard
- **Config Help System** — Full config.yaml/UI parity with contextual help icons, popovers, and expanded documentation
- **CLI tmux Alignment** — CLI launcher detects tmux pane and includes pane ID in session registration (removes failed claudec)
- **Full Command/Output Capture** — Store complete user commands and agent responses for drill-down review from any device

**The Differentiator:** Epic 5 closes the interaction loop. Claude Headspace becomes bidirectional — not just passively monitoring agents, but actively responding to them. The Input Bridge is Phase 1 of the Voice Bridge vision, laying the foundation for future voice-controlled agent interaction. The tmux Bridge provides a proven, reliable transport mechanism after the initial commander socket approach proved incompatible with Claude Code's Ink-based TUI. The Dashboard Restructure introduces a universally-understood Kanban task-flow view, while the Config Help System ensures every setting is visible, editable, and explained. The CLI tmux Alignment ensures the primary entry point (`claude-headspace start --bridge`) works seamlessly with the tmux transport. Full Command/Output Capture decouples detailed review from the terminal, enabling mobile access to complete agent work.

**Success Criteria:**

- See "Input needed" amber card → click quick-action button → agent resumes without leaving dashboard
- Response delivered via tmux send-keys (reliable, verified working with Claude Code)
- Navigate to `/projects/claude-headspace` → see full project detail on one page
- Click project name in list → navigates to show page (no inline edit/delete buttons)
- Expand Agents accordion → see all agents with state, priority, timing
- Expand Tasks accordion → see all tasks with state, instruction, completion summary
- Expand Turns accordion → see turns with frustration scores highlighted
- Activity metrics display with day/week/month toggle and period navigation
- Archive history shows previous waypoint/brain reboot versions
- SSE events update accordion data in real-time
- Activity page frustration shows average (0-10) instead of raw sum
- Frustration state widget shows immediate/short-term/session rolling averages
- Agents displayed with two-character hero identity (first two hex chars large)
- Kanban view as default with task lifecycle state columns
- Overall activity metrics visible on dashboard below menu bar
- Every config.yaml field editable via config UI (except openrouter.pricing)
- Help icons on all config sections and fields with popovers
- Deep-link anchors on help page for direct field documentation access
- CLI `--bridge` flag detects tmux pane and reports availability
- Session registration includes tmux_pane_id from CLI (no hook backfill wait)
- Full user command text stored on Task model
- Full agent final message stored on Task model
- Drill-down buttons on dashboard card tooltips to view full text
- Full output visible in project view agent transcript
- Mobile-friendly rendering of full text (iPad, iPhone)

**Architectural Foundation:** Builds on Epic 4's project controls (pause/resume), activity monitoring (metrics infrastructure), and archive system (timestamped versions). Also leverages Epic 3's inference service, summarisation, and priority scoring.

**Dependency:** Epic 4 must be complete before Epic 5 begins (project settings, activity metrics, archive APIs must exist).

---

## Epic 5 Story Mapping

| Story ID | Story Name                                        | Subsystem                    | PRD Directory | Sprint | Priority |
| -------- | ------------------------------------------------- | ---------------------------- | ------------- | ------ | -------- |
| E5-S1    | Remote session interaction via claude-commander   | `input-bridge`               | bridge/       | 1      | P1       |
| E5-S2    | Project show page with metadata and controls      | `project-show-core`          | ui/           | 2      | P2       |
| E5-S3    | Project show page with object tree and metrics    | `project-show-tree`          | ui/           | 3      | P2       |
| E5-S4    | Replace commander socket with tmux send-keys      | `tmux-bridge`                | bridge/       | 4      | P1       |
| E5-S5    | Activity page frustration display improvements    | `activity-frustration`       | ui/           | 5      | P2       |
| E5-S6    | Dashboard restructure with hero style and Kanban  | `dashboard-restructure`      | ui/           | 6      | P2       |
| E5-S7    | Configuration help system and UI parity           | `config-help-system`         | ui/           | 7      | P2       |
| E5-S8    | CLI launcher tmux bridge alignment                | `cli-tmux-bridge`            | bridge/       | 8      | P1       |
| E5-S9    | Full command and output capture                   | `full-output-capture`        | core/         | 9      | P2       |

---

## Sprint Breakdown

### Sprint 1: Input Bridge (E5-S1) — DONE

**Goal:** Enable users to send text responses to Claude Code sessions directly from the Headspace dashboard.

**Duration:** 1 week  
**Dependencies:** Epic 4 complete (project controls exist), claude-commander binary available

**Deliverables:**

- Commander service for Unix socket communication with claude-commander
- Send text + newline (simulating "type and press Enter") to Claude Code sessions
- Health check for commander socket availability
- Response endpoint: `POST /api/respond/<agent_id>`
- Turn record creation (actor: USER, intent: ANSWER) for audit trail
- State transition: AWAITING_INPUT → PROCESSING
- Quick-action buttons for numbered permission choices (parsed from question text)
- Free-text input field for arbitrary responses
- Visual feedback on send success/failure
- Commander availability checking and SSE broadcast
- Graceful degradation when no commander socket available
- Documentation for launching sessions with `claudec` wrapper

**Subsystem Requiring PRD:**

1. `input-bridge` — Commander service, response endpoint, dashboard input UI

**PRD Location:** `docs/prds/bridge/done/e5-s1-input-bridge-prd.md`

**Stories:**

- E5-S1: Remote session interaction via claude-commander

**Technical Decisions Made:**

- Socket path convention: `/tmp/claudec-<SESSION_ID>.sock` — **decided**
- Socket protocol: Newline-delimited JSON over Unix domain socket — **decided**
- Response creates Turn record for audit trail — **decided**
- Input widget only shown when commander socket available — **decided**

**Agent Card — AWAITING_INPUT State with Commander Available:**

```
┌─────────────────────────────────────────────────────────────────────┐
│  [AMBER] claude-headspace                           Input needed    │
├─────────────────────────────────────────────────────────────────────┤
│  Line 04: "Do you want to proceed? 1. Yes 2. No 3. Cancel"          │
│                                                                     │
│  Quick Actions: [1: Yes] [2: No] [3: Cancel]                        │
│                                                                     │
│  ┌─────────────────────────────────────────────┐ [Send]             │
│  │ Type a response...                          │                    │
│  └─────────────────────────────────────────────┘                    │
│                                                                     │
│  [Focus iTerm]                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

**Risks:**

- claude-commander is a new external dependency (single developer, v0.1.0)
- Socket protocol could change in future versions
- 2-5 second startup delay before socket is available

**Acceptance Criteria:**

- [x] User can respond to a permission prompt from the dashboard
- [x] iTerm terminal remains fully interactive alongside dashboard input
- [x] Quick-action buttons appear for numbered permission choices
- [x] Free-text input available for arbitrary responses
- [x] Visual feedback confirms response sent (or shows error)
- [x] Dashboard degrades gracefully when commander socket unavailable
- [x] Responses recorded as Turn entities in audit trail
- [x] Commander availability broadcast via SSE

---

### Sprint 2: Project Show Page — Core (E5-S2)

**Goal:** Create a dedicated project show page at `/projects/<slug>` that serves as the canonical detail view for a project.

**Duration:** 1-2 weeks  
**Dependencies:** E5-S1 complete, E4-S2 complete (project controls backend/UI exist)

**Deliverables:**

**Slug-Based Routing:**

- Add `slug` field to Project model (unique, non-nullable, indexed)
- Slug auto-generated from project name (lowercase, hyphens for spaces/special chars)
- Slug regenerated when project name changes
- Database migration to add slug column and backfill existing rows
- Route: `GET /projects/<slug>` returns project show page
- 404 response for non-existent slugs

**Project Show Page:**

- Metadata display: name, path, GitHub repo (linked), branch, description, created date
- Inference status display: active or paused (with timestamp and reason if paused)
- Control actions: Edit, Delete, Pause/Resume, Regenerate Description, Refetch GitHub Info
- Edit opens form, saves changes, updates slug if name changed
- Delete shows confirmation dialog with cascade warning, redirects to `/projects`

**Content Sections:**

- Waypoint section: rendered markdown, edit link, empty state guidance
- Brain reboot section: rendered markdown, generation timestamp with time-ago, Regenerate and Export buttons
- Progress summary section: rendered markdown, Regenerate button

**Navigation Changes:**

- Projects list: project names become clickable links to `/projects/<slug>`
- Projects list: remove Edit, Delete, Pause/Resume action buttons
- Brain reboot modal: add link to project show page

**Subsystem Requiring PRD:**

2. `project-show-core` — Slug routing, show page template, metadata display, control actions

**PRD Location:** `docs/prds/ui/e5-s2-project-show-core-prd.md`

**Stories:**

- E5-S2: Project show page with metadata and controls

**Technical Decisions Required:**

- Slug collision handling: append numeric suffix (e.g., `my-project-2`) — **decided**
- Bookmark breakage on rename: accepted trade-off (slugs update with name) — **decided**
- Long content handling: max-height with scroll or "show more" — **implementation detail**

**Data Model Changes:**

```python
class Project(Base):
    ...
    slug: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
```

**Project Show Page Layout:**

```
+-----------------------------------------------------------------------+
|  CLAUDE >_headspace    [Dashboard] [Projects] [Activity] [Objective]...|
+-----------------------------------------------------------------------+
|                                                                        |
|  < Back to Projects                                                    |
|                                                                        |
|  claude-headspace                                                      |
|  ~/dev/otagelabs/claude_headspace                                      |
|  GitHub: otagelabs/claude_headspace  |  Branch: development            |
|  Created: 2 Jan 2026                                                   |
|                                                                        |
|  Description:                                                          |
|  Kanban-style web dashboard for tracking Claude Code sessions          |
|  across multiple projects...                                           |
|                                                                        |
|  +--------------------------------------------------------------+     |
|  | [Edit] [Delete] [Pause Inference] [Regen Desc] [Refetch Git] |     |
|  +--------------------------------------------------------------+     |
|                                                                        |
|  Inference: Active                                                     |
|  (or: Paused since 3 Feb 2026 — "Cost control")                       |
|                                                                        |
|  ================================================================      |
|                                                                        |
|  Waypoint                                                    [Edit]    |
|  ------------------------------------------------------------------   |
|  [Rendered markdown content of waypoint.md]                            |
|                                                                        |
|  ================================================================      |
|                                                                        |
|  Brain Reboot                          Generated 2 hours ago           |
|  ------------------------------------------------------------------   |
|  [Rendered markdown content of last brain reboot]                      |
|                                                                        |
|  [Regenerate]  [Export]                                                |
|                                                                        |
|  ================================================================      |
|                                                                        |
|  Progress Summary                                        [Regenerate] |
|  ------------------------------------------------------------------   |
|  [Rendered markdown content of progress summary]                       |
|                                                                        |
+-----------------------------------------------------------------------+
```

**Simplified Projects List:**

```
+-----------------------------------------------------------------------+
|  Projects                                            [+ Add Project]   |
|  -------------------------------------------------------------------  |
|                                                                        |
|  +------------------------------------------------------------------+ |
|  | Name                | Path                 | Agents | Status     | |
|  +------------------------------------------------------------------+ |
|  | claude-headspace    | ~/dev/.../headspace  | 3      | Active     | |
|  | my-webapp           | ~/dev/my-webapp      | 1      | Paused     | |
|  | api-server          | ~/dev/api-server     | 0      | Active     | |
|  +------------------------------------------------------------------+ |
|                                                                        |
|  (project names are clickable links to /projects/<slug>)               |
|  (no Edit/Delete/Pause action buttons in list)                         |
+-----------------------------------------------------------------------+
```

**Risks:**

- Slug collisions with similar project names
- Bookmarked URLs break on project rename
- Large waypoint/brain reboot content making page unwieldy

**Acceptance Criteria:**

- [ ] Project model has `slug` field (unique, non-nullable, indexed)
- [ ] Creating a project auto-generates a slug from the name
- [ ] Editing a project name updates the slug
- [ ] Navigate to `/projects/<slug>` — shows project detail
- [ ] Navigate to non-existent slug — returns 404
- [ ] Page displays metadata: name, path, GitHub (linked), branch, description, created
- [ ] Page displays inference status (active/paused with timestamp and reason)
- [ ] Edit action opens form, saves changes, updates display
- [ ] Delete action shows confirmation, deletes, redirects to `/projects`
- [ ] Pause/Resume toggles inference status immediately
- [ ] Regenerate Description updates description field
- [ ] Refetch GitHub Info updates repo and branch fields
- [ ] Waypoint section shows rendered markdown or empty state
- [ ] Brain reboot shows content with date and time-ago
- [ ] Brain reboot Regenerate and Export work
- [ ] Progress summary shows content with Regenerate option
- [ ] Projects list: names are clickable links to show page
- [ ] Projects list: no Edit/Delete/Pause action buttons
- [ ] Brain reboot modal includes link to project show page

---

### Sprint 3: Project Show Page — Tree & Metrics (E5-S3)

**Goal:** Extend the project show page with an accordion-based object tree and embedded activity metrics.

**Duration:** 1-2 weeks  
**Dependencies:** E5-S2 complete (show page exists), E4-S3 complete (activity metrics infrastructure)

**Deliverables:**

**Accordion Object Tree:**

- Agents accordion: collapsed by default, count badge (e.g., "Agents (3)")
- Agent rows: state indicator (color-coded), session UUID (truncated), priority score, started/ended timestamps, active duration
- Ended agents visually distinguished (muted styling, "Ended" badge)
- Tasks accordion (nested per agent): state badge, instruction (truncated), completion summary, started/completed timestamps, turn count
- Turns accordion (nested per task): actor badge (USER/AGENT), intent label, summary text, frustration score
- Frustration highlighting: yellow for scores >= 4, red for scores >= 7
- Collapse/expand toggling, collapsing parent collapses children

**Lazy Data Loading:**

- Accordion sections don't fetch data until expanded
- Loading indicator while fetching
- Error state with "Retry" option on failure
- Client-side caching (collapse/re-expand doesn't re-fetch)
- SSE events invalidate cache for expanded sections

**Activity Metrics Section:**

- Default to week (7-day) view
- Day/week/month toggle
- Period navigation arrows (back/forward, forward disabled at current period)
- Summary cards: turn count, average turn time, active agent count, frustration turn count
- Time-series chart (matching `/activity` page pattern)

**Archive History Section:**

- List archived artifacts (waypoints, brain reboots, progress summaries) with timestamps
- View action for each archive entry
- Empty state message when no archives

**Inference Metrics Summary:**

- Total inference calls, input/output tokens, total cost for the project

**SSE Real-Time Updates:**

- SSE connection filtered for current project
- Agent state changes update Agents accordion (if expanded)
- Task state changes update Tasks accordion (if expanded)
- Project changes update page metadata
- Updates don't disrupt accordion expand/collapse state

**Subsystem Requiring PRD:**

3. `project-show-tree` — Accordion tree, lazy loading, activity metrics, archive history, SSE updates

**PRD Location:** `docs/prds/ui/e5-s3-project-show-tree-and-metrics-prd.md`

**Stories:**

- E5-S3: Project show page with object tree and metrics

**Technical Decisions Required:**

- Accordion lazy loading: fetch on expand only — **decided**
- Accordion caching: client-side, invalidated by SSE — **decided**
- Activity metrics: reuse `/activity` page patterns (Chart.js, time navigation) — **decided**
- SSE debouncing: batch updates every 2 seconds for high-activity projects — **recommended**

**New API Endpoints Needed:**

| Endpoint | Purpose |
|----------|---------|
| `GET /api/agents/<id>/tasks` | List tasks for an agent |
| `GET /api/tasks/<id>/turns` | List turns for a task |
| `GET /api/projects/<id>/inference-summary` | Aggregate inference metrics |

**Accordion Object Tree:**

```
+-----------------------------------------------------------------------+
|                                                                        |
|  (... metadata, controls, waypoint, brain reboot from E5-S2 ...)      |
|                                                                        |
|  ================================================================      |
|                                                                        |
|  v Agents (3)                                                          |
|  ------------------------------------------------------------------   |
|  | [green] abc-1234...  | Score: 85 | Active | Started 2h ago     |   |
|  |                                                                 |   |
|  |   v Tasks (5)                                                   |   |
|  |   +-----------------------------------------------------------+|   |
|  |   | [COMPLETE] Fix auth bug          | 3 turns | 25 min       ||   |
|  |   |                                                            ||   |
|  |   |   v Turns (3)                                              ||   |
|  |   |   +------------------------------------------------------+||   |
|  |   |   | [USER]  COMMAND  "Fix the login bug"        frust: 0  |||   |
|  |   |   | [AGENT] PROGRESS "Investigating auth..."    frust: -  |||   |
|  |   |   | [USER]  ANSWER   "Yes, that file"           frust: 6  |||   |
|  |   |   +------------------------------------------------------+||   |
|  |   |                                                            ||   |
|  |   | [PROCESSING] Add caching layer   | 1 turn  | 5 min        ||   |
|  |   | > Tasks (collapsed)                                        ||   |
|  |   +-----------------------------------------------------------+|   |
|  |                                                                 |   |
|  | [grey] def-5678...   | Score: -- | Ended  | 3h ago — 1h 20m    |   |
|  | > Tasks (collapsed)                                             |   |
|  |                                                                 |   |
|  | [blue] ghi-9012...   | Score: 42 | Active | Started 30m ago    |   |
|  | > Tasks (collapsed)                                             |   |
|  ------------------------------------------------------------------   |
|                                                                        |
+-----------------------------------------------------------------------+
```

**Activity Metrics Section:**

```
+-----------------------------------------------------------------------+
|                                                                        |
|  Activity Metrics                                                      |
|  ------------------------------------------------------------------   |
|                                                                        |
|  [< prev]  This Week (27 Jan - 2 Feb)  [next >]                       |
|                                                                        |
|  [Day] [Week*] [Month]                                                 |
|                                                                        |
|  +-------------+  +-------------+  +-------------+  +-------------+   |
|  | Turns       |  | Avg Time    |  | Agents      |  | Frustration |   |
|  | 142         |  | 3.2 min     |  | 4 active    |  | 8 elevated  |   |
|  +-------------+  +-------------+  +-------------+  +-------------+   |
|                                                                        |
|  [====== time series chart ======]                                     |
|  |  .    .                       |                                     |
|  | . .. ..  .    .  .            |                                     |
|  |..........  ....  ..  .   .    |                                     |
|  +-------------------------------+                                     |
|                                                                        |
+-----------------------------------------------------------------------+
```

**Risks:**

- Deep nesting with many agents/tasks/turns could create large DOM
- High-activity projects may generate many SSE events
- Stale cached accordion data if page left open for a long time
- Duplicating activity chart logic creates maintenance burden

**Acceptance Criteria:**

- [ ] Agents accordion present, collapsed by default with count badge
- [ ] Expanding Agents fetches and shows all project agents (active and ended)
- [ ] Agent rows show: state indicator, ID, priority score, timing, duration
- [ ] Ended agents visually distinguished from active agents
- [ ] Clicking agent expands Tasks section (lazy loaded)
- [ ] Task rows show: state badge, instruction, summary, timing, turn count
- [ ] Clicking task expands Turns section (lazy loaded)
- [ ] Turn rows show: actor badge, intent, summary, frustration score
- [ ] Frustration scores >= 4 highlighted (yellow)
- [ ] Frustration scores >= 7 highlighted (red)
- [ ] Loading indicators shown while fetching accordion data
- [ ] Error state with retry shown on fetch failure
- [ ] Collapsing parent collapses nested children
- [ ] Activity metrics section displays with week default
- [ ] Day/week/month toggle works
- [ ] Period navigation arrows work
- [ ] Forward arrow disabled at current period
- [ ] Summary cards show: turn count, avg time, agents, frustration count
- [ ] Time-series chart displays activity
- [ ] Archive section lists artifacts with timestamps
- [ ] Archive entries have view action
- [ ] Empty state when no archives
- [ ] Inference summary shows calls, tokens, cost
- [ ] SSE connection established with project filter
- [ ] SSE updates don't disrupt accordion state

---

### Sprint 4: tmux Bridge (E5-S4)

**Goal:** Replace the non-functional claude-commander socket bridge with a tmux-based input bridge using `tmux send-keys`.

**Duration:** 1 week  
**Dependencies:** E5-S1 complete (respond pipeline exists), tmux installed, iTerm2 tmux integration

**Deliverables:**

**tmux Bridge Service:**

- New `tmux_bridge.py` service wrapping tmux CLI commands as subprocess calls
- Send literal text via `tmux send-keys -t <pane_id> -l "<text>"`
- Send special keys (Enter, Escape, Up, Down, C-c, C-u) via `tmux send-keys -t <pane_id> <key>`
- Configurable delay between text send and Enter send (default 100ms)
- Health check: pane existence and Claude Code process detection
- Capture pane content for readiness detection
- List all tmux panes with metadata

**Agent Model & Hooks:**

- Add `tmux_pane_id` field to Agent model (new migration)
- Update `bin/notify-headspace.sh` to extract `$TMUX_PANE` in all hook payloads
- Update hook routes to extract and pass `tmux_pane` through to hook receiver
- Store pane ID on first hook event that includes it (typically session-start)
- Late discovery: any hook can populate `tmux_pane_id` if not yet set

**Respond Pipeline Updates:**

- Replace socket-based send with tmux subprocess calls in respond route
- Validate agent has `tmux_pane_id` before attempting send
- Preserve existing API contract (`POST /api/respond/<agent_id>`)

**Availability Tracking:**

- Replace socket probing with tmux pane existence checks
- Preserve SSE broadcast of availability changes
- Preserve `commander_availability` extension key for backward compatibility

**Error Handling:**

- New `TmuxBridgeErrorType` enum replacing `CommanderErrorType`
- Error types: `PANE_NOT_FOUND`, `TMUX_NOT_INSTALLED`, `SUBPROCESS_FAILED`, `NO_PANE_ID`, `TIMEOUT`, `SEND_FAILED`, `UNKNOWN`
- Preserve `SendResult` and `HealthResult` namedtuple shapes

**Configuration:**

- Replace `commander:` config section with `tmux_bridge:` section
- Settings: `health_check_interval`, `subprocess_timeout`, `text_enter_delay_ms`, `sequential_send_delay_ms`

**Subsystem Requiring PRD:**

4. `tmux-bridge` — tmux service, hook updates, respond pipeline rewiring

**PRD Location:** `docs/prds/bridge/e5-s4-tmux-bridge-prd.md`

**Stories:**

- E5-S4: Replace commander socket with tmux send-keys

**Technical Decisions Made:**

- Use `-l` flag for user text to prevent tmux interpreting key names — **decided**
- Send Enter as separate `send-keys` call without `-l` — **decided**
- 100ms delay between text and Enter sends — **decided**
- Preserve `commander_availability` extension key for backward compatibility — **decided**
- `tmux_pane_id` coexists with `iterm_pane_id` (separate concerns) — **decided**

**Data Model Changes:**

```python
class Agent(Base):
    ...
    tmux_pane_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
```

**Config.yaml Changes:**

```yaml
# Remove:
commander:
  health_check_interval: 30
  socket_timeout: 2
  socket_path_prefix: /tmp/claudec-

# Add:
tmux_bridge:
  health_check_interval: 30
  subprocess_timeout: 5
  text_enter_delay_ms: 100
  sequential_send_delay_ms: 150
```

**Replacement Mapping:**

| Current (commander) | New (tmux bridge) |
|---------------------|-------------------|
| `socket.connect("/tmp/claudec-{id}.sock")` | `subprocess.run(["tmux", "send-keys", ...])` |
| `{"action": "send", "text": "..."}` | `send-keys -t {pane_id} -l "text"` + `send-keys Enter` |
| `{"action": "status"}` | `tmux list-panes -a -F '#{pane_id} #{pane_current_command}'` |
| Socket path from `claude_session_id` | Pane ID from `$TMUX_PANE` via hooks |
| `CommanderErrorType` enum | `TmuxBridgeErrorType` enum |

**Risks:**

- tmux must be installed (`brew install tmux`)
- Sessions must be launched inside tmux panes
- Cannot target plain iTerm2 tabs without tmux
- All windows in a tmux session share dimensions

**Acceptance Criteria:**

- [ ] Response via dashboard delivered to Claude Code via `tmux send-keys`
- [ ] Dual input works (user typing + dashboard respond coexist)
- [ ] Hook scripts pass `$TMUX_PANE` and pane ID stored on Agent
- [ ] Availability checks detect tmux pane existence and Claude Code process
- [ ] API contract unchanged (`POST /api/respond/<agent_id>`)
- [ ] SSE events for availability changes continue to work
- [ ] Dashboard JS unchanged (transport swap is invisible)
- [ ] `tmux_pane_id` and `iterm_pane_id` coexist independently
- [ ] Clear error messages for: pane not found, tmux not installed, no pane ID

---

### Sprint 5: Activity Frustration Display (E5-S5)

**Goal:** Fix activity page frustration metrics to show averages instead of sums, and add a multi-window frustration state widget.

**Duration:** 1 week  
**Dependencies:** E4-S3 complete (activity monitoring), E4-S4 complete (headspace monitoring)

**Deliverables:**

**Average-Based Frustration Display:**

- Activity page metric cards show average frustration (0-10) instead of raw sum
- Average = `total_frustration ÷ frustration_turn_count`, rounded to one decimal
- Threshold-based coloring: green < 4, yellow 4-7, red > 7
- Display "—" when no scored turns in period
- Apply to overall, project, and agent levels

**Chart Frustration Line:**

- Chart shows per-bucket average (0-10) instead of sum
- Fixed right Y-axis scaled 0-10
- Gaps in line for buckets with no scored turns
- Threshold-based coloring on line/data points

**Frustration State Widget:**

- New widget near overall metrics section
- Three rolling-window averages: Immediate (~10 turns), Short-term (30 min), Session (3 hours)
- Numeric display with threshold-based coloring
- Hover tooltips showing threshold boundaries
- Real-time updates via SSE (existing headspace events)
- Hidden when headspace monitoring disabled
- "—" display when window has no data

**HeadspaceSnapshot Model:**

- Add `frustration_rolling_3hr` field (new rolling window)
- Session window duration configurable via config.yaml
- Update `/api/headspace/current` to include session-level average

**Configuration:**

- All thresholds read from config (no hardcoded values)
- Session rolling window duration configurable
- Config UI section for frustration settings

**Subsystem Requiring PRD:**

5. `activity-frustration` — Average display, chart changes, frustration state widget

**PRD Location:** `docs/prds/ui/e5-s5-activity-frustration-display-prd.md`

**Stories:**

- E5-S5: Activity page frustration display improvements

**Technical Decisions Made:**

- Compute average at display time from existing fields (no aggregator changes) — **decided**
- Reuse existing headspace SSE events for widget updates — **decided**
- Fixed 0-10 Y-axis for chart (matches frustration score scale) — **decided**
- Gap in chart line for zero-turn buckets (not draw-to-zero) — **decided**

**Data Model Changes:**

```python
class HeadspaceSnapshot(Base):
    ...
    frustration_rolling_3hr: Mapped[float | None]  # New field
```

**Config.yaml Additions:**

```yaml
headspace:
  ...
  session_rolling_window_minutes: 180  # 3 hours, configurable
```

**Frustration State Widget:**

```
+-----------------------------------------------------------------------+
|                                                                        |
|  Frustration State                                                     |
|  ------------------------------------------------------------------   |
|                                                                        |
|  +------------------+  +------------------+  +------------------+     |
|  | Immediate        |  | Short-term       |  | Session          |     |
|  | 3.2 [green]      |  | 5.1 [yellow]     |  | 2.8 [green]      |     |
|  +------------------+  +------------------+  +------------------+     |
|                                                                        |
|  (hover any value for threshold tooltip)                               |
|                                                                        |
+-----------------------------------------------------------------------+
```

**Risks:**

- 3-hour rolling window query performance (wider time range)
- Widget SSE handling adding complexity to activity page
- Users may be confused by average vs sum change

**Acceptance Criteria:**

- [ ] Metric cards show decimal average (0-10) instead of integer sum
- [ ] Frustration values colored green/yellow/red based on thresholds
- [ ] "—" displayed when no scored turns in period
- [ ] Chart frustration line shows per-bucket average (0-10)
- [ ] Chart right Y-axis fixed at 0-10
- [ ] Chart has gaps for buckets with no scored turns
- [ ] Frustration state widget displays three rolling averages
- [ ] Widget values update in real-time via SSE
- [ ] Widget hidden when headspace disabled
- [ ] Hover tooltips show threshold boundaries
- [ ] All thresholds from config (no hardcoded values)
- [ ] Config UI includes frustration settings section
- [ ] 3-hour rolling window computed by HeadspaceMonitor
- [ ] `/api/headspace/current` includes session-level average

---

### Sprint 6: Dashboard Restructure (E5-S6) — DONE

**Goal:** Introduce agent hero identity system, task-based Kanban layout, and real-time activity metrics on the dashboard.

**Duration:** 1-2 weeks  
**Dependencies:** E5-S5 complete (activity frustration display), existing dashboard infrastructure

**Deliverables:**

**Agent Hero Style:**

- Agent identity displays first two hex characters prominently (large text), remaining characters smaller trailing behind
- Remove `#` prefix from all agent identity displays
- Hero style applied across: dashboard cards, project agent lists, activity page sections, logging tables, filter dropdowns
- Active indicator moved to far right of card header, preceded by uptime display
- Logging agent filter dropdown format: `0a - 0a5510d4` (hero chars, separator, full truncated UUID)

**Kanban Layout:**

- New "Kanban" sort option as first/default sort mode
- Tasks organised into columns by lifecycle state: IDLE, COMMANDED, PROCESSING, AWAITING_INPUT, COMPLETE
- Idle agents (no active tasks) displayed in IDLE column as full agent cards
- Same agent can appear in multiple columns simultaneously (one per task)
- Priority-based ordering within columns when prioritisation enabled
- Multiple projects display as horizontal sections with own state columns
- Completed tasks render as collapsed accordions in scrollable COMPLETE column
- Completed tasks retained until parent agent reaped

**Activity Metrics on Dashboard:**

- Overall activity metrics bar below menu, above state summary
- Metrics: Total Turns, Turns/Hour, Avg Turn Time, Active Agents, Frustration (immediate)
- Real-time SSE updates on every turn
- Frustration changed to immediate (last 10 turns) on dashboard and activity page

**Subsystem Requiring PRD:**

6. `dashboard-restructure` — Agent hero style, Kanban layout, dashboard activity metrics

**PRD Location:** `docs/prds/ui/done/e5-s6-dashboard-restructure-prd.md`

**Stories:**

- E5-S6: Dashboard restructure with hero style and Kanban

**Technical Decisions Made:**

- Two-character hero identity extracted from session UUID start — **decided**
- Kanban as default view (replaces current agent-centric layout) — **decided**
- Frustration metric changed to immediate (last 10 turns) across all views — **decided**
- Same agent can appear in multiple Kanban columns — **decided**

**Dashboard Card Header (Updated):**

```
┌─────────────────────────────────────────────────────────────────────┐
│  0A5510d4   claude-headspace                    3h 24m  ● Active    │
├─────────────────────────────────────────────────────────────────────┤
│  [Task instruction or summary content...]                           │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

**Kanban View Layout:**

```
┌───────────────────────────────────────────────────────────────────────────────┐
│  [Activity Metrics Bar: Turns: 142 | Turns/Hr: 8.2 | Avg: 3.2m | ...]         │
├───────────────────────────────────────────────────────────────────────────────┤
│  INPUT NEEDED: 1  │  WORKING: 3  │  IDLE: 2                                   │
├───────────────────────────────────────────────────────────────────────────────┤
│                                                                               │
│  ┌─────────┐  ┌─────────┐  ┌──────────┐  ┌──────────────┐  ┌─────────┐       │
│  │  IDLE   │  │COMMANDED│  │PROCESSING│  │AWAITING_INPUT│  │ COMPLETE│       │
│  ├─────────┤  ├─────────┤  ├──────────┤  ├──────────────┤  ├─────────┤       │
│  │ [agent] │  │ [task]  │  │ [task]   │  │ [task]       │  │ ▶ task  │       │
│  │ [agent] │  │         │  │ [task]   │  │              │  │ ▶ task  │       │
│  │         │  │         │  │          │  │              │  │ ▶ task  │       │
│  └─────────┘  └─────────┘  └──────────┘  └──────────────┘  └─────────┘       │
│                                                                               │
└───────────────────────────────────────────────────────────────────────────────┘
```

**Risks:**

- Kanban view layout complexity on smaller viewports
- High task volume could create dense layouts
- SSE event frequency for real-time metric updates

**Acceptance Criteria:**

- [x] Agents displayed with two-character hero identity (first two hex chars large)
- [x] `#` prefix removed from all agent ID displays
- [x] Hero style applied consistently across dashboard, projects, activity, logging
- [x] Logging agent filter dropdowns use format: `0a - 0a5510d4`
- [x] Kanban view available and is first/default sort option
- [x] Tasks appear in correct lifecycle state columns
- [x] Idle agents in dedicated IDLE column
- [x] Completed tasks collapse to accordions in scrollable COMPLETE column
- [x] Priority ordering within columns when enabled
- [x] Multiple projects display as horizontal sections
- [x] Activity metrics bar visible below menu
- [x] Dashboard metrics update in real-time via SSE
- [x] Frustration metric shows immediate (last 10 turns)

---

### Sprint 7: Configuration Help System (E5-S7) — DONE

**Goal:** Close config.yaml/UI parity gap and add contextual help system with icons, popovers, and expanded documentation.

**Duration:** 1 week  
**Dependencies:** E5-S6 complete, existing config page infrastructure

**Deliverables:**

**Config/UI Parity:**

- Expose `tmux_bridge` section: `health_check_interval`, `subprocess_timeout`, `text_enter_delay_ms`
- Expose `dashboard` section: `stale_processing_seconds`, `active_timeout_minutes`
- Expose `archive` section: `enabled`, `retention.policy`, `retention.keep_last_n`, `retention.days`
- Expose missing `openrouter` fields: `retry.base_delay_seconds`, `retry.max_delay_seconds`, `priority_scoring.debounce_seconds`
- Expose missing `headspace` flow detection fields: `flow_detection.min_turn_rate`, `flow_detection.max_frustration`, `flow_detection.min_duration_minutes`
- Add `commander` section to config.yaml with explicit defaults

**Help Icons:**

- Clickable info icon on every config section header
- Clickable info icon on every config field label
- Icons visually subtle (muted colour), non-competing with labels

**Popover Component:**

- Field popover: practical description, default value, valid range, "Learn more" link
- Section popover: section description, "Learn more" link
- Only one popover visible at a time
- Dismissible: click outside, Escape key, or click icon again
- Smart positioning to avoid viewport overflow

**Deep-Link Anchors:**

- Help page supports anchor-based deep-linking (e.g., `/help/configuration#headspace`)
- Target section highlights on anchor navigation
- "Learn more" links use corresponding anchor URLs

**Documentation:**

- `docs/help/configuration.md` updated with per-field documentation
- Each field: what it controls, when to change it, consequences of incorrect values
- Each section: introductory paragraph explaining purpose

**Subsystem Requiring PRD:**

7. `config-help-system` — Config/UI parity, help icons, popovers, documentation

**PRD Location:** `docs/prds/ui/done/e5-s7-config-help-system-prd.md`

**Stories:**

- E5-S7: Configuration help system and UI parity

**Technical Decisions Made:**

- Vanilla JS popover implementation (no framework) — **decided**
- Single popover visible at a time (opening closes others) — **decided**
- openrouter.pricing excluded from UI (dynamic map) — **decided**
- Anchor-based deep-linking for help page sections — **decided**

**Config Page Help System:**

```
┌───────────────────────────────────────────────────────────────────────────────┐
│  HEADSPACE ⓘ                                                                  │
├───────────────────────────────────────────────────────────────────────────────┤
│                                                                               │
│  enabled ⓘ                    [x] Enabled                                     │
│                                                                               │
│  yellow_threshold ⓘ           [ 4 ]                                           │
│                                     ┌─────────────────────────────────┐       │
│  red_threshold ⓘ              [ 7 ] │ Frustration score threshold for │       │
│                                     │ yellow warning state.            │       │
│  session_rolling_window ⓘ     [180] │                                  │       │
│                                     │ Default: 4                       │       │
│                                     │ Range: 1-10                      │       │
│                                     │                                  │       │
│                                     │ Learn more →                     │       │
│                                     └─────────────────────────────────┘       │
│                                                                               │
└───────────────────────────────────────────────────────────────────────────────┘
```

**Risks:**

- Popover positioning edge cases on varied viewport sizes
- Documentation maintenance burden as config evolves
- Help content accuracy drift over time

**Acceptance Criteria:**

- [x] Every config.yaml field (except openrouter.pricing) editable in UI
- [x] `tmux_bridge`, `dashboard`, `archive` sections exposed
- [x] Missing `openrouter` and `headspace` fields exposed
- [x] Help icon on every section header
- [x] Help icon on every field label
- [x] Clicking help icon opens popover with description, default, range, link
- [x] Only one popover visible at a time
- [x] Popovers dismissible via click outside, Escape, or icon click
- [x] "Learn more" links navigate to `/help/configuration#section`
- [x] Help page supports anchor-based deep-linking
- [x] Target section highlights on anchor navigation
- [x] `docs/help/configuration.md` contains per-field documentation
- [x] Documentation covers: what, when to change, consequences

---

### Sprint 8: CLI Launcher tmux Bridge Alignment (E5-S8) — DONE

**Goal:** Replace failed claudec mechanism in CLI launcher with tmux pane detection, aligning the CLI with the server-side tmux bridge.

**Duration:** 1 week  
**Dependencies:** E5-S4 complete (tmux bridge server-side), E5-S7 complete

**Deliverables:**

**claudec Removal:**

- Remove `detect_claudec()` function and all claudec references from launcher
- Remove `shutil.which("claudec")` call
- Always launch `claude` directly (no wrapper binary)

**tmux Pane Detection:**

- New function to detect tmux pane via `$TMUX_PANE` environment variable
- Returns pane ID (e.g., `%0`, `%5`) if in tmux, or `None` if not
- When `--bridge` passed, output: `Input Bridge: available (tmux pane %N)` or `Input Bridge: unavailable (not in tmux session)`
- Warning (not block) when `--bridge` used outside tmux — monitoring still works, input bridge won't

**Session Registration:**

- `register_session()` accepts optional `tmux_pane_id` parameter
- Include `tmux_pane_id` in registration payload when available
- `POST /api/sessions` endpoint accepts and stores `tmux_pane_id` on Agent at creation
- Register agent with `CommanderAvailability` tracker immediately when pane ID provided

**CLI Help Text:**

- Update `--bridge` flag description to reference tmux instead of claudec
- No references to claudec or commander in any help text

**Subsystem Requiring PRD:**

8. `cli-tmux-bridge` — claudec removal, tmux detection, session registration update

**PRD Location:** `docs/prds/bridge/done/e5-s8-cli-tmux-bridge-prd.md`

**Stories:**

- E5-S8: CLI launcher tmux bridge alignment

**Technical Decisions Made:**

- Simple `os.environ.get("TMUX_PANE")` for detection (no subprocess) — **decided**
- Backward-compatible registration payload (tmux_pane_id optional) — **decided**
- Warn but don't block when outside tmux — **decided**
- Preserve `--bridge` flag short form for existing aliases — **decided**

**Current vs Target Launcher Flow:**

```
Current:
get_server_url() → validate_prerequisites() → get_project_info() →
get_iterm_pane_id() → uuid4() → register_session() →
[if --bridge: detect_claudec()] → setup_environment() →
SessionManager context → launch_claude()

Target:
get_server_url() → validate_prerequisites() → get_project_info() →
get_iterm_pane_id() → [if --bridge: get_tmux_pane_id()] → uuid4() →
register_session(tmux_pane_id=...) → setup_environment() →
SessionManager context → launch_claude()
```

**Session Registration Payload:**

```json
{
  "session_uuid": "...",
  "project_path": "...",
  "working_directory": "...",
  "project_name": "...",
  "current_branch": "...",
  "iterm_pane_id": "...",
  "tmux_pane_id": "%5"
}
```

**Risks:**

- Users with shell aliases (`clhb`) may expect old claudec behaviour (documentation needed)
- Outside tmux, input bridge unavailable but monitoring works

**Acceptance Criteria:**

- [x] `claude-headspace start --bridge` inside tmux shows `Input Bridge: available (tmux pane %N)`
- [x] `claude-headspace start --bridge` outside tmux shows `Input Bridge: unavailable (not in tmux session)`
- [x] `claude-headspace start` (without `--bridge`) launches with no bridge detection output
- [x] Session registration includes `tmux_pane_id` when available
- [x] Agent record has pane ID immediately after creation (no hook backfill wait)
- [x] `CommanderAvailability` begins monitoring from session creation
- [x] No references to claudec, claude-commander, or detect_claudec in launcher
- [x] Existing user aliases continue to work

---

### Sprint 9: Full Command & Output Capture (E5-S9) — DONE

**Goal:** Extend Task model to persist full user command and full agent output, with drill-down UI on dashboard and project view.

**Duration:** 1-2 weeks  
**Dependencies:** E5-S8 complete, E5-S6 complete (dashboard restructure)

**Deliverables:**

**Task Model Extensions:**

- New field for full user command text (no character limit)
- New field for full agent final message text (no character limit)
- Existing summary fields (`instruction`, `completion_summary`) unchanged
- Migration to add new text columns

**Capture Pipeline:**

- When task created from user command, persist complete command text
- When task transitions to COMPLETE, persist final agent message text
- Full text captured at same time as summary generation

**Dashboard Drill-Down UI:**

- Drill-down button in expanded tooltip for instruction line
- Drill-down button in expanded tooltip for completion summary line
- Pressing drill-down opens scrollable overlay/modal with full text
- Full text display readable on mobile viewports (min 320px width)

**Project View Integration:**

- Full agent output visible in agent chat transcript details
- Accordion or expandable section pattern for full text
- Consistent with Kanban completed task cards

**Performance Considerations:**

- Full text fields NOT included in SSE card_refresh payloads
- Full text loaded on demand when user requests drill-down
- On-demand loading responds within 1 second

**Subsystem Requiring PRD:**

9. `full-output-capture` — Task model fields, capture pipeline, drill-down UI

**PRD Location:** `docs/prds/core/done/e5-s9-full-command-output-capture-prd.md`

**Stories:**

- E5-S9: Full command and output capture

**Technical Decisions Made:**

- No hard character limit on full text fields — **decided**
- On-demand loading for full text (not broadcast via SSE) — **decided**
- Existing summaries unchanged (backward compatible) — **decided**
- Same overlay pattern for instruction and completion drill-down — **decided**

**Data Model Changes:**

```python
class Task(Base):
    ...
    full_command: Mapped[str | None] = mapped_column(Text, nullable=True)
    full_output: Mapped[str | None] = mapped_column(Text, nullable=True)
```

**Dashboard Drill-Down UI:**

```
┌─────────────────────────────────────────────────────────────────────┐
│  0A5510d4   claude-headspace                    3h 24m  ● Active    │
├─────────────────────────────────────────────────────────────────────┤
│  Instruction: "Fix the auth bug in login.py"      [View full ▸]     │
│  Completed: "Fixed auth by updating token..."     [View full ▸]     │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘

[Drill-down overlay]
┌─────────────────────────────────────────────────────────────────────┐
│  Full Agent Response                                         [×]    │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  I've fixed the authentication bug in login.py. The issue was      │
│  that the token validation wasn't checking the expiry timestamp.   │
│                                                                     │
│  Changes made:                                                      │
│  1. Added expiry check in validate_token()                         │
│  2. Updated token refresh logic in refresh_auth()                  │
│  3. Added test cases for expired token scenarios                   │
│                                                                     │
│  [scrollable if content exceeds viewport]                          │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

**Risks:**

- Very large outputs could impact database storage (mitigated: TEXT type handles it)
- Mobile rendering of long text needs careful UX testing
- Users may expect search within full text (out of scope for this sprint)

**Acceptance Criteria:**

- [x] Task model has field for full user command text
- [x] Task model has field for full agent final message text
- [x] Full command persisted when task created
- [x] Full output persisted when task completes
- [x] Drill-down button on dashboard card tooltip for instruction
- [x] Drill-down button on dashboard card tooltip for completion summary
- [x] Pressing drill-down displays full text in overlay
- [x] Full output visible in project view transcript
- [x] Full text display readable on mobile (320px min)
- [x] Full text NOT included in SSE card_refresh events
- [x] On-demand loading responds within 1 second
- [x] Existing summary display unchanged

---

## Subsystems Requiring OpenSpec PRDs

The following 9 subsystems have PRDs created. Each PRD was validated before implementation.

### PRD Directory Structure

```
docs/prds/
├── bridge/
│   ├── done/
│   │   ├── e5-s1-input-bridge-prd.md        # DONE
│   │   ├── e5-s4-tmux-bridge-prd.md         # DONE
│   │   └── e5-s8-cli-tmux-bridge-prd.md     # DONE
├── core/
│   └── done/
│       └── e5-s9-full-command-output-capture-prd.md  # DONE
└── ui/
    ├── done/
    │   ├── e5-s6-dashboard-restructure-prd.md     # DONE
    │   └── e5-s7-config-help-system-prd.md        # DONE
    ├── e5-s2-project-show-core-prd.md       # Draft
    ├── e5-s3-project-show-tree-and-metrics-prd.md  # Draft
    └── e5-s5-activity-frustration-display-prd.md   # Pending
```

---

### 1. Input Bridge

**Subsystem ID:** `input-bridge`  
**Sprint:** E5-S1  
**Priority:** P1  
**PRD Location:** `docs/prds/bridge/done/e5-s1-input-bridge-prd.md`

**Scope:**

- Commander service for Unix socket communication
- Response endpoint with state transition
- Quick-action buttons for numbered choices
- Free-text input for arbitrary responses
- Commander availability checking and SSE broadcast
- Graceful degradation when socket unavailable

**Key Requirements:**

- Must send text + newline to Claude Code via commander socket
- Must check socket availability before showing input widget
- Must create Turn record for audit trail
- Must trigger AWAITING_INPUT → PROCESSING state transition
- Must parse numbered options from question text for quick-action buttons
- Must broadcast commander availability changes via SSE

**OpenSpec Spec:** `openspec/specs/input-bridge/spec.md`

**Related Files:**

- `src/claude_headspace/services/commander_service.py` (new)
- `src/claude_headspace/services/commander_availability.py` (new)
- `src/claude_headspace/routes/respond.py` (new)
- `templates/partials/_agent_card.html` (update — add input widget)
- `static/js/respond.js` (new)
- `config.yaml` (add commander section)

**Config.yaml Additions:**

```yaml
commander:
  health_check_interval: 30
  socket_timeout: 2
  socket_path_prefix: /tmp/claudec-
```

**Dependencies:** Epic 4 complete, claude-commander binary installed

**Acceptance Tests:**

- Send response via dashboard → Claude Code receives text
- Quick-action buttons appear for numbered options
- Free-text input sends arbitrary text
- No commander socket → input widget hidden
- Response creates Turn record
- State transitions correctly

---

### 2. Project Show Core

**Subsystem ID:** `project-show-core`  
**Sprint:** E5-S2  
**Priority:** P2  
**PRD Location:** `docs/prds/ui/e5-s2-project-show-core-prd.md`

**Scope:**

- Slug field on Project model with migration
- Slug auto-generation and update on rename
- Project show page route and template
- Metadata display (name, path, GitHub, branch, description, created)
- Control actions (edit, delete, pause/resume, regenerate description, refetch git)
- Waypoint section with markdown rendering
- Brain reboot section with timestamp and controls
- Progress summary section with regenerate
- Projects list navigation changes
- Brain reboot modal link to show page

**Key Requirements:**

- Must add slug field to Project model (unique, non-nullable, indexed)
- Must auto-generate slug from name on create
- Must regenerate slug when name changes
- Must handle slug collisions with numeric suffix
- Must display all project metadata on show page
- Must provide all control actions inline (no modals in list)
- Must render waypoint/brain reboot/progress as markdown
- Must show brain reboot timestamp with time-ago

**OpenSpec Spec:** `openspec/specs/project-show-core/spec.md`

**Related Files:**

- `src/claude_headspace/models/project.py` (update — add slug field)
- `src/claude_headspace/routes/projects.py` (update — add show page route)
- `templates/project_show.html` (new)
- `templates/projects.html` (update — links, remove actions)
- `static/js/project_show.js` (new)
- `static/js/projects.js` (update — remove action handlers)
- `templates/partials/_brain_reboot_modal.html` (update — add link)
- `migrations/versions/xxxx_add_project_slug.py` (new)
- `tests/routes/test_project_show.py` (new)

**Data Model Changes:**

```python
class Project(Base):
    ...
    slug: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
```

**Dependencies:** E5-S1 complete, E4-S2 complete (project controls exist)

**Acceptance Tests:**

- Create project → slug auto-generated
- Rename project → slug updated
- Navigate to `/projects/<slug>` → see show page
- Navigate to invalid slug → 404
- Edit/Delete/Pause work from show page
- Waypoint/brain reboot/progress display correctly
- Projects list shows clickable links, no action buttons

---

### 3. Project Show Tree

**Subsystem ID:** `project-show-tree`  
**Sprint:** E5-S3  
**Priority:** P2  
**PRD Location:** `docs/prds/ui/e5-s3-project-show-tree-and-metrics-prd.md`

**Scope:**

- Accordion object tree (agents → tasks → turns)
- Lazy data loading per accordion section
- Frustration score highlighting (yellow/red thresholds)
- Activity metrics section with time navigation
- Archive history section
- Inference metrics summary
- SSE real-time updates for expanded sections

**Key Requirements:**

- Must display expandable/collapsible accordion tree
- Must lazy-load data only when section expanded
- Must cache fetched data client-side
- Must highlight frustration scores at or above thresholds
- Must display activity metrics with day/week/month toggle
- Must provide period navigation (back/forward)
- Must list archived artifacts with view action
- Must show inference metrics summary (calls, tokens, cost)
- Must update via SSE without disrupting accordion state

**OpenSpec Spec:** `openspec/specs/project-show-tree/spec.md`

**Related Files:**

- `templates/project_show.html` (update — add accordion, metrics, archive sections)
- `templates/partials/_project_accordion.html` (new)
- `templates/partials/_project_metrics.html` (new)
- `static/js/project_show.js` (update — accordion logic, lazy loading, SSE)
- `src/claude_headspace/routes/projects.py` (update — add drill-down endpoints if needed)
- `src/claude_headspace/routes/agents.py` (update — add tasks endpoint if needed)
- `src/claude_headspace/routes/tasks.py` (new — add turns endpoint)

**Dependencies:** E5-S2 complete, E4-S3 complete (activity metrics exist)

**Acceptance Tests:**

- Agents accordion shows count badge, expands on click
- Tasks accordion lazy-loads on expand
- Turns accordion lazy-loads on expand
- Frustration scores highlighted correctly
- Activity metrics display with toggles and navigation
- Archive history lists items with view action
- Inference summary shows totals
- SSE updates expanded sections without disruption

---

### 4. tmux Bridge

**Subsystem ID:** `tmux-bridge`  
**Sprint:** E5-S4  
**Priority:** P1  
**PRD Location:** `docs/prds/bridge/e5-s4-tmux-bridge-prd.md`

**Scope:**

- tmux bridge service wrapping CLI commands as subprocess calls
- Replace commander socket transport with tmux send-keys
- Add `tmux_pane_id` field to Agent model
- Update hook scripts and routes to pass pane ID
- Update respond pipeline to use tmux targeting
- Replace availability socket probing with tmux pane checks
- New error type enum for tmux-specific errors

**Key Requirements:**

- Must send text via `tmux send-keys -t <pane_id> -l "text"` + `send-keys Enter`
- Must check pane existence and Claude Code process detection
- Must preserve API contract (`POST /api/respond/<agent_id>`)
- Must preserve SSE availability event shape
- Must add `tmux_pane_id` to Agent model (nullable)
- Must update all hook routes to extract `tmux_pane` from payload
- Must provide clear error messages for tmux-specific failures

**OpenSpec Spec:** `openspec/specs/tmux-bridge/spec.md`

**Related Files:**

- `src/claude_headspace/services/tmux_bridge.py` (new)
- `src/claude_headspace/services/commander_service.py` (replace internals)
- `src/claude_headspace/services/commander_availability.py` (replace internals)
- `src/claude_headspace/routes/respond.py` (update targeting)
- `src/claude_headspace/routes/hooks.py` (extract tmux_pane)
- `src/claude_headspace/services/hook_receiver.py` (store pane ID)
- `src/claude_headspace/models/agent.py` (add tmux_pane_id)
- `bin/notify-headspace.sh` (add $TMUX_PANE extraction)
- `config.yaml` (replace commander section with tmux_bridge)
- `migrations/versions/xxxx_add_agent_tmux_pane_id.py` (new)

**Data Model Changes:**

```python
class Agent(Base):
    ...
    tmux_pane_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
```

**Config.yaml Changes:**

```yaml
tmux_bridge:
  health_check_interval: 30
  subprocess_timeout: 5
  text_enter_delay_ms: 100
  sequential_send_delay_ms: 150
```

**Dependencies:** E5-S1 complete, tmux installed, iTerm2 tmux integration

**Acceptance Tests:**

- Response via tmux send-keys triggers Claude Code prompt submission
- Dual input (keyboard + dashboard) works simultaneously
- Pane ID extracted from hooks and stored on Agent
- Availability reflects tmux pane existence
- Error messages clear for pane not found, tmux not installed

---

### 5. Activity Frustration

**Subsystem ID:** `activity-frustration`  
**Sprint:** E5-S5  
**Priority:** P2  
**PRD Location:** `docs/prds/ui/e5-s5-activity-frustration-display-prd.md`

**Scope:**

- Activity page metric cards show average frustration (0-10) instead of sum
- Chart frustration line shows per-bucket average with fixed 0-10 Y-axis
- Threshold-based coloring on all frustration displays
- New frustration state widget with three rolling-window averages
- Add `frustration_rolling_3hr` to HeadspaceSnapshot model
- Config UI section for frustration settings

**Key Requirements:**

- Must display average frustration (total_frustration ÷ frustration_turn_count)
- Must color values green < 4, yellow 4-7, red > 7
- Must display "—" when no scored turns exist
- Must fix chart Y-axis at 0-10 (not dynamic)
- Must show gaps in chart line for zero-turn buckets
- Must add frustration state widget with immediate/short-term/session values
- Must update widget via SSE in real-time
- Must hide widget when headspace disabled
- Must read all thresholds from config (no hardcoded values)
- Must add 3-hour rolling window to HeadspaceSnapshot

**OpenSpec Spec:** `openspec/specs/activity-frustration/spec.md`

**Related Files:**

- `src/claude_headspace/models/headspace_snapshot.py` (add frustration_rolling_3hr)
- `src/claude_headspace/services/headspace_monitor.py` (compute 3hr window)
- `src/claude_headspace/routes/headspace.py` (include 3hr in response)
- `src/claude_headspace/routes/activity.py` (pass config thresholds)
- `templates/activity.html` (add widget, update cards)
- `static/js/activity.js` (average calculation, widget, chart changes)
- `templates/partials/_config_form.html` (add frustration settings)
- `config.yaml` (add session_rolling_window_minutes)
- `migrations/versions/xxxx_add_headspace_3hr_rolling.py` (new)

**Data Model Changes:**

```python
class HeadspaceSnapshot(Base):
    ...
    frustration_rolling_3hr: Mapped[float | None]
```

**Config.yaml Additions:**

```yaml
headspace:
  ...
  session_rolling_window_minutes: 180
```

**Dependencies:** E4-S3 complete (activity monitoring), E4-S4 complete (headspace monitoring)

**Acceptance Tests:**

- Metric cards show decimal average instead of integer sum
- Values colored based on thresholds
- Chart Y-axis fixed 0-10
- Chart line gaps for zero-turn buckets
- Widget shows three rolling averages with colors
- Widget updates via SSE
- Widget hidden when headspace disabled
- Config UI edits frustration settings

---

### 6. Dashboard Restructure

**Subsystem ID:** `dashboard-restructure`  
**Sprint:** E5-S6  
**Priority:** P2  
**PRD Location:** `docs/prds/ui/done/e5-s6-dashboard-restructure-prd.md`

**Scope:**

- Agent hero style identity (two-character emphasis + trailing smaller chars)
- Hero style across all views: dashboard, projects, activity, logging
- Kanban layout as default view with task lifecycle state columns
- Idle agents column, completed tasks as accordions
- Overall activity metrics bar on dashboard
- Real-time SSE updates for dashboard metrics
- Frustration changed to immediate (last 10 turns) everywhere

**Key Requirements:**

- Must display first two hex characters prominently, remainder smaller
- Must remove `#` prefix from all agent ID displays
- Must add Kanban as first/default sort option
- Must organise tasks into lifecycle state columns
- Must show idle agents in dedicated column
- Must display completed tasks as collapsible accordions
- Must show activity metrics bar below menu
- Must update metrics in real-time via SSE
- Must change frustration display to immediate (last 10 turns)

**OpenSpec Spec:** `openspec/specs/dashboard-restructure/spec.md`

**Related Files:**

- `templates/dashboard.html` (update — hero style, Kanban layout, metrics bar)
- `templates/partials/_agent_card.html` (update — hero style, header reorder)
- `templates/partials/_kanban_column.html` (new)
- `templates/partials/_task_card.html` (new)
- `templates/activity.html` (update — hero style, immediate frustration)
- `templates/projects.html` (update — hero style)
- `templates/logging.html` (update — hero style, filter format)
- `static/js/dashboard.js` (update — Kanban rendering, SSE handling)
- `static/js/activity.js` (update — immediate frustration)
- `static/css/src/input.css` (update — hero style classes)

**Dependencies:** E5-S5 complete, existing dashboard infrastructure

**Acceptance Tests:**

- Agents displayed with two-character hero identity
- Kanban view is default with task columns
- Tasks appear in correct lifecycle state column
- Completed tasks collapse to accordions
- Activity metrics visible below menu
- Metrics update in real-time via SSE
- Frustration shows immediate (last 10 turns)

---

### 7. Config Help System

**Subsystem ID:** `config-help-system`  
**Sprint:** E5-S7  
**Priority:** P2  
**PRD Location:** `docs/prds/ui/done/e5-s7-config-help-system-prd.md`

**Scope:**

- Expose all missing config.yaml fields in UI (tmux_bridge, dashboard, archive, openrouter, headspace flow detection)
- Add commander section to config.yaml with explicit defaults
- Help icon on every config section header
- Help icon on every config field label
- Popover component with description, default, range, learn more link
- Deep-link anchors on help page
- Expanded per-field documentation

**Key Requirements:**

- Must expose every config.yaml field in UI (except openrouter.pricing)
- Must add clickable help icon to every section header
- Must add clickable help icon to every field label
- Must show popover with: description, default, range (numeric), learn more link
- Must support only one popover visible at a time
- Must dismiss popovers via click outside, Escape, or icon click
- Must support anchor-based deep-linking on help page
- Must include per-field documentation: what, when, consequences

**OpenSpec Spec:** `openspec/specs/config-help-system/spec.md`

**Related Files:**

- `src/claude_headspace/services/config_editor.py` (update — add missing sections to schema)
- `templates/config.html` (update — add help icons, popover containers)
- `templates/partials/_config_form.html` (update — section/field help icons)
- `static/js/config.js` (update — popover logic)
- `static/js/popover.js` (new — popover component)
- `static/js/help.js` (update — anchor deep-link handling)
- `docs/help/configuration.md` (update — per-field documentation)
- `config.yaml` (update — add commander section with defaults)

**Dependencies:** E5-S6 complete, existing config page infrastructure

**Acceptance Tests:**

- All config.yaml fields editable in UI
- Help icons on all sections and fields
- Popovers show description, default, range, link
- Only one popover visible at a time
- Deep-link anchors work on help page
- Documentation covers all fields

---

### 8. CLI tmux Bridge

**Subsystem ID:** `cli-tmux-bridge`  
**Sprint:** E5-S8  
**Priority:** P1  
**PRD Location:** `docs/prds/bridge/done/e5-s8-cli-tmux-bridge-prd.md`

**Scope:**

- Remove all claudec detection, wrapping, and references from CLI launcher
- Repurpose `--bridge` flag for tmux pane detection
- Detect tmux pane via `$TMUX_PANE` environment variable
- Include `tmux_pane_id` in session registration payload
- Update sessions API to accept and store pane ID on Agent
- Register agent with `CommanderAvailability` at session creation
- Update CLI help text for tmux

**Key Requirements:**

- Must remove `detect_claudec()` and all claudec references
- Must always launch `claude` directly (no wrapper)
- Must detect tmux pane via environment variable (no subprocess)
- Must include pane ID in registration when available
- Must warn (not block) when `--bridge` used outside tmux
- Must preserve `--bridge` flag short form for existing aliases
- Must update `POST /api/sessions` to accept `tmux_pane_id`

**OpenSpec Spec:** `openspec/specs/cli-tmux-bridge/spec.md`

**Related Files:**

- `src/claude_headspace/cli/launcher.py` (remove claudec, add tmux detection)
- `src/claude_headspace/routes/sessions.py` (accept tmux_pane_id)
- `tests/cli/test_launcher.py` (update tests)
- `tests/routes/test_sessions.py` (add pane ID tests)

**Dependencies:** E5-S4 complete (tmux bridge server-side)

**Acceptance Tests:**

- CLI inside tmux shows bridge available with pane ID
- CLI outside tmux shows bridge unavailable (warning, not error)
- Session registration includes pane ID
- Agent has pane ID immediately after creation
- No claudec references remain in code

---

### 9. Full Output Capture

**Subsystem ID:** `full-output-capture`  
**Sprint:** E5-S9  
**Priority:** P2  
**PRD Location:** `docs/prds/core/done/e5-s9-full-command-output-capture-prd.md`

**Scope:**

- Two new text fields on Task model for full command and full output
- Capture full user command when task created
- Capture full agent final message when task completes
- Drill-down buttons on dashboard card tooltips
- Full output in project view transcript
- Mobile-friendly full text rendering
- On-demand loading (not in SSE payloads)

**Key Requirements:**

- Must add `full_command` and `full_output` fields to Task model
- Must persist complete command text at task creation
- Must persist complete agent message at task completion
- Must provide drill-down UI on dashboard tooltips
- Must display full output in project view transcript
- Must render full text readably on mobile (320px min)
- Must NOT include full text in SSE card_refresh events
- Must load full text on demand within 1 second

**OpenSpec Spec:** `openspec/specs/full-output-capture/spec.md`

**Related Files:**

- `src/claude_headspace/models/task.py` (add full_command, full_output)
- `src/claude_headspace/services/task_lifecycle.py` (capture full text)
- `src/claude_headspace/services/summarisation_service.py` (pass full text)
- `src/claude_headspace/routes/tasks.py` (endpoint for full text retrieval)
- `templates/partials/_agent_card.html` (drill-down buttons)
- `templates/partials/_full_text_modal.html` (new)
- `static/js/dashboard.js` (drill-down handling)
- `migrations/versions/xxxx_add_task_full_text.py` (new)

**Data Model Changes:**

```python
class Task(Base):
    ...
    full_command: Mapped[str | None] = mapped_column(Text, nullable=True)
    full_output: Mapped[str | None] = mapped_column(Text, nullable=True)
```

**Dependencies:** E5-S8 complete, E5-S6 complete (dashboard restructure)

**Acceptance Tests:**

- Full command stored on task creation
- Full output stored on task completion
- Drill-down buttons appear on dashboard card tooltips
- Drill-down displays full text in overlay
- Full output visible in project view
- Mobile rendering readable
- Full text not in SSE payloads

---

## Sprint Dependencies & Critical Path

```
[Epic 4 Complete]
       │
       ▼
   E5-S1 (Input Bridge) ←── DONE
       │
       ├──▶ E5-S2 (Project Show Core)
       │       │
       │       └──▶ E5-S3 (Project Show Tree & Metrics)
       │
       └──▶ E5-S4 (tmux Bridge) ←── DONE
               │
               └──▶ E5-S8 (CLI tmux Alignment) ←── DONE
                       │
                       └──▶ [Input Bridge Complete]

[E4-S3 + E4-S4 Complete]
       │
       └──▶ E5-S5 (Activity Frustration Display)
               │
               └──▶ E5-S6 (Dashboard Restructure) ←── DONE
                       │
                       └──▶ E5-S7 (Config Help System) ←── DONE
                               │
                               └──▶ E5-S9 (Full Output Capture) ←── DONE
                                       │
                                       └──▶ [Epic 5 Complete]
```

**Critical Path:** Epic 4 → E5-S1 → E5-S4 → E5-S8 → [Input Bridge Complete]

**Parallel Tracks:**

- E5-S2/E5-S3 (Project Show) are independent of E5-S4/E5-S8 (tmux Bridge) — can run in parallel
- E5-S5 (Activity Frustration) is independent of E5-S2/E5-S3/E5-S4 — depends only on E4-S3 and E4-S4
- E5-S4 is a transport fix for E5-S1 — completed, Input Bridge now functional
- E5-S6 (Dashboard Restructure) depends on E5-S5 (uses immediate frustration metric)
- E5-S7 (Config Help System) depends on E5-S6 (sequential UI polish)
- E5-S8 (CLI tmux Alignment) depends on E5-S4 (server-side tmux bridge must exist)
- E5-S9 (Full Output Capture) depends on E5-S6 (dashboard restructure for drill-down UI)

**Recommended Sequence:**

1. E5-S1 (Input Bridge) — establishes respond pipeline (DONE)
2. E5-S4 (tmux Bridge) — fixes transport layer (DONE)
3. E5-S2 (Project Show Core) — creates the show page foundation
4. E5-S3 (Project Show Tree & Metrics) — adds data exploration and metrics
5. E5-S5 (Activity Frustration Display) — improves frustration metrics
6. E5-S6 (Dashboard Restructure) — hero style, Kanban, dashboard metrics (DONE)
7. E5-S7 (Config Help System) — config parity, help icons, documentation (DONE)
8. E5-S8 (CLI tmux Alignment) — CLI launcher tmux pane detection (DONE)
9. E5-S9 (Full Output Capture) — full command/output with drill-down UI (DONE)

**Total Duration:** 9-11 weeks

---

## Technical Decisions Made

### Decision 1: Slug Updates on Rename

**Decision:** When a project name changes, the slug is regenerated to match. The old slug is not preserved as an alias.

**Rationale:**

- Simple implementation (no alias tracking)
- Slugs always match current name (predictable)
- Users can re-navigate from projects list
- Alias management adds complexity with minimal benefit for single-user tool

**Impact:**

- Bookmarked URLs break on project rename
- Users must navigate via projects list after rename
- No redirect from old slug to new slug

---

### Decision 2: Accordion Lazy Loading

**Decision:** Accordion sections fetch data from the API only when expanded, not on page load.

**Rationale:**

- Fast initial page load (no agent/task/turn data fetched)
- Only load what user actually wants to see
- Supports projects with many agents/tasks without performance hit
- Client-side caching prevents redundant fetches

**Impact:**

- Brief loading indicator on first expand
- Need API endpoints for drill-down data
- SSE events must invalidate cached data

---

### Decision 3: Reuse Activity Page Patterns

**Decision:** Activity metrics on the project show page reuse the same JavaScript patterns from the `/activity` page.

**Rationale:**

- Consistent UX (same toggles, navigation, chart style)
- Reduced maintenance burden (shared code)
- Proven patterns that already work
- Chart.js already in use

**Impact:**

- May need to extract shared charting logic into reusable module
- Both pages must stay in sync on UI changes

---

### Decision 4: Commander Socket Protocol

**Decision:** Use the claude-commander socket protocol (JSON over Unix domain socket) as-is.

**Rationale:**

- Simple protocol (~200 lines of Rust)
- Already working and released (v0.1.0)
- Can fork/replace if project abandoned
- Anthropic may add native IPC (easy to swap)

**Impact:**

- Dependency on external binary
- Socket path convention must match
- Protocol changes require service update

---

### Decision 5: Frustration Score Thresholds

**Decision:** Use configurable thresholds for frustration highlighting (default: yellow >= 4, red >= 7).

**Rationale:**

- Matches headspace monitoring thresholds from E4-S4
- Configurable allows user personalization
- Visual consistency across dashboard and project show

**Impact:**

- Read thresholds from config at render time
- CSS classes for yellow/red highlighting
- Threshold changes update immediately

---

### Decision 6: tmux send-keys over Commander Socket

**Decision:** Replace claude-commander Unix socket injection with tmux send-keys subprocess calls.

**Rationale:**

- Commander socket failed in practice — Claude Code's Ink TUI doesn't recognize socket-injected newlines
- Proof of concept confirmed tmux send-keys reliably triggers Ink's onSubmit handler
- tmux is widely available (`brew install tmux`)
- iTerm2's native tmux integration preserves full terminal ergonomics

**Impact:**

- Users must launch Claude Code sessions inside tmux panes
- Cannot target plain iTerm2 tabs without tmux
- Dashboard respond UI unchanged (transport swap is invisible)
- Existing API contracts preserved

---

### Decision 7: Separate Text and Enter Sends

**Decision:** Send literal text and Enter key as separate tmux commands with 100ms delay.

**Rationale:**

- `-l` flag required for text to prevent tmux interpreting key names
- Enter must be sent without `-l` to trigger as a key
- 100ms delay prevents race conditions
- Pattern verified in proof of concept

**Impact:**

- Slightly slower than single command (100ms overhead)
- More reliable prompt submission
- Clear separation of text content vs control keys

---

### Decision 8: Average vs Sum for Frustration Display

**Decision:** Activity page displays average frustration per scored turn (0-10) instead of raw sum.

**Rationale:**

- Sum correlates with turn volume, not frustration intensity
- A calm 50-turn session showing "50" appears worse than 5 angry turns showing "40"
- Average on 0-10 scale is directly interpretable
- Existing data supports this (total_frustration ÷ frustration_turn_count)

**Impact:**

- Breaking change to displayed metric interpretation
- Chart Y-axis becomes fixed 0-10
- Users see actual frustration intensity, not activity volume

---

### Decision 9: Three Rolling Windows for Frustration State

**Decision:** Frustration state widget shows three windows: immediate (~10 turns), short-term (30 min), session (3 hours).

**Rationale:**

- Immediate captures real-time spikes
- Short-term shows recent trend
- Session provides overall context
- Three windows balance responsiveness with stability
- Immediate and short-term already computed by HeadspaceMonitor

**Impact:**

- New 3-hour rolling window added to HeadspaceSnapshot
- Widget provides at-a-glance frustration state
- Users can distinguish temporary spikes from sustained frustration

---

### Decision 10: Two-Character Hero Identity from Session UUID

**Decision:** Agent identity displays first two hex characters of session UUID prominently, with remaining characters rendered smaller.

**Rationale:**

- Two characters provide 256 unique combinations — sufficient for typical session counts
- Prominent display creates visual personality for agents
- Remaining characters available for disambiguation when needed
- Consistent with logging filter format: `0a - 0a5510d4`

**Impact:**

- Agents are instantly recognizable across all views
- `#` prefix removed from all displays (cleaner appearance)
- Dashboard, projects, activity, and logging all use hero style

---

### Decision 11: Kanban as Default Dashboard View

**Decision:** The Kanban task-flow view becomes the default (first) sort option, replacing the agent-centric layout.

**Rationale:**

- Kanban is a universally understood task-flow metaphor
- Maps directly to task lifecycle states (IDLE → COMMANDED → PROCESSING → AWAITING_INPUT → COMPLETE)
- Shows where work is flowing, not just which agents exist
- Same agent can appear in multiple columns (one per task)

**Impact:**

- Users see task progress at a glance
- Idle agents have dedicated column
- Completed tasks accumulate in scrollable accordion column
- Multiple projects display as horizontal sections

---

### Decision 12: Immediate Frustration Metric (Last 10 Turns)

**Decision:** Frustration metrics on dashboard and activity page now show immediate frustration (last 10 turns) instead of aggregated/averaged values.

**Rationale:**

- Immediate frustration reflects current state, not historical average
- Aligns with headspace monitoring's rolling-10 window
- More actionable — shows if user is frustrated right now
- Consistent across dashboard metrics bar and activity page sections

**Impact:**

- Breaking change to frustration display interpretation
- All sections (overall, project, agent) use immediate metric
- Dashboard activity bar shows same metric as headspace

---

### Decision 13: Single Popover Visibility

**Decision:** Only one help popover can be visible at a time on the config page.

**Rationale:**

- Multiple overlapping popovers would create visual clutter
- Opening a new popover implicitly closes the previous one
- Simpler mental model for users
- Easier to implement positioning logic

**Impact:**

- Clean, uncluttered config page even with many help icons
- Users focus on one field explanation at a time
- Consistent UX pattern throughout config page

---

### Decision 14: Anchor-Based Deep-Linking for Help

**Decision:** Help page supports anchor-based URLs (e.g., `/help/configuration#headspace`) that scroll to and highlight the target section.

**Rationale:**

- Standard web pattern for deep-linking to page sections
- Enables "Learn more" links in popovers to navigate directly
- Target highlighting orients user to the relevant content
- Simple implementation without complex routing

**Impact:**

- Help popovers can link directly to relevant documentation
- External bookmarks can target specific config sections
- Users land on exactly the information they need

---

## Open Questions

### 1. Voice Bridge Integration Points

**Question:** Where should Phase 2 (Voice Capture) integrate with the Input Bridge architecture?

**Options:**

- **Option A:** Voice transcription feeds directly into commander service
- **Option B:** Voice transcription goes through a separate voice service, then to commander
- **Option C:** Voice transcription creates a new input type alongside text

**Recommendation:** Option A — voice transcription feeds into the same commander service, keeping the architecture simple.

**Decision needed by:** Future Voice Bridge Phase 2 planning

---

### 2. Project Show Page Caching Strategy

**Question:** How long should accordion data be cached client-side?

**Options:**

- **Option A:** Cache forever until SSE invalidates
- **Option B:** Cache with TTL (e.g., 5 minutes)
- **Option C:** No caching, always re-fetch on expand

**Recommendation:** Option A — cache until SSE invalidates. SSE provides real-time invalidation, so no TTL needed.

**Decision needed by:** E5-S3 implementation

---

### 3. Large Project Performance

**Question:** How should the accordion handle projects with many agents (>50)?

**Options:**

- **Option A:** Show all agents, let user scroll
- **Option B:** Paginate agents (show first 20, "load more" button)
- **Option C:** Virtual scrolling (only render visible items)

**Recommendation:** Option B — pagination with "load more" is simpler than virtual scrolling and handles large projects gracefully.

**Decision needed by:** E5-S3 implementation

---

## Risks & Mitigation

### Risk 1: Slug Collisions

**Risk:** Two projects could generate the same slug (e.g., "My Project" and "my-project").

**Impact:** Low (unique constraint prevents data corruption)

**Mitigation:**

- Unique constraint on slug column
- Slug generation appends numeric suffix on collision (e.g., `my-project-2`)
- Collision handling tested in migration for existing data

**Monitoring:** Track slug collision occurrences in logs

---

### Risk 2: claude-commander Dependency

**Risk:** claude-commander is a new project (v0.1.0, single developer). It could be abandoned or have breaking changes.

**Impact:** Medium (Input Bridge would stop working)

**Mitigation:**

- Simple protocol (~200 lines of Rust) — easy to fork/reimplement
- Socket protocol is stable (JSON over Unix socket)
- If Anthropic adds native IPC, can swap to that
- Commander service is isolated — changes don't affect rest of system

**Monitoring:** Track claude-commander releases, test with new versions

---

### Risk 3: Deep Accordion Nesting Performance

**Risk:** A project with many agents, each with many tasks and turns, could create a very large DOM when fully expanded.

**Impact:** Medium (UI slowdown, browser memory issues)

**Mitigation:**

- Lazy loading ensures only expanded sections are in DOM
- Pagination for agents/tasks with high counts (>50)
- Collapsing parent removes children from DOM
- Consider virtual scrolling if pagination insufficient

**Monitoring:** Track page performance metrics, DOM node counts

---

### Risk 4: SSE Event Volume

**Risk:** A highly active project could generate many SSE events, causing frequent DOM updates while user is reading.

**Impact:** Low (distracting, but not breaking)

**Mitigation:**

- Debounce accordion updates (batch every 2 seconds)
- Only update sections that are currently expanded
- SSE filter by project_id reduces irrelevant events

**Monitoring:** Track SSE event frequency per project

---

### Risk 5: Bookmarked URLs Breaking

**Risk:** Users bookmark project show URLs, then rename the project. The old URL returns 404.

**Impact:** Low (single-user tool, easy to re-navigate)

**Mitigation:**

- Accepted trade-off per workshop decision
- Users can navigate from projects list
- Could add redirect table in future if needed

**Monitoring:** Track 404 responses for `/projects/<slug>` pattern

---

### Risk 6: tmux Dependency

**Risk:** Users must install tmux and launch Claude Code sessions inside tmux panes. This changes the workflow.

**Impact:** Medium (requires setup change, but one-time)

**Mitigation:**

- Clear documentation for tmux setup
- iTerm2's native tmux integration preserves terminal ergonomics
- Recommended iTerm2 setting documented
- Plain iTerm2 tabs still work for monitoring (just not respond)

**Monitoring:** Track respond failures due to missing tmux_pane_id

---

### Risk 7: tmux Session Dimension Sharing

**Risk:** All windows within a tmux session share dimensions. Resizing affects all panes.

**Impact:** Low (use one tmux session per agent as workaround)

**Mitigation:**

- Document recommendation: one tmux session per Claude Code agent
- Multiple iTerm2 windows can each attach to different tmux sessions
- This is a tmux limitation, not a Headspace issue

**Monitoring:** User feedback on workflow friction

---

### Risk 8: Frustration Metric Interpretation Change

**Risk:** Users accustomed to sum-based frustration display may be confused by switch to average.

**Impact:** Low (new metric is more intuitive once understood)

**Mitigation:**

- Tooltip on frustration values explaining "average per scored turn"
- Fixed 0-10 scale makes interpretation obvious
- Threshold coloring provides immediate visual meaning

**Monitoring:** User feedback on metric clarity

---

### Risk 9: 3-Hour Rolling Window Performance

**Risk:** Computing 3-hour rolling frustration average may be slower than existing 30-minute window.

**Impact:** Low (query is still bounded, runs periodically not on-demand)

**Mitigation:**

- Index on timestamp column
- Periodic computation (not real-time)
- Same query pattern as existing windows, just wider range

**Monitoring:** Track headspace recalculation duration

---

### Risk 10: Kanban Layout Complexity on Small Viewports

**Risk:** Five-column Kanban layout may be difficult to use on tablet or narrow viewports.

**Impact:** Medium (reduces usability on smaller screens)

**Mitigation:**

- Horizontal scroll for columns on narrow viewports
- Responsive breakpoints collapse to fewer visible columns
- Alternative list view remains available via sort toggle
- NFR2 specifies tablet (768px) as minimum supported width

**Monitoring:** User feedback on mobile/tablet experience

---

### Risk 11: High Task Volume Dense Layouts

**Risk:** Projects with many concurrent tasks could create dense, hard-to-read Kanban columns.

**Impact:** Low (expected typical load is <20 tasks)

**Mitigation:**

- Scrollable columns for overflow
- Completed tasks collapse to accordions
- Priority ordering surfaces important tasks at top
- Pagination pattern available if needed (like accordion lazy loading)

**Monitoring:** Track max concurrent tasks per project

---

### Risk 12: Immediate Frustration Metric Interpretation

**Risk:** Users accustomed to aggregated frustration may be confused by switch to immediate (last 10 turns).

**Impact:** Low (new metric is more actionable once understood)

**Mitigation:**

- Tooltip on frustration values explaining "last 10 turns"
- Consistent across all views (dashboard, activity, headspace)
- Aligns with existing headspace rolling-10 window

**Monitoring:** User feedback on metric clarity

---

### Risk 13: Popover Positioning Edge Cases

**Risk:** Help popovers may overflow viewport on edge cases (field near screen edge, very small viewport).

**Impact:** Low (affects minority of use cases)

**Mitigation:**

- Smart positioning logic that flips popover direction
- FR14 specifies popovers must avoid viewport overflow
- Test at minimum supported viewport width (640px)
- Fall back to centered modal if positioning fails

**Monitoring:** Track popover positioning errors in JS console

---

### Risk 14: Documentation Maintenance Burden

**Risk:** Per-field configuration documentation must be maintained as config schema evolves.

**Impact:** Medium (documentation can drift out of sync)

**Mitigation:**

- Documentation co-located in CONFIG_SCHEMA (description field)
- Help page generated/validated from schema where possible
- Documentation updates included in config change PRDs
- Regular audit as part of Epic planning

**Monitoring:** Track undocumented config fields

---

## Success Metrics

From Epic 5 Acceptance Criteria:

### Test Case 1: Input Bridge

**Setup:** Agent in AWAITING_INPUT state with permission question, commander socket available.

**Success:**

- ✅ Quick-action buttons appear for numbered options
- ✅ Click quick-action button → response sent
- ✅ Free-text input available
- ✅ Send free-text → response sent
- ✅ Visual feedback on success
- ✅ Error message on failure
- ✅ Turn record created for response
- ✅ State transitions to PROCESSING
- ✅ No commander socket → input widget hidden

---

### Test Case 2: Project Show Core

**Setup:** Existing project with waypoint, brain reboot, and progress summary.

**Success:**

- ✅ Navigate to `/projects/<slug>` → see full project detail
- ✅ Metadata displayed: name, path, GitHub (linked), branch, description, created
- ✅ Inference status shows active or paused
- ✅ Edit opens form, saves changes, updates display
- ✅ Delete shows confirmation, deletes, redirects
- ✅ Pause/Resume toggles immediately
- ✅ Regenerate Description updates field
- ✅ Refetch GitHub Info updates repo/branch
- ✅ Waypoint section shows markdown
- ✅ Brain reboot shows with timestamp and time-ago
- ✅ Brain reboot Regenerate and Export work
- ✅ Progress summary shows with Regenerate
- ✅ Projects list: names are links
- ✅ Projects list: no action buttons

---

### Test Case 3: Project Show Tree & Metrics

**Setup:** Project with multiple agents, tasks, turns, and activity history.

**Success:**

- ✅ Agents accordion collapsed by default with count badge
- ✅ Expand Agents → fetches and shows all agents
- ✅ Agent rows show state, ID, score, timing
- ✅ Ended agents visually distinguished
- ✅ Click agent → Tasks expand (lazy loaded)
- ✅ Task rows show state, instruction, summary, timing, turns
- ✅ Click task → Turns expand (lazy loaded)
- ✅ Turn rows show actor, intent, summary, frustration
- ✅ Frustration >= 4 highlighted yellow
- ✅ Frustration >= 7 highlighted red
- ✅ Loading indicator during fetch
- ✅ Error state with retry on failure
- ✅ Activity metrics show with week default
- ✅ Day/week/month toggle works
- ✅ Period navigation works
- ✅ Summary cards show correct data
- ✅ Time-series chart displays
- ✅ Archive history lists items
- ✅ Inference summary shows totals
- ✅ SSE updates expanded sections

---

### Test Case 4: End-to-End Epic 5 Flow

**Setup:** Fresh Epic 5 deployment with Epic 4 complete.

**Success:**

- ✅ Start Claude Code session in tmux → agent appears on dashboard
- ✅ Agent asks permission question → amber card, input widget appears
- ✅ Click quick-action button → response sent via tmux, agent resumes
- ✅ Navigate to projects list → click project name
- ✅ Project show page displays with all sections
- ✅ Expand Agents accordion → see agents with details
- ✅ Drill into tasks and turns → see full hierarchy
- ✅ Frustration scores highlighted appropriately
- ✅ Activity metrics show project-specific data
- ✅ Archive history shows previous versions
- ✅ Edit project name → slug updates, page URL changes
- ✅ SSE events update page in real-time

---

### Test Case 5: tmux Bridge

**Setup:** Claude Code session running inside a tmux pane, attached via iTerm2 `-CC`.

**Success:**

- ✅ Hook scripts include `tmux_pane` in payloads
- ✅ Agent has `tmux_pane_id` populated from hooks
- ✅ Dashboard shows input widget when agent in AWAITING_INPUT
- ✅ Click quick-action button → tmux send-keys delivers text
- ✅ Claude Code receives text and Enter → prompt submitted
- ✅ Dual input works (typing in terminal + dashboard respond)
- ✅ Availability checks detect pane existence
- ✅ Availability changes broadcast via SSE
- ✅ Clear error when tmux not installed
- ✅ Clear error when pane not found
- ✅ Clear error when no pane ID on agent

---

### Test Case 6: Activity Frustration Display

**Setup:** Activity page with historical turn data including frustration scores.

**Success:**

- ✅ Overall metric card shows average frustration (0-10 decimal)
- ✅ Project metric cards show average frustration
- ✅ Agent rows show average frustration
- ✅ Values colored green < 4, yellow 4-7, red > 7
- ✅ "—" displayed for periods with no scored turns
- ✅ Chart frustration line shows per-bucket average
- ✅ Chart right Y-axis fixed at 0-10
- ✅ Chart line has gaps for zero-turn buckets
- ✅ Frustration state widget displays three windows
- ✅ Widget values update via SSE
- ✅ Widget hidden when headspace disabled
- ✅ Hover tooltips show threshold boundaries
- ✅ Config UI allows editing thresholds

---

### Test Case 7: Dashboard Restructure

**Setup:** Dashboard with multiple active agents across projects, some with active tasks, some idle.

**Success:**

- ✅ Agent cards display two-character hero identity (large) + trailing chars (small)
- ✅ No `#` prefix on any agent ID displays
- ✅ Hero style appears on dashboard, projects, activity, logging pages
- ✅ Logging agent filter dropdown shows format: `0a - 0a5510d4`
- ✅ Card header shows: Hero Identity, Project, Uptime, Active indicator (right-aligned)
- ✅ Kanban view is first/default sort option
- ✅ Tasks appear in correct lifecycle state columns (IDLE, COMMANDED, PROCESSING, AWAITING_INPUT, COMPLETE)
- ✅ Idle agents (no tasks) appear in IDLE column
- ✅ Same agent can appear in multiple columns simultaneously
- ✅ Completed tasks collapse to accordions in scrollable COMPLETE column
- ✅ Priority ordering within columns when prioritisation enabled
- ✅ Multiple projects display as horizontal sections
- ✅ Activity metrics bar visible below menu bar
- ✅ Metrics show: Total Turns, Turns/Hr, Avg Turn Time, Active Agents, Frustration
- ✅ Dashboard metrics update in real-time via SSE
- ✅ Frustration shows immediate (last 10 turns) value

---

### Test Case 8: Configuration Help System

**Setup:** Config page with all sections expanded, help page available.

**Success:**

- ✅ `tmux_bridge` section visible with all fields
- ✅ `dashboard` section visible with all fields
- ✅ `archive` section visible with all fields
- ✅ Missing `openrouter` fields visible (retry, priority_scoring)
- ✅ Missing `headspace` flow detection fields visible
- ✅ Every section header has clickable help icon
- ✅ Every field label has clickable help icon
- ✅ Clicking help icon opens popover
- ✅ Popover shows: description, default value, range (numeric), "Learn more" link
- ✅ Only one popover visible at a time (opening new closes previous)
- ✅ Popover dismisses on: click outside, Escape key, click icon again
- ✅ "Learn more" link navigates to `/help/configuration#section`
- ✅ Help page scrolls to target section on anchor navigation
- ✅ Target section highlights briefly on anchor navigation
- ✅ `docs/help/configuration.md` contains all field documentation
- ✅ Documentation includes: what field does, when to change, consequences

---

## Recommended PRD Generation Order

All 7 PRDs have been generated. Implementation order:

### Phase 1: Input Bridge — DONE

1. **input-bridge** (`docs/prds/bridge/done/e5-s1-input-bridge-prd.md`) — Commander service, response endpoint, dashboard input UI

**Rationale:** Enables dashboard response capability, establishes respond pipeline.

---

### Phase 2: tmux Bridge — DONE

2. **tmux-bridge** (`docs/prds/bridge/done/e5-s4-tmux-bridge-prd.md`) — Replace commander socket with tmux send-keys

**Rationale:** Fixes transport layer — commander socket doesn't work with Claude Code's Ink TUI. Completed, Input Bridge now functional.

---

### Phase 3: Project Show Core

3. **project-show-core** (`docs/prds/ui/e5-s2-project-show-core-prd.md`) — Slug routing, show page template, metadata display, control actions

**Rationale:** Creates the project show page foundation that E5-S3 extends.

---

### Phase 4: Project Show Tree & Metrics

4. **project-show-tree** (`docs/prds/ui/e5-s3-project-show-tree-and-metrics-prd.md`) — Accordion tree, lazy loading, activity metrics, archive history, SSE updates

**Rationale:** Builds on show page foundation, adds data exploration and embedded metrics.

---

### Phase 5: Activity Frustration Display

5. **activity-frustration** (`docs/prds/ui/e5-s5-activity-frustration-display-prd.md`) — Average-based frustration display, frustration state widget

**Rationale:** Improves frustration metrics interpretation on activity page, adds at-a-glance frustration state.

---

### Phase 6: Dashboard Restructure — DONE

6. **dashboard-restructure** (`docs/prds/ui/done/e5-s6-dashboard-restructure-prd.md`) — Agent hero style, Kanban layout, dashboard activity metrics

**Rationale:** Introduces agent visual identity system, task-flow Kanban view, and surfaces key metrics on the dashboard.

---

### Phase 7: Configuration Help System — DONE

7. **config-help-system** (`docs/prds/ui/done/e5-s7-config-help-system-prd.md`) — Config/UI parity, help icons, popovers, documentation

**Rationale:** Closes configuration visibility gap, adds self-documenting help system for all settings.

---

## Future Roadmap (Voice Bridge Phases 2-3)

Epic 5 Sprint 1 (Input Bridge) is Phase 1 of the Voice Bridge vision. Future phases are out of scope for Epic 5 but documented here for planning:

### Phase 2: Voice Capture (Future)

- Web Speech API integration for voice-to-text
- Voice transcription feeds into commander service
- "Push to talk" or voice activity detection modes
- Dashboard microphone button/indicator

### Phase 3: Voice Output (Future)

- Text-to-speech for agent responses
- Summarisation service generates spoken summaries
- Hands-free monitoring loop
- Audio output for notifications/alerts

**Reference:** See `docs/ideas/VOICE_BRIDGE_OUTLINE_PROMPT.md` for the original Voice Bridge vision.

---

## Document History

| Version | Date       | Author          | Changes                                         |
| ------- | ---------- | --------------- | ----------------------------------------------- |
| 1.0     | 2026-02-04 | PM Agent (John) | Initial detailed roadmap for Epic 5 (3 sprints) |
| 1.1     | 2026-02-04 | PM Agent (John) | Added E5-S4 (tmux Bridge) and E5-S5 (Activity Frustration Display), now 5 sprints |
| 1.2     | 2026-02-05 | PM Agent (John) | Added E5-S6 (Dashboard Restructure) and E5-S7 (Config Help System), now 7 sprints |

---

**End of Epic 5 Detailed Roadmap**
