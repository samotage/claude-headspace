---
validation:
  status: valid
  validated_at: '2026-02-23T15:23:01+11:00'
---

## Product Requirements Document (PRD) — Persona-Aware Agent Creation

**Project:** Claude Headspace
**Scope:** Persona selection during agent creation from dashboard and CLI persona discovery
**Author:** PRD Workshop (AI-assisted)
**Status:** Draft

---

## Executive Summary

Sprints 15 and 16 deliver persona management UI (list, CRUD, detail, skill editing). This sprint closes the loop by integrating persona selection into the agent creation workflow — both from the dashboard UI and the CLI.

Currently, personas can only be assigned to agents via the CLI launcher (`claude-headspace start --persona <slug>`), which requires knowing the exact slug. This sprint adds a persona selector to the dashboard's agent creation flow and enhances the CLI with persona discovery commands and short-name matching, so users can easily find and assign personas when launching new agents.

After this sprint, the full persona lifecycle is complete: create personas (S15), define their skills (S16), and assign them to agents when launching sessions (S17) — all from the dashboard or CLI.

---

## 1. Context & Purpose

### 1.1 Context
The persona backend supports agent-persona assignment: the launcher passes `CLAUDE_HEADSPACE_PERSONA_SLUG` to the session, the session-start hook looks up the persona and assigns it to the agent, and skill injection delivers the persona's skill.md content via tmux. However, the dashboard has no agent creation flow that includes persona selection, and the CLI requires users to know the exact slug (e.g., `developer-con-1`) with no way to discover or search for personas.

### 1.2 Target User
Users launching new Claude Code agent sessions who want to assign a persona identity, either from the dashboard or the command line.

### 1.3 Success Moment
A user clicks "New Agent" on the dashboard, selects a project and a persona from a dropdown showing available personas with their roles, launches the session, and sees the agent card immediately display the persona's name and role.

---

## 2. Scope

### 2.1 In Scope
- Persona selector in the dashboard agent creation/launch flow
- Persona quick-info display during selection (role, description preview)
- Agent creation API accepting optional `persona_slug` parameter
- CLI `flask persona list` command showing all available personas
- CLI short-name matching for the `--persona` flag (e.g., `--persona con` resolves to `developer-con-1`)
- Disambiguation prompt when short-name matches multiple personas
- Persona filter on the persona selector (active personas only, grouped by role)

### 2.2 Out of Scope
- Persona CRUD operations (E8-S15)
- Persona detail page and skill editing (E8-S16)
- Modifying the skill injection mechanism (already working)
- Creating personas inline during agent creation (user should create via Personas tab first)
- Agent re-assignment to a different persona after creation
- Batch agent creation with personas

---

## 3. Success Criteria

### 3.1 Functional Success Criteria
1. User can select a persona from a dropdown when creating/launching an agent from the dashboard
2. The persona selector shows persona name, role, and description preview for each option
3. Persona selection is optional — agents can still be created without a persona
4. The selected persona is passed to the agent creation flow and the agent card displays the persona identity immediately
5. CLI `flask persona list` displays all personas with name, role, slug, and status
6. CLI `--persona` flag accepts short names (e.g., `con`) and resolves to the correct slug
7. When a short name matches multiple personas, the CLI presents a disambiguation prompt
8. Only active personas appear in the dashboard selector and CLI list by default

### 3.2 Non-Functional Success Criteria
1. Persona selector loads the persona list within 500ms
2. CLI short-name matching is case-insensitive

---

## 4. Functional Requirements (FRs)

**Dashboard Persona Selector:**
- FR1: The agent creation/launch flow shall include an optional persona selector field
- FR2: The selector shall display personas grouped by role (e.g., "Developer" group, "Tester" group)
- FR3: Each persona option shall show: name, role badge, and first line of description (if available)
- FR4: A "None" or empty option shall be the default, allowing agent creation without a persona
- FR5: Only active personas shall appear in the selector (archived personas are excluded)
- FR6: The selected persona slug shall be included in the agent creation/session start request

**Agent Creation API:**
- FR7: The agent creation endpoint shall accept an optional `persona_slug` parameter
- FR8: When `persona_slug` is provided, the endpoint shall validate the persona exists and is active
- FR9: If the persona is not found or is archived, the endpoint shall return a clear error message
- FR10: The created agent shall be associated with the matching persona

**CLI Persona List:**
- FR11: `flask persona list` shall display all personas in a formatted table
- FR12: Table columns: Name, Role, Slug, Status, Agents (count of linked agents)
- FR13: A `--active` flag shall filter to active personas only
- FR14: A `--role` flag shall filter by role name
- FR15: Output shall be sorted alphabetically by name within each role

**CLI Short-Name Matching:**
- FR16: The `--persona` flag shall accept partial names (short names) in addition to full slugs
- FR17: Short-name matching shall be case-insensitive and match against the persona's name field
- FR18: If exactly one persona matches the short name, it shall be used automatically
- FR19: If multiple personas match, the CLI shall present a numbered list and prompt the user to choose
- FR20: If no personas match, the CLI shall display available personas and exit with an error

---

## 5. Non-Functional Requirements (NFRs)

- NFR1: The persona selector shall follow existing form field patterns (dropdown styling consistent with project selector)
- NFR2: CLI output shall follow existing CLI formatting conventions (consistent with other `flask` commands)
- NFR3: Short-name matching shall not require exact prefix matching — substring matching is acceptable (e.g., `con` matches `Conrad`)

---

## 6. UI Overview

**Dashboard Agent Creation Flow:**
- Existing agent creation UI (or new if none exists yet) gains a "Persona" field
- Persona field: dropdown/select with search capability
- Options grouped by role heading (e.g., "-- Developer --", "-- Tester --")
- Each option shows: persona name + brief description
- Default selection: "No persona" (blank/none)
- Placement: after project selector, before launch/create button

**CLI `flask persona list` Output:**
```
Available Personas:
  Name        Role        Slug              Status   Agents
  ────────    ────────    ────────────────   ──────   ──────
  Con         developer   developer-con-1    active   2
  Archie      architect   architect-archie-3 active   0
  Tess        tester      tester-tess-2      active   1

3 personas (3 active, 0 archived)
```

**CLI Short-Name Disambiguation:**
```
$ claude-headspace start --persona dev

Multiple personas match "dev":
  1. Con (developer-con-1) — developer
  2. Dana (developer-dana-4) — developer

Select persona [1-2]:
```
