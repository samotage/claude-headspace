---
validation:
  status: valid
  validated_at: '2026-01-30T14:22:37+11:00'
---

## Product Requirements Document (PRD) — Brain Reboot Generation

**Project:** Claude Headspace v3.1
**Scope:** Epic 3, Sprint 5 — Context restoration via combined waypoint and progress summary, with staleness detection
**Author:** PRD Workshop (AI-assisted)
**Status:** Draft

---

## Executive Summary

When a developer manages multiple projects with AI agents, they inevitably context-switch. Returning to a project after days away means they've lost mental context — what was done, what's next, where things stand. Brain reboot solves this by combining two existing project artifacts — the waypoint (path ahead) and progress summary (what was accomplished) — into a single context restoration document, generated on demand from the dashboard.

This PRD defines the brain reboot generator, a dashboard modal for viewing the combined document, export and clipboard functionality for portability, and a staleness detection system that proactively flags projects needing attention. Staleness is based on time since last agent activity, classified into freshness tiers with visual indicators on the dashboard.

Brain reboot does not require LLM inference calls — it composes existing artifacts with formatting. It depends on E3-S4 (progress summary generation) for the progress summary content and the waypoint editor (Epic 2) for waypoint content. When either artifact is missing, the brain reboot gracefully shows what's available and indicates what's absent.

---

## 1. Context & Purpose

### 1.1 Context

Claude Headspace is a Kanban-style web dashboard for tracking Claude Code sessions across multiple projects. Epic 3 adds an intelligence layer: E3-S1 provides inference infrastructure, E3-S2 adds turn/command summarisation, E3-S3 adds priority scoring, and E3-S4 provides git-based progress summary generation.

The system already has:
- A waypoint editor (Epic 2) that reads/writes `waypoint.md` from each project's `docs/brain_reboot/` directory, with archiving, conflict detection, and a full modal UI
- Agent activity tracking via `Agent.last_seen_at` and session registry with `get_inactive_sessions()` — staleness infrastructure exists but is not surfaced to the user
- Three established modal patterns in the dashboard (`_waypoint_editor.html`, `_doc_viewer_modal.html`, `_help_modal.html`)
- Clipboard functionality in the help system (`navigator.clipboard.writeText()` with feedback)
- A Project model with `name`, `path`, and `agents` relationship
- Config.yaml with `inactivity_timeout` for session-level timeout (separate from project-level staleness)

This sprint is the capstone of Epic 3. It combines the waypoint (what's ahead) with the progress summary (what was done) into a brain reboot document, adds staleness detection to proactively flag projects needing attention, and provides export and clipboard for portability.

### 1.2 Target User

The primary user is a developer returning to a project after being away — whether for days or hours. They need to rapidly restore mental context: what was accomplished recently, what's next, and where things stand. Secondary use: handing context to an AI agent via clipboard when starting a new session on a stale project.

### 1.3 Success Moment

A developer opens the Claude Headspace dashboard and sees a red "Needs Reboot" badge on a project they haven't touched in 10 days. They click the "Brain Reboot" button, and a modal appears showing a progress summary of recent git activity alongside the waypoint's next-up items. In 30 seconds they understand the project's state. They click "Copy to Clipboard" and paste it into a new Claude Code session as context, immediately resuming productive work.

---

## 2. Scope

### 2.1 In Scope

- Brain reboot generator that combines a project's waypoint and progress summary into a single formatted context restoration document
- Dynamic generation on demand (not stored by default)
- Dashboard modal to view the generated brain reboot content
- Export option to save the brain reboot document to the target project's brain reboot directory
- Copy to clipboard functionality for the generated brain reboot content
- Staleness detection classifying projects into freshness tiers based on configurable time-since-last-activity thresholds
- Visual staleness indicators on the dashboard per project
- "Needs Reboot" badge on projects classified as stale
- Graceful handling when waypoint or progress summary (or both) are missing
- Configurable staleness thresholds in config.yaml
- Brain Reboot button per project on the dashboard
- API endpoint: POST `/api/projects/<id>/brain-reboot` — generate brain reboot for a project
- API endpoint: GET `/api/projects/<id>/brain-reboot` — retrieve last generated brain reboot

### 2.2 Out of Scope

- Progress summary generation from git history (E3-S4 prerequisite)
- Waypoint editing (Epic 2, already complete)
- LLM-based synthesis or enhancement of brain reboot content
- Inference service infrastructure (E3-S1)
- Turn or command summarisation (E3-S2)
- Priority scoring (E3-S3)
- Version history or archiving of brain reboot documents
- Scheduled or automatic brain reboot generation
- Mobile-optimised modal layout
- Brain reboot for projects that have never had any agent sessions

---

## 3. Success Criteria

### 3.1 Functional Success Criteria

1. Brain reboot combines waypoint and progress summary into a formatted document for a given project
2. Dashboard shows a "Brain Reboot" button per project
3. Clicking the button opens a modal displaying the brain reboot content
4. Export saves the brain reboot document to the project's brain reboot directory
5. Export creates the directory structure in the target project if it does not exist
6. Copy to clipboard copies the full brain reboot content with user feedback confirming the copy
7. Projects classified as stale display a visual indicator and "Needs Reboot" badge on the dashboard
8. Projects classified as aging display a warning-level indicator on the dashboard
9. Staleness thresholds are configurable via config.yaml
10. When waypoint is missing, the brain reboot shows the progress summary and indicates the waypoint is absent
11. When progress summary is missing, the brain reboot shows the waypoint and indicates the progress summary is absent
12. When both artifacts are missing, the modal displays guidance on how to create them

### 3.2 Non-Functional Success Criteria

1. Brain reboot generation does not require LLM inference calls — it composes existing artifacts
2. Modal opens and displays content without perceptible delay (artifacts are local files)
3. Export does not overwrite existing files without indication to the user
4. Staleness detection does not add measurable overhead to dashboard rendering

---

## 4. Functional Requirements (FRs)

### Brain Reboot Generator

**FR1:** The system shall provide a brain reboot generator that reads a project's waypoint and progress summary and combines them into a single formatted document.

**FR2:** Brain reboot generation shall be on-demand — triggered by user action, not stored by default.

**FR3:** The generated brain reboot document shall include the project name, generation timestamp, progress summary content, and waypoint content (organised by priority sections: next up, upcoming, later, not now).

**FR4:** Brain reboot generation shall not make any LLM inference calls — it shall compose existing file-based artifacts with formatting.

### Missing Artifact Handling

**FR5:** When a project's waypoint exists but progress summary does not, the brain reboot shall include the waypoint content and indicate that the progress summary is not yet available.

**FR6:** When a project's progress summary exists but waypoint does not, the brain reboot shall include the progress summary content and indicate that the waypoint is not yet available.

**FR7:** When neither waypoint nor progress summary exists, the brain reboot shall display a message indicating both artifacts are missing, with guidance on how to create them (generate progress summary, create waypoint via the editor).

**FR8:** When both artifacts exist, the brain reboot shall combine them in a consistent structure: progress summary first, then waypoint.

### API Endpoints

**FR9:** POST `/api/projects/<id>/brain-reboot` shall generate a brain reboot for the specified project and return the formatted content.

**FR10:** GET `/api/projects/<id>/brain-reboot` shall return the most recently generated brain reboot content for the specified project, or indicate that none has been generated yet.

**FR11:** Both endpoints shall return appropriate error responses when the project does not exist.

### Dashboard Modal

**FR12:** The dashboard shall display a "Brain Reboot" button for each project.

**FR13:** Clicking the Brain Reboot button shall open a modal overlay displaying the generated brain reboot content for that project.

**FR14:** The modal shall include a "Copy to Clipboard" button that copies the full brain reboot content as text and provides visual feedback confirming the copy.

**FR15:** The modal shall include an "Export" button that saves the brain reboot document to the target project's brain reboot directory.

**FR16:** The modal shall be dismissable via backdrop click, close button, or escape key.

### Export

**FR17:** Export shall save the brain reboot document as a markdown file in the target project's brain reboot directory.

**FR18:** Export shall create the brain reboot directory structure in the target project if it does not already exist.

**FR19:** Export shall provide feedback to the user indicating success or failure of the save operation.

**FR20:** If a brain reboot file already exists at the export location, the system shall overwrite it (brain reboots are regenerated on demand, not versioned).

### Staleness Detection

**FR21:** The system shall classify each project into a freshness tier based on the time elapsed since the most recent agent activity on that project.

**FR22:** The system shall support three freshness tiers: fresh, aging, and stale, with configurable day-based thresholds.

**FR23:** The staleness thresholds shall be configurable in config.yaml with sensible defaults.

**FR24:** Projects with no agent activity history shall not display a staleness indicator (unknown freshness).

### Staleness Dashboard Integration

**FR25:** Projects classified as stale shall display a prominent visual indicator and a "Needs Reboot" badge on the dashboard.

**FR26:** Projects classified as aging shall display a warning-level visual indicator on the dashboard.

**FR27:** Projects classified as fresh shall display a positive freshness indicator or no special indicator.

**FR28:** Staleness indicators shall update when the dashboard refreshes or receives SSE updates reflecting new agent activity.

---

## 5. Non-Functional Requirements (NFRs)

**NFR1:** Brain reboot generation shall complete without network calls — reading only local filesystem artifacts — ensuring near-instant response.

**NFR2:** The modal shall follow the established modal patterns in the codebase (overlay, dismiss behavior, keyboard handling) for UI consistency.

**NFR3:** Staleness classification shall be computed efficiently from existing Agent model data (`last_seen_at`) without additional database queries beyond what the dashboard already performs.

**NFR4:** The clipboard operation shall use the modern browser clipboard API with graceful fallback if the API is unavailable.

**NFR5:** Export file writes shall handle filesystem errors (permissions, disk space) gracefully with user-facing error messages.

---

## 6. UI Overview

Brain reboot integrates into three dashboard areas:

**Project Group Headers:** Each project group on the dashboard gains a "Brain Reboot" button alongside existing project controls. Stale and aging projects display freshness indicators (badge, colour, or icon) in the project header area, with stale projects showing a "Needs Reboot" badge.

**Brain Reboot Modal:** A full-content modal overlay (consistent with existing modal patterns) displays the generated brain reboot. The modal contains:
- Project name and generation timestamp as header
- Progress summary section (rendered markdown)
- Waypoint section with priority groupings (next up, upcoming, later, not now)
- Missing artifact notices where applicable
- Action buttons: "Copy to Clipboard" and "Export" in the modal footer
- Close button and backdrop/escape dismiss

**Staleness Indicators:** Visual freshness indicators per project, visible at a glance on the dashboard without opening any modal. Fresh projects have no special treatment (or a subtle positive indicator). Aging projects show a warning-level indicator. Stale projects show a prominent indicator with "Needs Reboot" badge, drawing the user's eye to projects that need context restoration.

---

## 7. Technical Context for Builder

This section provides implementation guidance and is not part of the requirements. The builder may adapt these recommendations.

### Brain Reboot Output Structure

The roadmap defines this output format:

```markdown
# Brain Reboot: {project.name}

Generated: {timestamp}

## Progress Summary

{progress_summary content}

## Waypoint (Path Ahead)

### Next Up

{waypoint.next_up}

### Upcoming

{waypoint.upcoming}

### Later

{waypoint.later}

### Not Now

{waypoint.not_now}

---

_Use this document to quickly restore context when returning to this project._
```

### Staleness Threshold Defaults

The roadmap recommends these default thresholds:

| Days Since Activity | Status | Indicator                  |
| ------------------- | ------ | -------------------------- |
| 0-3 days            | Fresh  | Green (or no indicator)    |
| 4-7 days            | Aging  | Yellow / warning           |
| 8+ days             | Stale  | Red + "Needs Reboot" badge |

### Config.yaml Additions

```yaml
brain_reboot:
  staleness_threshold_days: 7    # Days before project marked stale
  aging_threshold_days: 4        # Days before project marked aging
  export_filename: brain_reboot.md  # Filename for export
```

Note: This is separate from the existing `inactivity_timeout` (90 min) which handles session-level agent timeouts. Brain reboot staleness operates at the project level on a days scale.

### Integration Points

- Reads waypoint from target project via existing waypoint editor service (or directly from `docs/brain_reboot/waypoint.md`)
- Reads progress summary from target project's `docs/brain_reboot/progress_summary.md` (generated by E3-S4)
- Staleness uses `Agent.last_seen_at` from the existing Agent model (indexed on `(project_id, last_seen_at)`)
- Modal follows established patterns from `_waypoint_editor.html`, `_doc_viewer_modal.html`
- Clipboard follows established pattern from `static/js/help.js`
- Export follows the directory creation pattern from the waypoint editor service

### Existing Infrastructure to Reuse

| Component | Source | Reuse |
|---|---|---|
| Waypoint file reading | `waypoint_editor.py` | Read waypoint content |
| Modal pattern | `_waypoint_editor.html` | Overlay, dismiss, keyboard |
| Clipboard | `help.js` | `navigator.clipboard.writeText()` |
| Directory creation | `waypoint_editor.py` | `os.makedirs(exist_ok=True)` |
| Agent last_seen_at | `agent.py` | Staleness calculation |
| Session inactivity | `session_registry.py` | Pattern reference (different scale) |
