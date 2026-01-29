---
validation:
  status: valid
  validated_at: '2026-01-29T16:35:18+11:00'
---

## Product Requirements Document (PRD) — Waypoint Editor

**Project:** Claude Headspace v3.1
**Scope:** Epic 2, Sprint 2 (E2-S2) — Waypoint Editing UI
**Author:** PRD Workshop
**Status:** Draft

---

## Executive Summary

The Waypoint Editor enables users to view and edit project waypoints directly from the Claude Headspace dashboard, eliminating the need to manually navigate to and edit files in each project's repository.

The waypoint is a core artifact of the brain_reboot system — it defines the path ahead for a project with four sections: Next Up, Upcoming, Later, and Not Now. Keeping waypoints current is essential for effective mental context restoration when returning to stale projects.

This PRD delivers a web-based editor with project selection, markdown editing with preview, automatic archiving of previous versions, and graceful handling of missing files and permission errors. It builds on the Project model from Epic 1 and follows editing patterns established in E2-S1 (Config UI).

---

## 1. Context & Purpose

### 1.1 Context

Waypoints live in each target project's repository at `docs/brain_reboot/waypoint.md`. Currently, editing requires navigating to the project directory and manually editing the file. This friction leads to stale waypoints that diminish the value of the brain_reboot system.

Epic 1 established the Project model with paths to monitored projects. The dashboard already displays a waypoint preview with a placeholder [Edit] button. This sprint activates that capability.

### 1.2 Target User

Users managing multiple projects through Claude Headspace who need to keep project waypoints current without context-switching to file editors or terminals.

### 1.3 Success Moment

User clicks [Edit] on a project's waypoint, updates the "Next Up" section to reflect new priorities, saves, and sees confirmation that the waypoint is updated — all without leaving the dashboard.

---

## 2. Scope

### 2.1 In Scope

- Waypoint editor UI accessible from dashboard (tab or modal)
- Project selector dropdown populated from database
- Markdown textarea for editing waypoint content
- Markdown preview toggle (view rendered output)
- Load waypoint from `<project_path>/docs/brain_reboot/waypoint.md`
- Save waypoint to project directory
- Archive previous waypoint to `archive/waypoint_YYYY-MM-DD.md` before saving
- Create `docs/brain_reboot/` directory structure if missing
- Create waypoint from template if file doesn't exist
- File permission error handling with actionable messages
- Conflict detection (file modified externally while editing)
- Success/error feedback via toast notifications
- API endpoints: GET/POST `/api/projects/<id>/waypoint`

### 2.2 Out of Scope

- Rich markdown editor (WYSIWYG) — plain textarea with preview only
- Real-time collaboration / multi-user editing
- Version history browser (archives created, no UI to browse them)
- Waypoint validation / structure enforcement
- Auto-save / draft recovery
- Integration with progress_summary (Epic 3)
- Brain reboot generation (Epic 3)

---

## 3. Success Criteria

### 3.1 Functional Success Criteria

1. User can select any monitored project from dropdown and waypoint loads
2. User can edit waypoint content in markdown textarea
3. User can toggle between edit and preview modes
4. Save operation archives previous waypoint with date stamp (e.g., `waypoint_2026-01-29.md`)
5. New projects without waypoint receive standard template on first save
6. Directory structure (`docs/brain_reboot/` and `archive/`) created automatically if missing
7. External file modification detected: user prompted to reload or overwrite
8. Permission errors display actionable message with specific path

### 3.2 Non-Functional Success Criteria

1. Waypoint loads within 500ms for files up to 100KB
2. Save operation completes within 2 seconds (including archive)
3. Archive operation is atomic — no partial writes or data loss
4. Error messages include specific file path and suggested remediation action

---

## 4. Functional Requirements (FRs)

### Project Selection

**FR1:** The editor displays a dropdown listing all monitored projects by name, sorted alphabetically.

**FR2:** Selecting a project loads its waypoint content into the editor. If no waypoint exists, the editor displays the default template.

**FR3:** The editor indicates which project is currently selected and whether it has an existing waypoint or is using the template.

### Waypoint Loading

**FR4:** The system loads waypoint content from `<project.path>/docs/brain_reboot/waypoint.md`.

**FR5:** If the waypoint file does not exist, the editor displays the default waypoint template (see FR14) and indicates this is a new waypoint.

**FR6:** If the `docs/brain_reboot/` directory does not exist, the system creates it (and `archive/` subdirectory) when the user saves.

### Editing Interface

**FR7:** The editor provides a markdown textarea for editing waypoint content.

**FR8:** The editor provides a preview mode that renders the markdown content.

**FR9:** Users can toggle between edit mode (textarea visible) and preview mode (rendered markdown visible).

**FR10:** The editor displays an indicator when there are unsaved changes.

### Saving Waypoint

**FR11:** When saving, the system first archives the existing waypoint (if any) to `<project.path>/docs/brain_reboot/archive/waypoint_YYYY-MM-DD.md`.

**FR12:** If an archive file with today's date already exists, the system appends a counter (e.g., `waypoint_2026-01-29_2.md`).

**FR13:** After archiving, the system writes the new content to `waypoint.md`.

**FR14:** For new waypoints (no existing file), the system uses this template:

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

### Conflict Detection

**FR15:** Before saving, the system checks if the file's modification time has changed since loading.

**FR16:** If a conflict is detected, the user is prompted with options: "Reload" (discard changes and load current file) or "Overwrite" (save anyway, replacing external changes).

### Error Handling

**FR17:** If the project path is inaccessible or does not exist, the system displays an error with the specific path.

**FR18:** If the system lacks write permission to the project directory, the error message includes the path and suggests checking directory permissions.

**FR19:** All save errors are reported via toast notification with actionable detail.

### Feedback

**FR20:** Successful save displays a success toast notification.

**FR21:** The [Edit] button in the project group on the dashboard opens the waypoint editor for that project.

---

## 5. Non-Functional Requirements (NFRs)

**NFR1:** Waypoint content loads within 500ms for files up to 100KB.

**NFR2:** Save operation (including archive) completes within 2 seconds under normal conditions.

**NFR3:** Archive write is atomic — system writes to a temporary file first, then renames to prevent partial writes.

**NFR4:** The editor handles waypoint files up to 1MB without performance degradation.

**NFR5:** Error messages follow the pattern: "[Action] failed: [Reason]. [Suggested fix]." (e.g., "Save failed: Permission denied for /path/to/project/docs/brain_reboot/. Check directory permissions.")

---

## 6. UI Overview

### 6.1 Editor Layout

The waypoint editor consists of:

1. **Header Bar**
   - Project selector dropdown (left)
   - Status indicator: "Editing" / "New waypoint" / "Unsaved changes" (center)
   - Action buttons: Save, Cancel (right)

2. **Editor Area**
   - Toggle control: Edit | Preview
   - **Edit mode:** Full-width textarea with monospace font, line numbers optional
   - **Preview mode:** Rendered markdown with standard styling (headings, lists, code blocks)

3. **Footer**
   - File path display: `<project>/docs/brain_reboot/waypoint.md`
   - Last modified timestamp (if file exists)

### 6.2 Integration with Dashboard

- The existing [Edit] button in `_project_group.html` waypoint preview section opens the editor
- Editor may be implemented as:
  - A modal overlay (recommended for quick edits)
  - A dedicated tab (alternative for extended editing sessions)
- Decision on modal vs tab deferred to implementation, with modal as default recommendation

### 6.3 Conflict Resolution Dialog

When external modification detected:
- Modal dialog with message: "This waypoint was modified externally since you started editing."
- Two buttons: "Reload" (primary), "Overwrite" (secondary/destructive)
- Shows timestamp of external modification

---

## 7. API Endpoints

### GET `/api/projects/<id>/waypoint`

**Purpose:** Retrieve waypoint content for a project.

**Response (200):**
```json
{
  "project_id": 1,
  "project_name": "RAGlue",
  "exists": true,
  "content": "# Waypoint\n\n## Next Up\n...",
  "last_modified": "2026-01-29T10:30:00Z",
  "path": "/Users/sam/dev/raglue/docs/brain_reboot/waypoint.md"
}
```

**Response (200, no waypoint):**
```json
{
  "project_id": 1,
  "project_name": "RAGlue",
  "exists": false,
  "content": "# Waypoint\n\n## Next Up\n...",
  "template": true,
  "path": "/Users/sam/dev/raglue/docs/brain_reboot/waypoint.md"
}
```

**Response (404):** Project not found.

**Response (500):** File system error (with detail).

### POST `/api/projects/<id>/waypoint`

**Purpose:** Save waypoint content for a project.

**Request:**
```json
{
  "content": "# Waypoint\n\n## Next Up\n...",
  "expected_mtime": "2026-01-29T10:30:00Z"
}
```

**Response (200):**
```json
{
  "success": true,
  "archived": true,
  "archive_path": "archive/waypoint_2026-01-29.md",
  "last_modified": "2026-01-29T11:00:00Z"
}
```

**Response (409, conflict):**
```json
{
  "error": "conflict",
  "message": "File was modified externally",
  "current_mtime": "2026-01-29T10:45:00Z",
  "expected_mtime": "2026-01-29T10:30:00Z"
}
```

**Response (403):** Permission denied (with path).

**Response (404):** Project not found.

---

## 8. Technical Decisions (Pre-Made)

Per the Epic 2 Detailed Roadmap, the following decisions have been made:

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Editor type | Plain textarea with preview | Simpler, users know markdown, rich editors can be buggy |
| Archive frequency | Every save | Simple, predictable, low storage cost |
| Waypoint location | `docs/brain_reboot/waypoint.md` | Standardized per conceptual overview |
| Conflict detection | mtime comparison | Simple, effective, no locking complexity |

---

## 9. Dependencies

- **Epic 1 complete:** Project model, dashboard, tab navigation, toast notifications
- **E2-S1 Config UI:** Establishes editing UI patterns (form layout, save feedback, error handling)

---

## 10. Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| File permission errors on project directories | Medium | Check permissions on load, show read-only indicator if can't write, clear error messages |
| Project path inaccessible (network drive, moved) | Medium | Validate path exists before showing editor, graceful error if disappeared |
| Large waypoint files causing slow load | Low | Warn if file >100KB, stream load if needed |
| User confusion about archive location | Low | Show archive path in success toast, document in help |

---

## Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-01-29 | PRD Workshop | Initial PRD from workshop |
