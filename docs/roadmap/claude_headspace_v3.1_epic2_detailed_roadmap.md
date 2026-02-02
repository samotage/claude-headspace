# Epic 2 Detailed Roadmap: UI Polish & Documentation

**Project:** Claude Headspace v3.1  
**Epic:** Epic 2 — UI Polish & Documentation  
**Author:** PM Agent (John)  
**Status:** Roadmap — Baseline for PRD Generation  
**Date:** 2026-01-29

---

## Executive Summary

This document serves as the **high-level roadmap and baseline** for Epic 2 implementation. It breaks Epic 2 into 4 logical sprints (1 sprint = 1 PRD = 1 OpenSpec change), identifies subsystems that require OpenSpec PRDs, and provides the foundation for generating detailed Product Requirements Documents for each subsystem.

**Epic 2 Goal:** Polish the user experience with configuration UI, waypoint editing, help system, and native macOS notifications.

**Epic 2 Value Proposition:**

- **Config UI Tab** — Edit application settings via web UI instead of manually editing YAML
- **Waypoint Editing** — Manage project waypoints (the path ahead) directly from the dashboard
- **Help System** — Searchable documentation for users to understand and use the system
- **macOS Notifications** — Native system notifications when tasks complete or need input

**Success Criteria:**

- Edit `config.yaml` via web UI, changes persist and apply
- Edit `waypoint.md` via web UI for any monitored project
- Search help documentation, find relevant topics quickly
- Receive macOS notification banner when task completes or needs input
- Toggle notification preferences per event type

**Architectural Foundation:** Builds on Epic 1's Flask application, database, SSE system, and dashboard UI. Epic 2 adds configuration management, file editing capabilities, documentation rendering, and macOS integration.

**Dependency:** Epic 1 must be complete before Epic 2 begins.

---

## Epic 2 Story Mapping

| Story ID | Story Name                                 | Subsystem             | PRD Directory  | Sprint | Priority |
| -------- | ------------------------------------------ | --------------------- | -------------- | ------ | -------- |
| E2-S1    | Edit application settings via web UI       | `config-ui`           | ui/            | 1      | P1       |
| E2-S2    | Edit project waypoints via web UI          | `waypoint-editor`     | ui/            | 2      | P1       |
| E2-S3    | Searchable help and documentation system   | `help-system`         | ui/            | 3      | P1       |
| E2-S4    | Native macOS notifications for task events | `macos-notifications` | notifications/ | 4      | P1       |

---

## Sprint Breakdown

### Sprint 1: Config UI Tab (E2-S1)

**Goal:** Web-based UI for editing `config.yaml` settings without manual file editing.

**Duration:** 1 week  
**Dependencies:** Epic 1 complete (Flask app, dashboard, tab navigation)

**Deliverables:**

- Config tab HTML template with Tailwind CSS styling
- Form-based UI for editing config.yaml sections
- Server-side YAML parsing and serialization
- Validation before save (type checking, required fields)
- Persist changes to `config.yaml` file
- Handle nested YAML structures (server, database, file_watcher, etc.)
- Error handling with user-friendly messages
- Success feedback (toast notification)
- Auto-reload configuration or manual refresh button
- API endpoints: GET/POST `/api/config`

**Subsystem Requiring PRD:**

1. `config-ui` — Config tab form, YAML parsing, validation, persistence

**PRD Location:** `docs/prds/ui/e2-s1-config-ui-prd.md`

**Stories:**

- E2-S1: Edit application settings via web UI

**Technical Decisions Required:**

- Form-based UI vs raw YAML editor — **recommend form-based for usability**
- Which config sections to expose (all vs subset) — **recommend all sections**
- Config reload: auto-reload vs manual restart — **recommend manual refresh button**
- Validation: client-side vs server-side — **recommend server-side with client hints**
- Sensitive fields (passwords): show/hide toggle — **recommend masked with reveal**

**Risks:**

- Invalid config breaking application startup
- YAML serialization changing formatting/comments
- Users not understanding config field meanings
- Race conditions if multiple users edit simultaneously

**Acceptance Criteria:**

- Config tab displays all `config.yaml` sections as form fields
- Edit a field (e.g., `server.port`) → save → value persisted to file
- Invalid value (e.g., non-numeric port) → validation error shown
- Nested structures (database._, file_watcher._) editable
- Password fields masked by default with reveal toggle
- Success toast on save, error message on failure
- Refresh button applies new config without server restart (where possible)

---

### Sprint 2: Waypoint Editing UI (E2-S2)

**Goal:** Web-based UI for editing project waypoints (`waypoint.md`) directly from the dashboard.

**Duration:** 1 week  
**Dependencies:** E2-S1 complete (establishes editing UI patterns), Epic 1 Project model

**Deliverables:**

- Waypoint editor tab or modal
- Project selector dropdown (which project's waypoint to edit)
- Markdown textarea or rich editor for waypoint content
- Load `waypoint.md` from project's `docs/brain_reboot/` directory
- Save changes to project directory
- Create `waypoint.md` if it doesn't exist (with template)
- Create `docs/brain_reboot/` directory structure if missing
- Archive previous waypoint on save (to `archive/waypoint_YYYY-MM-DD.md`)
- Preview rendered markdown
- API endpoints: GET/POST `/api/projects/<id>/waypoint`

**Subsystem Requiring PRD:**

2. `waypoint-editor` — Waypoint editor UI, project selection, markdown editing, archiving

**PRD Location:** `docs/prds/ui/e2-s2-waypoint-editor-prd.md`

**Stories:**

- E2-S2: Edit project waypoints via web UI

**Technical Decisions Required:**

- Editor type: plain textarea vs rich markdown editor — **recommend textarea with preview**
- Waypoint location: standardized `docs/brain_reboot/waypoint.md` — **decided in conceptual overview**
- Archive on every save vs only on significant changes — **recommend archive on every save**
- Template for new waypoints: structured sections (next_up, upcoming, later, not_now) — **per conceptual overview**
- Project path access: verify write permissions before allowing edit

**Risks:**

- File permission errors writing to project directories
- Project path not accessible (network drive, permissions)
- Conflicting edits if waypoint edited externally
- Large waypoint files causing slow load/save

**Acceptance Criteria:**

- Select project from dropdown → waypoint.md content loads in editor
- Edit content → save → changes written to project's `docs/brain_reboot/waypoint.md`
- Previous version archived to `archive/waypoint_YYYY-MM-DD.md`
- Project without waypoint → create with template on first save
- Preview button shows rendered markdown
- Permission errors display actionable message
- Works for all monitored projects from Epic 1

---

### Sprint 3: Help/Documentation System (E2-S3)

**Goal:** Searchable help system for users to understand and use Claude Headspace.

**Duration:** 1 week  
**Dependencies:** Epic 1 complete (dashboard, tab navigation)

**Deliverables:**

- Help tab or searchable modal (accessible via `?` keyboard shortcut)
- Markdown-based documentation source files
- Search index for quick lookup (client-side full-text search)
- Navigation/table of contents
- Documentation topics covering:
  - Getting started / Quick start
  - Dashboard overview
  - Objective setting
  - Project monitoring
  - Agent states and lifecycle
  - Configuration options
  - Waypoint editing
  - Keyboard shortcuts
  - Troubleshooting
- Links to external documentation where appropriate
- API endpoint: GET `/api/help/search?q=<query>`

**Subsystem Requiring PRD:**

3. `help-system` — Help tab/modal, documentation source, search functionality

**PRD Location:** `docs/prds/ui/e2-s3-help-system-prd.md`

**Stories:**

- E2-S3: Searchable help and documentation system

**Technical Decisions Required:**

- Help location: dedicated tab vs modal overlay — **recommend modal (less navigation)**
- Search implementation: client-side (lunr.js) vs server-side — **recommend client-side for speed**
- Documentation format: markdown files vs database content — **recommend markdown files**
- Documentation location: `docs/help/` directory in Claude Headspace repo
- Keyboard shortcut: `?` to open help — **recommend this for discoverability**

**Risks:**

- Documentation becoming stale as features change
- Search not finding relevant results (poor indexing)
- Help content too technical or too vague
- Modal interfering with other UI elements

**Acceptance Criteria:**

- Press `?` → help modal opens
- Type search query → relevant topics shown instantly
- Click topic → full documentation displayed
- Table of contents navigable
- All major features documented (dashboard, objective, config, waypoint)
- Documentation renders markdown correctly (headings, code blocks, links)
- Close modal with Escape or click outside
- Help tab also accessible from navigation (fallback for keyboard-less users)

---

### Sprint 4: macOS Notifications (E2-S4)

**Goal:** Native macOS system notifications when tasks complete or need user input.

**Duration:** 1 week  
**Dependencies:** Epic 1 complete (SSE event stream, task state machine)

**Deliverables:**

- macOS notification integration via `terminal-notifier` or native APIs
- Trigger notifications on specific events:
  - `task_complete` — Agent finished a task
  - `awaiting_input` — Agent needs user response
- Notification preferences stored in `config.yaml`
- Enable/disable notifications globally
- Enable/disable per event type
- Click notification to:
  - Focus dashboard in browser
  - Optionally focus specific agent's iTerm window
- Notification service integrated with SSE event stream
- Sound options (default macOS sound, custom, or silent)
- API endpoints: GET/PUT `/api/notifications/preferences`

**Subsystem Requiring PRD:**

4. `macos-notifications` — Notification service, preferences, terminal-notifier integration

**PRD Location:** `docs/prds/notifications/e2-s4-macos-notifications-prd.md`

**Stories:**

- E2-S4: Native macOS notifications for task events

**Technical Decisions Required:**

- Notification library: `terminal-notifier` (Homebrew) vs `NSUserNotification` (native) — **recommend terminal-notifier for simplicity**
- Click action: open dashboard vs focus agent window — **recommend dashboard with agent highlight**
- Rate limiting: prevent notification spam during rapid state changes — **recommend 5-second cooldown per agent**
- Sound: enable by default or silent — **recommend default macOS sound**
- Notification grouping: group by project or show individual — **recommend individual with project context**

**Risks:**

- `terminal-notifier` not installed (Homebrew dependency)
- macOS notification permissions denied
- Notification spam if many agents active
- Click action not working (browser focus issues)

**Acceptance Criteria:**

- Task completes → macOS notification banner appears
- Agent enters `awaiting_input` → macOS notification appears
- Click notification → browser focuses, dashboard shows relevant agent
- Preferences UI: toggle notifications on/off globally
- Preferences UI: toggle per event type (task_complete, awaiting_input)
- Notifications respect rate limiting (no spam)
- Works on macOS Monterey, Ventura, Sonoma, Sequoia
- Clear error message if `terminal-notifier` not installed

---

## Subsystems Requiring OpenSpec PRDs

The following 4 subsystems need detailed PRDs created via OpenSpec. Each PRD will be generated as a separate change proposal and validated before implementation.

### PRD Directory Structure

```
docs/prds/
├── ui/                    # User interface components
│   ├── e2-s1-config-ui-prd.md
│   ├── e2-s2-waypoint-editor-prd.md
│   └── e2-s3-help-system-prd.md
└── notifications/         # Notification system
    └── e2-s4-macos-notifications-prd.md
```

---

### 1. Config UI

**Subsystem ID:** `config-ui`  
**Sprint:** E2-S1  
**Priority:** P1  
**PRD Location:** `docs/prds/ui/e2-s1-config-ui-prd.md`

**Scope:**

- Config tab HTML template with form UI
- YAML parsing and serialization
- Form field generation from config structure
- Validation before save
- Persist changes to `config.yaml`
- Error handling and success feedback
- Configuration refresh mechanism

**Key Requirements:**

- Must display all config.yaml sections as editable form fields
- Must validate input before saving (type checking, required fields)
- Must handle nested YAML structures correctly
- Must preserve YAML formatting where possible
- Must show clear error messages for invalid input
- Must provide success feedback on save
- Must handle sensitive fields (passwords) appropriately

**OpenSpec Spec:** `openspec/specs/config-ui/spec.md`

**Related Files:**

- `templates/config.html` (new)
- `static/js/config.js` (new)
- `src/routes/config.py` (new)
- `src/services/config_editor.py` (new)
- `config.yaml` (read/write target)

**Data Model Changes:**

None (reads/writes existing `config.yaml`)

**Dependencies:** Epic 1 complete (Flask app, dashboard tabs)

**Acceptance Tests:**

- Config tab renders all config sections
- Edit field, save → value persisted to file
- Invalid value → validation error
- Password fields masked
- Success toast on save

---

### 2. Waypoint Editor

**Subsystem ID:** `waypoint-editor`  
**Sprint:** E2-S2  
**Priority:** P1  
**PRD Location:** `docs/prds/ui/e2-s2-waypoint-editor-prd.md`

**Scope:**

- Waypoint editor tab or modal
- Project selector dropdown
- Markdown textarea with preview
- Load waypoint from project directory
- Save waypoint to project directory
- Create waypoint if missing (with template)
- Archive previous waypoint on save
- Directory structure creation

**Key Requirements:**

- Must allow selection of any monitored project
- Must load `waypoint.md` from `docs/brain_reboot/` in project directory
- Must save changes back to project directory
- Must archive previous version before saving new
- Must create directory structure if missing
- Must provide markdown preview
- Must handle file permission errors gracefully
- Must use standard waypoint template for new files

**OpenSpec Spec:** `openspec/specs/waypoint-editor/spec.md`

**Related Files:**

- `templates/waypoint.html` (new) or integrated into existing template
- `static/js/waypoint.js` (new)
- `src/routes/waypoint.py` (new)
- `src/services/waypoint_editor.py` (new)

**Data Model Changes:**

None (reads/writes files in external project directories)

**Waypoint Template:**

```markdown
# Waypoint

## Next Up

<!-- Immediate next steps -->

## Upcoming

<!-- Coming soon -->

## Later

<!-- Future work -->

## Not Now

<!-- Parked/deprioritised -->
```

**Dependencies:** E2-S1 complete (editing patterns), Epic 1 Project model

**Acceptance Tests:**

- Select project → waypoint loads
- Edit and save → file updated
- Previous version archived
- New project → template created
- Preview renders markdown
- Permission errors handled

---

### 3. Help System

**Subsystem ID:** `help-system`  
**Sprint:** E2-S3  
**Priority:** P1  
**PRD Location:** `docs/prds/ui/e2-s3-help-system-prd.md`

**Scope:**

- Help modal or tab UI
- Markdown documentation source files
- Client-side search functionality
- Table of contents navigation
- Keyboard shortcut activation
- Documentation content for all features

**Key Requirements:**

- Must provide searchable documentation
- Must be accessible via `?` keyboard shortcut
- Must render markdown documentation
- Must support full-text search across all docs
- Must have navigable table of contents
- Must document all major features
- Must be easy to update as features change

**OpenSpec Spec:** `openspec/specs/help-system/spec.md`

**Related Files:**

- `templates/partials/_help_modal.html` (new)
- `static/js/help.js` (new)
- `docs/help/` directory (new, documentation source)
- `docs/help/index.md` (table of contents)
- `docs/help/getting-started.md`
- `docs/help/dashboard.md`
- `docs/help/objective.md`
- `docs/help/configuration.md`
- `docs/help/waypoints.md`
- `docs/help/troubleshooting.md`
- `src/routes/help.py` (new, serves help content)

**Data Model Changes:**

None (reads markdown files)

**Dependencies:** Epic 1 complete (dashboard)

**Acceptance Tests:**

- Press `?` → help modal opens
- Search returns relevant results
- Topics render correctly
- Navigation works
- All features documented
- Modal closes on Escape

---

### 4. macOS Notifications

**Subsystem ID:** `macos-notifications`  
**Sprint:** E2-S4  
**Priority:** P1  
**PRD Location:** `docs/prds/notifications/e2-s4-macos-notifications-prd.md`

**Scope:**

- `terminal-notifier` integration
- Notification service
- Event-to-notification mapping
- Notification preferences
- Rate limiting
- Click-to-action handling

**Key Requirements:**

- Must send macOS notifications on task_complete and awaiting_input events
- Must integrate with SSE event stream
- Must allow enable/disable globally and per event type
- Must rate limit to prevent spam
- Must handle click action (focus dashboard)
- Must detect if `terminal-notifier` installed
- Must provide clear setup instructions if not installed

**OpenSpec Spec:** `openspec/specs/macos-notifications/spec.md`

**Related Files:**

- `src/services/notification_service.py` (new)
- `src/routes/notifications.py` (new)
- `templates/partials/_notification_preferences.html` (new)
- `static/js/notifications.js` (new)
- `config.yaml` (add notifications section)

**Data Model Changes:**

Add to `config.yaml`:

```yaml
notifications:
  enabled: true
  sound: true
  events:
    task_complete: true
    awaiting_input: true
  rate_limit_seconds: 5
```

**Dependencies:** Epic 1 complete (SSE, task state machine)

**Acceptance Tests:**

- Task completes → notification appears
- Awaiting input → notification appears
- Preferences toggle works
- Rate limiting prevents spam
- Click opens dashboard
- Missing terminal-notifier detected

---

## Sprint Dependencies & Critical Path

```
[Epic 1 Complete]
        │
        ▼
    E2-S1 (Config UI)
        │
        └──▶ E2-S2 (Waypoint Editor)
                │
                └──▶ [UI editing patterns established]

    E2-S3 (Help System) ──────────────┐
        │                              │
    E2-S4 (macOS Notifications) ──────┤
                                       │
                                       ▼
                               [Epic 2 Complete]
```

**Critical Path:** Epic 1 → E2-S1 → E2-S2

**Parallel Tracks:**

- E2-S3 (Help) can run in parallel with E2-S1 and E2-S2 (independent)
- E2-S4 (Notifications) can run in parallel with E2-S2 and E2-S3 (only needs Epic 1 SSE)

**Recommended Sequence:**

1. E2-S1 (Config UI) — establishes form/editing patterns
2. E2-S2 (Waypoint Editor) — uses patterns from E2-S1
3. E2-S3 (Help System) — can start anytime after Epic 1
4. E2-S4 (macOS Notifications) — can start anytime after Epic 1

**Total Duration:** 3-4 weeks

---

## Technical Decisions Made

### Decision 1: Form-Based Config Editor

**Decision:** Use form-based UI for config editing (not raw YAML editor).

**Rationale:**

- More user-friendly (no YAML syntax knowledge required)
- Enables field-level validation
- Can show field descriptions and hints
- Prevents YAML formatting errors

**Impact:**

- Need to generate form fields from config structure
- Need to handle all YAML types (string, number, boolean, nested objects)
- May not preserve comments in YAML file

---

### Decision 2: Waypoint Location Standardized

**Decision:** Waypoint stored at `docs/brain_reboot/waypoint.md` in each project.

**Rationale:**

- Consistent location across all projects
- Co-located with progress_summary
- Part of repo artifacts (version controlled)
- Defined in conceptual overview

**Impact:**

- Claude Headspace needs write access to project directories
- May need to create directory structure

---

### Decision 3: Client-Side Help Search

**Decision:** Use client-side search (e.g., lunr.js) instead of server-side.

**Rationale:**

- Instant results (no network latency)
- Works offline
- Simpler implementation
- Documentation size is small enough for client-side indexing

**Impact:**

- Search index built on page load
- Documentation must be loaded into browser
- May need lazy loading for large doc sets

---

### Decision 4: terminal-notifier for macOS Notifications

**Decision:** Use `terminal-notifier` (Homebrew package) for macOS notifications.

**Rationale:**

- Simple subprocess call (no native API complexity)
- Reliable and well-maintained
- Supports click actions (open URL)
- Users likely have Homebrew already

**Impact:**

- Homebrew dependency (users must install)
- Need to detect if installed and guide users
- subprocess call for each notification

---

### Decision 5: Markdown Textarea for Waypoint Editor

**Decision:** Use plain textarea with markdown preview (not rich editor).

**Rationale:**

- Simpler implementation
- Users familiar with markdown syntax
- Rich editors can be buggy
- Preview provides visual feedback

**Impact:**

- Users must know markdown basics
- Split-pane or toggle preview mode

---

## Open Questions

### 1. Config Reload Mechanism

**Question:** How should config changes take effect?

**Options:**

- **Option A:** Auto-reload on save (hot reload Flask config)
- **Option B:** Manual restart required (safest, clearest)
- **Option C:** Refresh button that applies safe changes, warns about restart-required changes

**Recommendation:** Option C — refresh button with clear feedback about what requires restart.

**Decision needed by:** E2-S1 implementation

---

### 2. Waypoint Conflict Resolution

**Question:** How to handle waypoint edited externally while editing in UI?

**Options:**

- **Option A:** Last write wins (simple, may lose changes)
- **Option B:** Detect conflict and prompt user (merge or overwrite)
- **Option C:** Lock file while editing (complex, may leave stale locks)

**Recommendation:** Option B — detect conflict by checking file modification time before save.

**Decision needed by:** E2-S2 implementation

---

### 3. Help Content Maintenance

**Question:** Who maintains help documentation and when?

**Options:**

- **Option A:** Update help docs as part of each feature PRD
- **Option B:** Dedicated documentation sprint after features complete
- **Option C:** Auto-generate from code/comments where possible

**Recommendation:** Option A — include help updates in each feature PRD for freshness.

**Decision needed by:** E2-S3 implementation

---

### 4. Notification Click Action

**Question:** What should clicking a notification do?

**Options:**

- **Option A:** Focus browser, show dashboard (simple)
- **Option B:** Focus browser, highlight specific agent (better UX)
- **Option C:** Focus agent's iTerm window directly (most direct)

**Recommendation:** Option B — focus dashboard and scroll to/highlight the relevant agent.

**Decision needed by:** E2-S4 implementation

---

## Risks & Mitigation

### Risk 1: Config Editing Breaking Application

**Risk:** Invalid config values may prevent application from starting.

**Impact:** High (users locked out of application)

**Mitigation:**

- Server-side validation before save
- Test config loading before persisting
- Keep backup of previous config
- Clear error messages explaining what's wrong
- "Reset to defaults" button

**Monitoring:** Log config validation errors, track failed saves

---

### Risk 2: File Permission Issues in Project Directories

**Risk:** Claude Headspace may not have write access to project directories for waypoint editing.

**Impact:** Medium (waypoint editing fails for some projects)

**Mitigation:**

- Check permissions before showing edit UI
- Clear error message with permission fix instructions
- Show read-only view if can't write
- Document required permissions in help system

**Monitoring:** Track permission errors per project

---

### Risk 3: terminal-notifier Not Installed

**Risk:** Users may not have `terminal-notifier` installed via Homebrew.

**Impact:** Medium (notifications don't work until installed)

**Mitigation:**

- Detect if installed on startup
- Show installation instructions in preferences UI
- Provide one-command install: `brew install terminal-notifier`
- Graceful degradation (notifications disabled if not available)
- Consider bundling or using native API as fallback

**Monitoring:** Track notification attempts vs deliveries

---

### Risk 4: Help Documentation Becoming Stale

**Risk:** Documentation may not reflect actual feature behavior after changes.

**Impact:** Low (user confusion, support burden)

**Mitigation:**

- Include doc updates in each feature PRD
- Review docs during release process
- Version documentation with releases
- User feedback mechanism ("Was this helpful?")

**Monitoring:** Track help search terms with no results (indicate gaps)

---

### Risk 5: Notification Spam

**Risk:** Many agents with rapid state changes may flood user with notifications.

**Impact:** Medium (user disables all notifications, misses important ones)

**Mitigation:**

- Rate limiting per agent (5-second cooldown)
- Aggregate notifications when multiple agents complete simultaneously
- Clear preference controls (enable/disable per event type)
- "Do Not Disturb" integration

**Monitoring:** Track notifications per minute, user disable rate

---

## Success Metrics

From Epic 2 Acceptance Criteria:

### Test Case 1: Config Editing

**Setup:** Open config tab.

**Success:**

- ✅ All config sections displayed as form fields
- ✅ Edit `server.port` → save → value persisted to `config.yaml`
- ✅ Enter invalid value → validation error shown
- ✅ Nested structures (database._, file_watcher._) editable
- ✅ Password fields masked with reveal toggle
- ✅ Success toast on save

---

### Test Case 2: Waypoint Editing

**Setup:** Open waypoint editor, select a project.

**Success:**

- ✅ Project dropdown shows all monitored projects
- ✅ Select project → `waypoint.md` loads in editor
- ✅ Edit content → save → file updated in project directory
- ✅ Previous version archived with timestamp
- ✅ New project (no waypoint) → template created on save
- ✅ Preview button renders markdown

---

### Test Case 3: Help Search

**Setup:** Press `?` to open help modal.

**Success:**

- ✅ Help modal opens on `?` keypress
- ✅ Type search query → relevant topics appear instantly
- ✅ Click topic → full documentation displayed
- ✅ Table of contents navigable
- ✅ All major features documented
- ✅ Modal closes on Escape

---

### Test Case 4: macOS Notifications

**Setup:** Enable notifications, run Claude Code task.

**Success:**

- ✅ Task completes → macOS notification banner appears
- ✅ Agent enters `awaiting_input` → notification appears
- ✅ Click notification → browser focuses, dashboard shows agent
- ✅ Preferences: toggle notifications on/off globally
- ✅ Preferences: toggle per event type works
- ✅ Rate limiting prevents spam (5-second cooldown)

---

### Test Case 5: End-to-End User Flow

**Setup:** Fresh Epic 2 deployment.

**Success:**

- ✅ Edit config via UI → application behavior changes
- ✅ Edit waypoint for project → file persisted in project repo
- ✅ Search help → find answer to question
- ✅ Complete task → notification received → click → dashboard focused

---

## Recommended PRD Generation Order

Generate OpenSpec PRDs in implementation order:

### Phase 1: Config UI (Week 1)

1. **config-ui** (`docs/prds/ui/e2-s1-config-ui-prd.md`) — Config tab form, YAML parsing, validation

**Rationale:** Establishes patterns for form-based editing UI that E2-S2 will reuse.

---

### Phase 2: Waypoint Editor (Week 2)

2. **waypoint-editor** (`docs/prds/ui/e2-s2-waypoint-editor-prd.md`) — Waypoint editor, project selection, markdown editing

**Rationale:** Uses editing patterns from E2-S1, depends on Project model from Epic 1.

---

### Phase 3: Help System (Week 2-3)

3. **help-system** (`docs/prds/ui/e2-s3-help-system-prd.md`) — Help modal, documentation source, search

**Rationale:** Can run in parallel with E2-S2, only depends on Epic 1 dashboard.

---

### Phase 4: macOS Notifications (Week 3-4)

4. **macos-notifications** (`docs/prds/notifications/e2-s4-macos-notifications-prd.md`) — Notification service, preferences, terminal-notifier

**Rationale:** Can run in parallel with E2-S2/E2-S3, depends on Epic 1 SSE event stream.

---

## Document History

| Version | Date       | Author          | Changes                                         |
| ------- | ---------- | --------------- | ----------------------------------------------- |
| 1.0     | 2026-01-29 | PM Agent (John) | Initial detailed roadmap for Epic 2 (4 sprints) |

---

**End of Epic 2 Detailed Roadmap**
