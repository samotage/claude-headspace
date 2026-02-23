---
validation:
  status: valid
  validated_at: '2026-02-23T15:22:17+11:00'
---

## Product Requirements Document (PRD) — Persona Detail Page & Skill Editor

**Project:** Claude Headspace
**Scope:** Persona detail view with skill file editor, experience log viewer, and linked agent display
**Author:** PRD Workshop (AI-assisted)
**Status:** Draft

---

## Executive Summary

Sprint 15 delivers persona list and CRUD operations. This sprint adds the persona detail page — a dedicated view for each persona showing its full profile, a markdown editor for the skill file, a read-only viewer for the experience log, and a list of agents currently using the persona.

The skill editor is the centrepiece: it allows users to define and refine what a persona knows and how it behaves, using markdown with a live preview. This is the content that gets injected into agent sessions via the tmux bridge, making it the primary mechanism for shaping agent behaviour.

After this sprint, users have end-to-end persona management: browse the list (S15), drill into any persona to see its full profile, edit its skill definition, review its accumulated experience, and see which agents are using it.

---

## 1. Context & Purpose

### 1.1 Context
Sprint 15 provides the persona list page and CRUD operations (create, edit, archive, delete). The persona backend already manages filesystem assets — each persona has a `data/personas/{slug}/` directory containing `skill.md` (user-editable identity definition) and `experience.md` (append-only log of accumulated learnings). These files currently can only be edited by hand in the filesystem.

### 1.2 Target User
Users who want to define and refine persona behaviour by editing skill files, review what a persona has learned through its experience log, and understand which agents are currently using a persona.

### 1.3 Success Moment
A user clicks a persona name in the list, sees its full profile, opens the skill editor, refines the persona's communication style and domain knowledge, saves it, and sees the updated content in the preview — knowing this will be injected into the next agent session that uses this persona.

---

## 2. Scope

### 2.1 In Scope
- Persona detail page (`/personas/<slug>`) showing full persona profile
- Page sections: metadata header, skill content, experience log, linked agents
- Skill file editor with markdown editing and preview modes (following waypoint editor pattern)
- Experience log viewer (read-only, rendered markdown)
- Linked agents list showing agents currently assigned to this persona
- Back navigation to persona list
- API endpoints for skill file read/write, experience file read, and persona asset status

### 2.2 Out of Scope
- Experience log editing (append-only by design, modified by the skill injection system)
- Persona CRUD operations (covered in E8-S15)
- Persona selection during agent creation (E8-S17)
- Skill file version history or diffing
- Skill file templates or starter content beyond what the registration service already seeds
- Real-time skill content sync across multiple editors

---

## 3. Success Criteria

### 3.1 Functional Success Criteria
1. User can navigate from the persona list to a detail page by clicking a persona's name
2. Detail page displays persona metadata: name, role, slug, status, creation date, description
3. User can view the persona's skill.md content rendered as markdown
4. User can switch to edit mode and modify the skill.md content in a text editor
5. User can preview skill.md changes as rendered markdown before saving
6. User can save skill.md edits, which persist to the filesystem
7. User can view the persona's experience.md content rendered as markdown (read-only)
8. User can see a list of agents currently linked to this persona with their status
9. An empty state is shown for skill content, experience content, or linked agents when none exist
10. Toast notifications confirm successful save or report errors

### 3.2 Non-Functional Success Criteria
1. Skill editor handles files up to 50KB without performance issues
2. Detail page loads within 1 second including file content

---

## 4. Functional Requirements (FRs)

**Detail Page Layout:**
- FR1: The detail page shall be accessible at `/personas/<slug>`
- FR2: A back link/button shall navigate to the persona list page
- FR3: The page header shall display the persona's name, role, and status badge
- FR4: Below the header, the page shall show metadata: slug, description, creation date
- FR5: The page shall have distinct sections for Skill, Experience, and Linked Agents

**Skill Section:**
- FR6: The skill section shall display skill.md content rendered as markdown by default (view mode)
- FR7: An "Edit" button shall switch the skill section to edit mode
- FR8: Edit mode shall show the raw markdown in a monospace textarea
- FR9: A "Preview" tab/button shall render the current textarea content as markdown without saving
- FR10: A "Save" button shall persist the textarea content to the skill.md file via the API
- FR11: A "Cancel" button shall discard edits and return to view mode with the last saved content
- FR12: If skill.md does not exist, an empty state shall be shown with an option to create it
- FR13: Unsaved changes shall be indicated visually (e.g., "Unsaved changes" label or modified indicator)

**Experience Section:**
- FR14: The experience section shall display experience.md content rendered as markdown
- FR15: The experience section shall be read-only (no edit controls)
- FR16: If experience.md does not exist or is empty, an informational empty state shall be shown
- FR17: The experience section shall display the file's last modified timestamp if available

**Linked Agents Section:**
- FR18: The linked agents section shall list all agents currently assigned to this persona
- FR19: Each agent entry shall show: agent display name or session ID, project name, current state, last seen time
- FR20: If no agents are linked, an empty state message shall be shown
- FR21: Agent entries shall be clickable to navigate to the agent's card on the dashboard (or open agent info)

**API Endpoints:**
- FR22: A skill read endpoint shall return the raw markdown content of skill.md for a given persona slug
- FR23: A skill write endpoint shall accept markdown content and write it to skill.md for a given persona slug
- FR24: An experience read endpoint shall return the raw markdown content of experience.md for a given persona slug
- FR25: An asset status endpoint shall report which files exist (skill.md, experience.md) for a given persona slug
- FR26: A linked agents endpoint shall return agents currently assigned to the persona with their status

---

## 5. Non-Functional Requirements (NFRs)

- NFR1: The skill editor shall follow the same modal/tab patterns as the waypoint editor (Edit/Preview tabs, monospace textarea, prose-styled preview)
- NFR2: Markdown rendering shall use the existing marked.js + DOMPurify pipeline
- NFR3: The detail page layout shall follow the project show page pattern (slug-based routing, section headings with action buttons)

---

## 6. UI Overview

**Persona Detail Page (`/personas/<slug>`):**
- Back link at top: "< Back to Personas"
- Header: Large persona name, role badge, status badge (active/archived)
- Metadata bar: Slug (copyable), description, created date
- Three content sections stacked vertically:

**Skill Section:**
- Section heading "Skill Definition" with Edit button
- Default view: rendered markdown (prose styling)
- Edit mode: textarea (monospace, full width, ~20 rows) with tab bar (Edit | Preview)
- Footer bar with Save (cyan) and Cancel (secondary) buttons
- Status indicator: "Unsaved changes" when modified

**Experience Section:**
- Section heading "Experience Log"
- Rendered markdown (prose styling), read-only
- Last modified timestamp shown below content
- Empty state: "No experience recorded yet. Experience is accumulated automatically as this persona works across sessions."

**Linked Agents Section:**
- Section heading "Active Agents"
- Simple list/table: agent name/ID, project, state badge, last seen
- Empty state: "No agents are currently using this persona."
