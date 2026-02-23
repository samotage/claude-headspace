---
validation:
  status: valid
  validated_at: '2026-02-23T15:22:59+11:00'
---

## Product Requirements Document (PRD) — Persona List & CRUD

**Project:** Claude Headspace
**Scope:** Dashboard UI for browsing, creating, editing, and archiving personas and roles
**Author:** PRD Workshop (AI-assisted)
**Status:** Draft

---

## Executive Summary

The persona system backend was built across Epic 8 Sprints 1-14, delivering database models, registration services, filesystem assets, skill injection, and CLI tooling. However, no management UI was implemented. Users can only interact with personas via CLI commands (`flask persona register`) or raw API calls, making the feature effectively invisible from the dashboard.

This PRD delivers the first half of the persona management UI: a dedicated Personas tab in the main navigation, a list page showing all registered personas, and full CRUD operations (create, edit, archive/delete) via modal forms. It also introduces role management inline during persona creation and the API endpoints needed to power the UI.

After this sprint, users will be able to discover, create, and manage personas entirely from the dashboard without touching the CLI.

---

## 1. Context & Purpose

### 1.1 Context
Epic 8 built a complete persona backend: Role and Persona models, registration service, filesystem asset creation, skill injection via tmux, CLI commands, and session hook integration. The only UI touchpoints are persona name/role display on agent cards (S10) and the agent info panel (S11). There is no way to browse, create, edit, or delete personas from the dashboard.

### 1.2 Target User
Dashboard users who want to define and manage agent personas — giving their Claude Code agents named identities with specific roles and specialisations.

### 1.3 Success Moment
A user opens the Personas tab, sees all their defined personas at a glance, clicks "New Persona", fills in a name and role, and the persona appears in the list ready to be assigned to an agent.

---

## 2. Scope

### 2.1 In Scope
- Personas tab added to main navigation bar (top-level, alongside Projects/Config/Help)
- Persona list page (`/personas`) displaying all personas in a table
- Table columns: name, role, status (active/archived), number of linked agents, created date
- Create persona modal with fields: name (required), role (required — select from existing or create new), description (optional)
- Edit persona modal for updating name, description, and status
- Archive persona action with confirmation dialog
- Delete persona action with confirmation dialog (only when no agents are linked)
- Role listing within the create/edit flow (dropdown of existing roles with "create new" option)
- Toast notifications for all CRUD success/failure outcomes
- API endpoints to support all UI operations

### 2.2 Out of Scope
- Persona detail page with skill/experience content (E8-S16)
- Skill file editing (E8-S16)
- Experience log viewing (E8-S16)
- Persona selection during agent creation (E8-S17)
- Bulk operations (multi-select, bulk archive)
- Persona templates, cloning, or import/export
- Persona analytics or usage metrics
- Search or filtering on the list page (can be added later if list grows large)

---

## 3. Success Criteria

### 3.1 Functional Success Criteria
1. User can navigate to a "Personas" tab from the main navigation bar on any page
2. Persona list page displays all registered personas with name, role, status, agent count, and creation date
3. User can create a new persona from a modal form, selecting an existing role or creating a new one inline
4. User can edit a persona's name, description, and status from the list page
5. User can archive a persona (sets status to archived, persona remains in DB but is visually distinguished)
6. User can delete a persona that has no linked agents, with a confirmation step
7. Attempting to delete a persona with linked agents shows an error explaining why deletion is blocked
8. All CRUD operations display toast notifications on success or failure
9. The list page reflects changes immediately after create/edit/archive/delete without requiring a page refresh

### 3.2 Non-Functional Success Criteria
1. List page loads within 1 second for up to 50 personas
2. Modal forms validate required fields before submission

---

## 4. Functional Requirements (FRs)

**Navigation:**
- FR1: A "Personas" tab shall be added to the main navigation bar, positioned after "Help"
- FR2: The Personas tab shall link to `/personas` and highlight as active when on that page

**List Page:**
- FR3: The `/personas` page shall display a table of all personas ordered by creation date (newest first)
- FR4: Each row shall show: persona name, role name, status badge (active = green, archived = muted), count of currently linked agents, and creation date
- FR5: Each row shall have action buttons for Edit and Archive/Delete
- FR6: Archived personas shall be visually distinguished (muted text/row styling)
- FR7: An empty state message shall be shown when no personas exist, with a prompt to create one
- FR8: A "New Persona" button shall be prominently placed above the table

**Create Modal:**
- FR9: The create modal shall have fields: Name (text, required), Role (dropdown, required), Description (textarea, optional)
- FR10: The Role dropdown shall list all existing roles and include a "Create new role..." option
- FR11: Selecting "Create new role..." shall reveal an inline text field for the new role name
- FR12: On submission, the persona shall be created via the API and the list shall update without page reload
- FR13: Validation errors (empty name, empty role) shall be displayed inline on the form

**Edit Modal:**
- FR14: The edit modal shall pre-populate with the persona's current name, role (read-only), description, and status
- FR15: Role shall not be editable after creation (display only)
- FR16: Status can be toggled between active and archived
- FR17: On save, changes shall be persisted via the API and the list row shall update

**Delete/Archive:**
- FR18: Archive action shall set the persona's status to "archived" with a confirmation step
- FR19: Delete action shall only be available for personas with zero linked agents
- FR20: Delete action shall require a confirmation dialog stating the action is irreversible
- FR21: Attempting to delete a persona with linked agents shall display an error message indicating which agents are using it

**API Endpoints:**
- FR22: A list endpoint shall return all personas with their role name, status, and linked agent count
- FR23: A get endpoint shall return a single persona's full details by slug
- FR24: An update endpoint shall accept changes to name, description, and status
- FR25: A delete endpoint shall remove a persona only if it has no linked agents, returning an error otherwise
- FR26: A roles list endpoint shall return all available roles

---

## 5. Non-Functional Requirements (NFRs)

- NFR1: All API endpoints shall return appropriate HTTP status codes (200, 201, 400, 404, 409)
- NFR2: The create and edit modals shall follow existing modal patterns (project form modal styling, z-index conventions, backdrop blur)
- NFR3: The list page shall follow existing page patterns (extends base.html, consistent header/tab styling)

---

## 6. UI Overview

**Personas List Page (`/personas`):**
- Header area with page title "Personas" and a "New Persona" button (primary cyan styling)
- Table with columns: Name, Role, Status, Agents, Created
- Each row has Edit (pencil icon or text link) and Archive/Delete action buttons
- Status shown as a small badge: green "Active" or muted "Archived"
- Agent count is a simple number (clickable in future to navigate to detail, but not in this sprint)
- Empty state: centred message "No personas yet" with a "Create your first persona" call-to-action

**Create/Edit Persona Modal:**
- Follows project form modal pattern (fixed position, backdrop blur, header/body/footer layout)
- Name field: text input with required indicator
- Role field: dropdown select with existing roles + "Create new role..." option at bottom
- Inline new role input: appears below dropdown when "Create new role..." is selected
- Description field: textarea (optional, 2-3 rows)
- Status toggle: only in edit modal (active/archived switch or dropdown)
- Footer: Cancel (secondary) and Save (primary cyan) buttons
- Inline error display above form fields
