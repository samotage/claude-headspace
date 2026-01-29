---
validation:
  status: valid
  validated_at: '2026-01-29T16:33:20+11:00'
---

## Product Requirements Document (PRD) — Config UI Tab

**Project:** Claude Headspace v3.1
**Scope:** Epic 2, Sprint 1 — Web-based configuration editing
**Author:** PRD Workshop
**Status:** Draft

---

## Executive Summary

Claude Headspace currently requires users to manually edit `config.yaml` in a text editor to change application settings. This creates friction, requires YAML syntax knowledge, and risks formatting errors that could break the application.

The Config UI Tab provides a web-based form interface for editing all configuration sections directly from the dashboard. Users can modify server settings, database credentials, file watcher behavior, and SSE parameters without leaving the browser. All changes are validated before saving, with clear feedback on success or failure.

This sprint establishes the editing UI patterns that subsequent sprints (E2-S2 Waypoint Editor) will reuse, making it foundational for Epic 2's UI polish goals.

---

## 1. Context & Purpose

### 1.1 Context

Claude Headspace is configured via a `config.yaml` file containing 7 sections: server, logging, database, claude, file_watcher, event_system, and sse. Currently, changing any setting requires:

1. Locating the config file in the project directory
2. Opening it in a text editor
3. Understanding YAML syntax
4. Making changes without validation feedback
5. Restarting the server to apply changes

This workflow is error-prone and breaks the self-contained dashboard experience that Claude Headspace aims to provide.

### 1.2 Target User

Developers and power users who run Claude Headspace locally to monitor their Claude Code sessions. They want to tune settings (ports, timeouts, connection limits) without context-switching to a terminal and text editor.

### 1.3 Success Moment

A user opens the Config tab, changes `server.port` from 5050 to 5055, clicks Save, sees a success toast, clicks Refresh, and the application restarts on the new port—all without touching the command line or a text editor.

---

## 2. Scope

### 2.1 In Scope

- Config tab accessible from main navigation (alongside dashboard, objective, logging)
- Form-based UI displaying all `config.yaml` sections as editable fields
- Field types: text inputs, number inputs, boolean toggles, password fields
- Nested structure handling (e.g., `database.host`, `file_watcher.polling_interval`)
- Server-side validation before save (type checking, required fields, value ranges)
- Password field masking with reveal toggle (for `database.password`)
- Persist validated changes to `config.yaml` file
- Success toast on save, error toast on validation failure
- Manual refresh button to apply configuration changes
- API endpoints: GET `/api/config`, POST `/api/config`
- Field descriptions/hints for user guidance
- Loading indicators during fetch and save operations

### 2.2 Out of Scope

- Raw YAML text editor (form-based only per technical decision)
- Auto-reload of config changes (manual refresh per technical decision)
- Environment variable editing (env vars are read-only overrides)
- Config file backup/versioning
- Multi-user conflict resolution (single-user assumed)
- Real-time config sync across browser tabs
- Preserving YAML comments (acknowledged PyYAML limitation)

---

## 3. Success Criteria

### 3.1 Functional Success Criteria

1. Config tab displays all 7 config sections as grouped form fields
2. Edit `server.port` value, save, and verify value persisted to `config.yaml`
3. Enter invalid value (e.g., "abc" for port) and see validation error displayed
4. All nested structures (database.*, file_watcher.*, sse.*, event_system.*) are editable
5. Password field (`database.password`) is masked by default with working reveal toggle
6. Success toast appears after successful save
7. Error toast appears when save fails (validation error or file write error)
8. Refresh button is visible with indication of what requires server restart

### 3.2 Non-Functional Success Criteria

1. Form loads within 500ms of navigating to Config tab
2. Save operation completes within 1 second
3. Validation errors appear inline next to the relevant field
4. UI is accessible (proper labels, ARIA attributes, keyboard navigation)

---

## 4. Functional Requirements (FRs)

**Navigation & Access**

- **FR1:** Config tab is accessible from main navigation bar
- **FR2:** Config tab follows existing navigation styling pattern (active state indicator)

**Form Display**

- **FR3:** All config.yaml sections display as visually grouped form fieldsets
- **FR4:** Each config section has a clear heading (e.g., "Server", "Database", "File Watcher")
- **FR5:** Form pre-populates with current config values on page load
- **FR6:** Field descriptions/hints display below each field explaining its purpose

**Field Types**

- **FR7:** String fields render as text inputs
- **FR8:** Numeric fields render as number inputs with appropriate min/max constraints
- **FR9:** Boolean fields render as toggle switches
- **FR10:** Password fields render as masked inputs with a reveal/hide toggle button

**Validation**

- **FR11:** Server validates all fields before saving (type, required, range)
- **FR12:** Validation errors display inline next to the invalid field
- **FR13:** Form cannot be submitted while validation errors exist

**Save & Feedback**

- **FR14:** Save button submits all form data to POST `/api/config`
- **FR15:** Loading indicator displays during save operation
- **FR16:** Success toast appears after successful save with message "Configuration saved"
- **FR17:** Error toast appears if save fails with specific error message

**Refresh Mechanism**

- **FR18:** Refresh button is visible after successful save
- **FR19:** Refresh button indicates which settings require server restart to take effect
- **FR20:** Clicking refresh triggers application restart or page reload as appropriate

**API**

- **FR21:** GET `/api/config` returns current configuration as JSON
- **FR22:** POST `/api/config` accepts JSON payload, validates, and persists to config.yaml
- **FR23:** POST `/api/config` returns validation errors as structured JSON on failure
- **FR24:** API excludes environment variable overrides from response (shows file values only)

---

## 5. Non-Functional Requirements (NFRs)

- **NFR1:** Password values are never logged or exposed in error messages
- **NFR2:** Config file write is atomic (write to temp file, then rename) to prevent corruption
- **NFR3:** Form maintains scroll position after save operation
- **NFR4:** All form controls meet WCAG 2.1 AA accessibility standards
- **NFR5:** Form is usable on viewport widths down to 768px

---

## 6. UI Overview

**Layout:**

The Config tab displays a single-column form with collapsible sections for each config category. The layout follows the existing dashboard aesthetic (dark theme, Tailwind CSS, monospace accents).

**Section Order:**

1. Server (host, port, debug)
2. Logging (level, file)
3. Database (host, port, name, user, password, pool_size, pool_timeout)
4. Claude (projects_path)
5. File Watcher (polling_interval, reconciliation_interval, inactivity_timeout, debounce_interval)
6. Event System (write_retry_attempts, write_retry_delay_ms, max_restarts_per_minute, shutdown_timeout_seconds)
7. SSE (heartbeat_interval_seconds, max_connections, connection_timeout_seconds, retry_after_seconds)

**Key Interactions:**

- **Password reveal:** Click eye icon to toggle between masked (•••) and plain text
- **Save:** Single "Save Configuration" button at bottom of form
- **Refresh:** "Apply Changes" button appears after save, with tooltip explaining restart behavior
- **Validation:** Red border and error text appear on invalid fields immediately after save attempt

**Toast Messages:**

- Success: "Configuration saved successfully"
- Error: "Failed to save configuration: [specific error]"
- Validation: "Please fix the errors above before saving"

---

## 7. Technical Context (Reference Only)

*This section captures technical decisions from the roadmap for implementer reference. These are not requirements—implementation details will be determined during OpenSpec proposal.*

- Form-based editor chosen over raw YAML for usability
- Server-side validation is authoritative (client hints optional)
- Manual refresh button chosen over auto-reload for predictability
- YAML comments may be lost on save (PyYAML limitation accepted)
- Existing patterns available: tab navigation, toast notifications, form styling

---

## Document History

| Version | Date       | Author       | Changes                    |
|---------|------------|--------------|----------------------------|
| 1.0     | 2026-01-29 | PRD Workshop | Initial PRD from workshop  |
