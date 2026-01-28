---
validation:
  status: valid
  validated_at: '2026-01-29T10:32:50+11:00'
---

## Product Requirements Document (PRD) — Objective Tab

**Project:** Claude Headspace v3.1
**Scope:** Epic 1, Sprint 9 — Objective Tab UI and API
**Author:** PRD Workshop
**Status:** Draft

---

## Executive Summary

Claude Headspace's core value proposition is cross-project prioritisation aligned to a user's current objective. This PRD defines the Objective Tab—the user interface for setting, viewing, and tracking objectives that guide agent prioritisation.

The objective is a global singleton that represents "what the user is trying to achieve right now." When set, it enables future sprints (Epic 3) to rank agents by how well their current work aligns with this goal. Without a way to set objectives, users cannot leverage the prioritisation features that differentiate Claude Headspace from simple agent monitoring.

This sprint delivers the objective tab template, auto-saving form with debounce, objective history display with pagination, and three API endpoints for objective management. The data layer (Objective and ObjectiveHistory models) already exists from Sprint 3.

---

## 1. Context & Purpose

### 1.1 Context

Claude Headspace monitors multiple Claude Code agents across projects. To prioritise which agent needs attention, the system needs to know the user's current focus. The objective tab provides the interface for users to declare their current objective and optional constraints, which the system uses to guide prioritisation.

The Objective and ObjectiveHistory database models were implemented in Sprint 3 (Domain Models). This sprint builds the user-facing interface and API layer on top of that foundation.

### 1.2 Target User

Developers using Claude Code across multiple projects who need to:
- Set their current focus/objective
- Track how their objectives change over time
- Enable AI-driven prioritisation based on their stated goals

### 1.3 Success Moment

A developer opens the objective tab, types "Ship the authentication feature before EOD," optionally adds constraints like "avoid breaking changes," and sees the objective auto-save. Later, they can view their objective history to see what they were focused on previously.

---

## 2. Scope

### 2.1 In Scope

- Objective tab HTML template with dark terminal aesthetic (matching existing base template)
- Objective form with text input field (required) and constraints textarea (optional)
- Auto-save functionality with debounce (2-3 seconds recommended)
- Visual feedback for save state (saving indicator, saved confirmation, error state)
- Objective history display showing previous objectives with timestamps
- History pagination (approximately 10 per page)
- API endpoint: `GET /api/objective` - retrieve current objective
- API endpoint: `POST /api/objective` - create/update objective with automatic history tracking
- API endpoint: `GET /api/objective/history` - retrieve objective history with pagination
- Proper history tracking: when objective changes, previous objective gets `ended_at` timestamp
- Empty state handling: display message when no objective is set or no history exists
- Error state handling: display user-friendly message when API calls fail
- Shared state: multiple browser tabs reflect the same current objective

### 2.2 Out of Scope

- Tab navigation component (Sprint 8 - Dashboard UI delivers shared navigation)
- LLM-based priority scoring using objectives (Epic 3 - Intelligence Layer)
- Real-time SSE updates when objective changes from another tab
- Objective validation rules beyond required text field
- Objective templates or presets
- Objective categories or tagging
- Integration with agents/tasks for prioritisation calculations
- Markdown rendering in objective text
- Rich text editing

---

## 3. Success Criteria

### 3.1 Functional Success Criteria

1. User can enter objective text in the form and it auto-saves after debounce period
2. User can optionally enter constraints in a separate textarea
3. Save state is visually indicated (saving spinner, "saved" confirmation, error message)
4. Objective changes persist across page reloads
5. Objective history displays previous objectives with started_at and ended_at timestamps
6. History is paginated when more than one page of entries exists
7. Empty states display appropriate messages ("No objective set", "No objective history yet")
8. API error states display user-friendly error messages

### 3.2 Non-Functional Success Criteria

1. Auto-save debounce prevents excessive API calls during typing
2. Page load displays current objective without noticeable delay
3. History pagination loads additional pages without full page refresh
4. UI follows existing dark terminal aesthetic from base template

---

## 4. Functional Requirements (FRs)

### FR1: Objective Tab Template

The system shall provide an objective tab page that:
- Extends the base template
- Displays the current objective form
- Displays the objective history section below the form
- Uses the established dark terminal aesthetic (Tailwind classes)

### FR2: Objective Form - Text Field

The system shall provide a text input field for the objective that:
- Displays placeholder text guiding the user (e.g., "What's your objective right now?")
- Is required (objective cannot be empty)
- Loads the current objective text on page load
- Triggers auto-save on content change (after debounce)

### FR3: Objective Form - Constraints Field

The system shall provide a textarea for optional constraints that:
- Displays placeholder text (e.g., "Constraints: limited time, avoid breaking changes...")
- Is optional (can be empty)
- Loads current constraints on page load
- Triggers auto-save on content change (after debounce)

### FR4: Auto-Save with Debounce

The system shall auto-save objective changes that:
- Waits for user to stop typing (debounce period of 2-3 seconds)
- Sends POST request to `/api/objective` with current form values
- Does not save if objective text is empty
- Cancels pending save if user continues typing

### FR5: Save State Indicators

The system shall display save state feedback:
- "Saving..." indicator while API request is in flight
- "Saved" confirmation when save completes successfully (auto-dismiss after brief delay)
- Error message when save fails (persists until next action)
- "Changes save automatically" hint text near the form

### FR6: Objective History Display

The system shall display objective history that:
- Shows a list of previous objectives ordered by started_at descending (most recent first)
- Displays the objective text for each history entry
- Displays the constraints for each history entry (if present)
- Displays started_at timestamp for each entry
- Displays ended_at timestamp for each entry (except current objective)

### FR7: History Pagination

The system shall paginate objective history that:
- Displays approximately 10 entries per page
- Provides navigation to load more entries
- Indicates when no more entries are available

### FR8: Empty States

The system shall handle empty states:
- When no objective is set: form fields are empty, ready for input
- When no history exists: display "No objective history yet" message

### FR9: API Endpoint - Get Current Objective

The system shall provide `GET /api/objective` that:
- Returns the current objective with id, current_text, constraints, and set_at
- Returns appropriate response when no objective exists
- Returns JSON response

### FR10: API Endpoint - Create/Update Objective

The system shall provide `POST /api/objective` that:
- Accepts JSON body with `text` (required) and `constraints` (optional)
- Creates a new objective if none exists
- Updates existing objective if one exists
- When updating: sets ended_at on current ObjectiveHistory, creates new ObjectiveHistory record
- Returns the updated objective
- Returns validation error if text is empty

### FR11: API Endpoint - Get Objective History

The system shall provide `GET /api/objective/history` that:
- Returns paginated list of ObjectiveHistory records
- Accepts optional `page` query parameter (default: 1)
- Accepts optional `per_page` query parameter (default: 10)
- Returns entries ordered by started_at descending
- Returns total count and pagination metadata
- Returns JSON response

### FR12: History Tracking Logic

The system shall track objective history correctly:
- When objective is first created: create ObjectiveHistory with started_at = now, ended_at = null
- When objective is updated: set ended_at on previous history record, create new history record
- ObjectiveHistory.text and constraints snapshot the values at that point in time

### FR13: Error Handling

The system shall handle errors gracefully:
- API validation errors return 400 with descriptive message
- Database errors return 500 with generic error message
- Frontend displays user-friendly error messages for failed requests

---

## 5. Non-Functional Requirements (NFRs)

### NFR1: Debounce Timing

Auto-save debounce should be approximately 2-3 seconds to balance responsiveness with preventing excessive API calls.

### NFR2: Page Load Performance

Current objective should be displayed within the initial page render (server-side rendered or immediate API fetch on load).

### NFR3: Pagination Defaults

History pagination should default to 10 entries per page, with ability to navigate to additional pages.

### NFR4: Visual Consistency

UI styling should use existing Tailwind CSS classes from base template (bg-void, text-primary, font-mono, etc.).

### NFR5: Long Text Handling

Objective text and constraints should display gracefully regardless of length (text wrapping, scrollable if needed).

---

## 6. UI Overview

### Objective Tab Layout

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
│   │ [User types objective here...]                                  │   │
│   └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│   ┌─────────────────────────────────────────────────────────────────┐   │
│   │ Constraints (optional)                                          │   │
│   │                                                                 │   │
│   │ [User types constraints here...]                                │   │
│   └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│   Changes save automatically                          [Saved ✓]         │
│                                                                         │
│   ─────────────────────────────────────────────────────────────────     │
│                                                                         │
│   OBJECTIVE HISTORY                                                     │
│                                                                         │
│   ┌─────────────────────────────────────────────────────────────────┐   │
│   │ "Ship authentication feature before EOD"                        │   │
│   │ Constraints: Avoid breaking changes                             │   │
│   │ Jan 29, 2026 9:00 AM - Jan 29, 2026 2:30 PM                    │   │
│   └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│   ┌─────────────────────────────────────────────────────────────────┐   │
│   │ "Fix critical bug in payment flow"                              │   │
│   │ Jan 28, 2026 3:00 PM - Jan 29, 2026 9:00 AM                    │   │
│   └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│   [Load more...]                                                        │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### Empty History State

```
│   OBJECTIVE HISTORY                                                     │
│                                                                         │
│   No objective history yet.                                             │
```

---

## 7. Technical Context

*Note: This section captures architectural decisions for implementation reference.*

### File Structure

```
src/claude_headspace/
├── routes/
│   ├── __init__.py
│   ├── health.py          # Existing
│   └── objective.py       # New: objective_bp blueprint
templates/
└── objective.html          # New: objective tab template
static/
└── js/
    └── objective.js        # New: auto-save and UI logic
```

### API Response Formats

**GET /api/objective**
```json
{
  "id": 1,
  "current_text": "Ship authentication feature",
  "constraints": "Avoid breaking changes",
  "set_at": "2026-01-29T09:00:00Z"
}
```

**POST /api/objective**
```json
// Request
{
  "text": "New objective text",
  "constraints": "Optional constraints"
}

// Response
{
  "id": 1,
  "current_text": "New objective text",
  "constraints": "Optional constraints",
  "set_at": "2026-01-29T14:30:00Z"
}
```

**GET /api/objective/history**
```json
{
  "items": [
    {
      "id": 1,
      "text": "Previous objective",
      "constraints": null,
      "started_at": "2026-01-28T15:00:00Z",
      "ended_at": "2026-01-29T09:00:00Z"
    }
  ],
  "page": 1,
  "per_page": 10,
  "total": 25,
  "pages": 3
}
```

### Dependencies

- Sprint 3 (Domain Models) - complete: Objective and ObjectiveHistory models exist
- Sprint 8 (Dashboard UI) - provides tab navigation structure (can be developed in parallel)

---

## 8. Open Questions

*None — all questions resolved during workshop.*

---

## 9. Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-01-29 | PRD Workshop | Initial PRD created |
