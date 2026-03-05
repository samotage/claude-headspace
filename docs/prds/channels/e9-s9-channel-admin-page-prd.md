---
validation:
  status: valid
  validated_at: '2026-03-06T07:42:53+11:00'
---

## Product Requirements Document (PRD) — Channel Admin Page

**Project:** Claude Headspace v3.2
**Scope:** Epic 9, Sprint 9 — Dedicated channel admin page with filters, attention signals, lifecycle management, and member management
**Author:** Mel (workshopped with Sam and Robbo)
**Status:** Draft

---

## Executive Summary

The channel system has a complete backend (S3-S6), dashboard channel cards, a chat panel, and a basic management modal (S7). The operator cannot effectively manage channels at scale. The management modal is buried, has no filtering or search, no attention signals, no delete capability, and no way to assess which channels need action vs which are done.

This sprint replaces the management modal with a dedicated `/channels` admin page — a proper operator control surface for channel oversight and lifecycle management. The page provides a filterable, searchable list of all channels with attention indicators, full lifecycle actions (complete, archive, delete), and member management. It follows the same pattern as the existing `/personas`, `/projects`, and `/activity` pages.

This is a frontend sprint. All backend services and API endpoints exist (S4-S5). The page consumes existing REST endpoints and handles existing SSE events.

---

## 1. Context & Purpose

### 1.1 Context

The dashboard is evolving from a monitoring tool into the operator's back office — the control plane for the entire platform. Channel management is the next panel in that back office.

Sprint 7 built channel cards (top of dashboard), a slide-out chat panel, and a management modal with basic list and create. The modal provides a table view (name, type, status, members, created date) and a create form. It does not provide:

- Status filters or search
- Attention signals (which channels need the operator's attention)
- Delete capability
- Staleness indicators
- Channel detail view with member management
- A discoverable, dedicated page in the navigation

The operator has channels accumulating in the system with no efficient way to triage them — which are active and need attention, which should be completed, which are stale and should be archived. The CLI (`flask channel list`) works but doesn't belong in the operator's workflow.

### 1.2 Target User

The operator (Sam), who manages multiple agents and channels across projects. Needs at-a-glance visibility into channel health and efficient lifecycle controls without leaving the dashboard.

### 1.3 Success Moment

Sam navigates to `/channels` from the dashboard header. He sees 12 channels: 3 active (green), 2 with attention signals (amber pulse — no activity in 2+ hours despite active members), 4 complete, and 3 archived. He filters to "active" and sees just the 3 active channels with their members, last message preview, and time since last activity. One channel — "api-review" — has been idle for 3 hours with 2 active members. He clicks into it, sees the member list, decides Robbo's agent has gone stale, removes Robbo from the channel, and marks it complete. Back on the list, the channel has moved to the "complete" section. He filters to "complete", selects two old channels, and archives them. The whole triage took 30 seconds.

---

## 2. Scope

### 2.1 In Scope

- New `/channels` route and page template, linked from dashboard header navigation
- Channel list view with columns: name, type, status, members, last activity, created date
- Status filter tabs or dropdown: all, pending, active, complete, archived
- Text search by channel name or slug
- Attention signals: visual indicators for channels that may need operator action (e.g., active channels with no messages in configurable time window)
- Channel detail/expand view showing: full member list, message count, chair, description, timestamps
- Create channel form: name, type, description, initial members (persona autocomplete picker)
- Lifecycle actions: complete (active → complete), archive (complete → archived), delete (with confirmation dialog)
- Member management: add persona to channel, remove persona from channel
- Real-time updates via existing `channel_message` and `channel_update` SSE events
- Navigation link in dashboard header alongside existing pages
- Deprecation of the existing channel management modal (`_channel_management.html`): the modal is superseded by this page and should be removed or disabled. The "Channel Management" button on the dashboard that opens the modal should be replaced with a link to `/channels`.

### 2.2 Out of Scope

- Channel messaging UI / chat panel (S7 — already built, continues to work from dashboard)
- Channel cards on dashboard (S7 — already built, unaffected)
- Channel backend services, models, or API endpoints (S3-S5 — already built)
- Channel delivery engine (S6 — already built)
- Voice chat channel creation (separate PRD)
- Promote-to-group / spawn-and-merge from agent chat (separate PRD)
- Chair transfer from UI (TBD — pending operator decision; can be added as a follow-up)
- Bulk actions (select multiple channels for archive/delete — v2 if needed)
- Unread message counts or badges (v2 — no per-recipient tracking in v1 data model)

---

## 3. Success Criteria

### 3.1 Functional Success Criteria

1. A `/channels` page is accessible via a navigation link in the dashboard header
2. The page displays all channels the operator can see, with name, type, status, member count, last activity timestamp, and created date
3. The operator can filter channels by status (pending, active, complete, archived, or all)
4. The operator can search channels by name or slug via a text input
5. Active channels with no message activity in a configurable time window display an attention indicator
6. The operator can create a new channel with name, type, description, and initial members
7. The operator can complete an active channel from the admin page
8. The operator can archive a completed channel from the admin page
9. The operator can delete a channel (with confirmation dialog) from the admin page
10. The operator can view a channel's full member list, message count, and metadata
11. The operator can add a persona to a channel from the admin page
12. The operator can remove a persona from a channel from the admin page
13. Channel list updates in real-time when `channel_message` or `channel_update` SSE events arrive (e.g., new message updates last activity, member join/leave updates member count)
14. Creating a channel from the admin page also creates a channel card on the dashboard (via existing SSE flow)

### 3.2 Non-Functional Success Criteria

1. The page loads within 200ms for up to 100 channels
2. All UI elements follow the existing dark theme and Tailwind CSS conventions
3. No new backend routes beyond the page-serving route — all data operations use existing S5 API endpoints
4. No new npm or Python dependencies
5. The page is usable on tablet-width screens (768px+)

---

## 4. Functional Requirements (FRs)

### Navigation & Page Structure

**FR1: Channel admin page route**
A new route at `/channels` serves a dedicated page template. The page follows the existing layout pattern: header (with navigation), page title, content area.

**FR2: Navigation link**
The dashboard header navigation includes a "Channels" link alongside existing links (Dashboard, Personas, Projects, Activity). The link highlights when the operator is on the `/channels` page.

### Channel List

**FR3: Channel list table**
The page displays a table of all channels visible to the operator. Columns: name (linked to detail view or expandable), type (badge), status (colour-coded label), members (count with tooltip showing names), last activity (relative time), created date, actions (lifecycle buttons). Default sort: active channels first, then by last activity descending.

**FR4: Status filter**
A set of filter tabs or a dropdown above the table allows filtering by channel status: Active (default on page load), Pending, Complete, Archived, All. The selected filter is visually indicated. Filter state persists during the session (not across page reloads). The "All" filter genuinely shows all channels including archived — no hidden exclusions.

**FR5: Text search**
A search input filters the channel list by name or slug as the operator types (client-side filtering for v1, given expected channel counts under 100). No server-side pagination in v1 — the full channel list is rendered client-side. If channel counts grow beyond 100, pagination should be added as a follow-up.

**FR6: Attention signals**
Active channels with no message activity in a configurable time window (default: 2 hours) display a visual attention indicator (e.g., amber dot or pulse). The threshold is defined in the page template or JS config for v1 — not a backend config change. If attention signals prove useful, the threshold should migrate to `config.yaml` in a future iteration to avoid config drift into JS. Attention signals help the operator identify channels that may be stale or stuck.

### Channel Detail

**FR7: Channel detail view**
Clicking a channel row or name expands an inline detail panel (or navigates to a detail section) showing: channel name, slug, type, status, description, chair persona, full member list (with status: active/muted/left), message count, created date, last activity date, and available lifecycle actions.

### Channel Creation

**FR8: Create channel form**
A "New Channel" button opens a create form (inline or modal) with fields: name (required), type (required, dropdown: workshop, delegation, review, standup, broadcast), description (optional), initial members (optional, persona autocomplete/picker). Submit calls `POST /api/channels`. On success, the new channel appears in the list.

**FR9: Persona picker for members**
The member selection field provides autocomplete search of available personas. The picker shows persona name and role. Selected personas appear as removable tags. The picker queries available personas from the existing API.

### Lifecycle Management

**FR10: Complete channel**
An active channel can be completed via a "Complete" button. The button calls `POST /api/channels/<slug>/complete`. On success, the channel's status updates in the list. The button is only visible/enabled for active channels.

**FR11: Archive channel**
A completed channel can be archived via an "Archive" button. The button calls `POST /api/channels/<slug>/archive`. On success, the channel moves to the archived filter group. The button is only visible/enabled for completed channels.

**FR12: Delete channel**
An archived channel (or a channel with no active members) can be deleted via a "Delete" button. The button is only visible/enabled for channels that are archived or have zero active members — active channels with members cannot be deleted directly (complete and archive first). Clicking delete opens a confirmation dialog ("Are you sure you want to permanently delete channel #[name]? This cannot be undone."). On confirmation, calls `DELETE /api/channels/<slug>` (endpoint must be added — see Section 7, API Gaps). On success, the channel is removed from the list.

### Member Management

**FR13: Add member to channel**
From the channel detail view, an "Add Member" action opens a persona picker. Selecting a persona calls `POST /api/channels/<slug>/members` with the persona slug. On success, the member appears in the detail view's member list.

**FR14: Remove member from channel**
From the channel detail view, each member row has a "Remove" action. Clicking it calls `DELETE /api/channels/<slug>/members/<persona_slug>` (or appropriate API). On success, the member is removed from the list. The operator cannot remove themselves if they are the sole chair (show error message).

### Real-Time Updates

**FR15: SSE-driven list updates**
The channel list subscribes to `channel_message` and `channel_update` SSE events. When a `channel_message` event arrives, the corresponding channel row's "last activity" column updates. When a `channel_update` event arrives (member join/leave, status transition), the corresponding row updates its member count and/or status.

---

## 5. Non-Functional Requirements (NFRs)

**NFR1: Vanilla JS only**
All JavaScript follows the existing IIFE pattern. No framework dependencies. No new npm packages.

**NFR2: Tailwind CSS styling**
All styling uses Tailwind utility classes and existing custom properties. New custom CSS goes in `static/css/src/input.css`, never directly in `main.css`.

**NFR3: Minimal new backend code**
The primary work is frontend. Data operations use existing S5 API endpoints where available. New backend code is limited to: (1) the page-serving route, and (2) any missing API endpoints identified in Section 7 (API Gaps) — specifically channel deletion and member removal. These are thin route handlers delegating to existing ChannelService methods.

**NFR4: Consistent page pattern**
The `/channels` page follows the same template structure and navigation pattern as `/personas` and `/activity`.

---

## 6. UI Overview

### Page Layout

```
┌─────────────────────────────────────────────────┐
│  Header: Dashboard | Channels* | Personas | ... │
├─────────────────────────────────────────────────┤
│  Channel Admin                    [+ New Channel]│
│                                                  │
│  [Active*] [Pending] [Complete] [Archived] [All]  │
│  [🔍 Search channels...]                        │
│                                                  │
│  ┌──────────────────────────────────────────┐    │
│  │ Name        Type    Status  Members Last │    │
│  │─────────────────────────────────────────│    │
│  │ api-review  review  ● active  3    2h ⚠ │    │
│  │ persona-wk  wkshop  ● active  4    5m   │    │
│  │ deploy-v3   deleg   ○ complete 2   1d   │    │
│  │ ...                                      │    │
│  └──────────────────────────────────────────┘    │
│                                                  │
│  ▼ Channel Detail: api-review                    │
│  ┌──────────────────────────────────────────┐    │
│  │ Type: review  Chair: Robbo  Status: act  │    │
│  │ Members: Robbo (active), Con (active),   │    │
│  │          Sam (active)      [+ Add Member]│    │
│  │ Messages: 47  Created: 2 days ago        │    │
│  │                                          │    │
│  │ [Complete]  [Archive]  [Delete]          │    │
│  └──────────────────────────────────────────┘    │
└─────────────────────────────────────────────────┘
```

### Interaction Flow

1. Operator clicks "Channels" in header navigation
2. Channel list loads with "Active" filter selected by default
3. Operator uses filter tabs to narrow by status
4. Operator clicks a channel row to expand detail panel
5. From detail panel: manage members, trigger lifecycle actions
6. "New Channel" button opens create form
7. SSE events keep the list current without page refresh

---

## 7. Dependencies

| Dependency | Sprint | Status | What It Provides |
|------------|--------|--------|------------------|
| Channel data model | E9-S3 | Done | Channel, ChannelMembership, Message tables |
| ChannelService | E9-S4 | Done | Service methods for all channel operations |
| API endpoints | E9-S5 | Done | REST API for channel CRUD, membership, messaging |
| Dashboard UI | E9-S7 | Done | Channel cards, chat panel (unaffected by this sprint) |

### Potential API Gaps

The following API endpoints may need to be added or verified before this sprint can be built:

- `DELETE /api/channels/<slug>` — channel deletion (verify if exists in S5)
- `DELETE /api/channels/<slug>/members/<persona_slug>` — member removal (verify if exists in S5)
- `GET /api/personas?active=true` — persona list for autocomplete picker (verify if exists)

If these endpoints do not exist, they must be added as pre-requisite tasks in this sprint's implementation.

---

## 8. Open Decisions

| Decision | Options | Status |
|----------|---------|--------|
| Chair transfer UI | Include in this PRD vs separate follow-up | **Deferred** — Sam to decide. Not blocking v1. |

---

## Document History

| Version | Date       | Author  | Changes |
|---------|------------|---------|---------|
| 1.0     | 2026-03-06 | Mel | Initial PRD from workshop with Sam and Robbo |
| 1.1     | 2026-03-06 | Mel | Robbo review fixes: default filter to Active (not misleading "All"), restrict delete to archived/empty channels, flag attention threshold config drift, explicit no-pagination v1 statement, fix NFR3 contradiction with API gaps, add modal deprecation |
