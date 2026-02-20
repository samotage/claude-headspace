---
validation:
  status: valid
  validated_at: '2026-02-20T15:41:41+11:00'
---

## Product Requirements Document (PRD) — Persona Filesystem Assets

**Project:** Claude Headspace v3.1
**Scope:** Epic 8, Sprint 5 (E8-S5) — Persona filesystem asset convention, template files, and path resolution utilities
**Author:** Sam (workshopped with Claude)
**Status:** Draft

---

## Executive Summary

Claude Headspace agents are driven by personas — named identities with persistent skills and accumulated experience. Each persona has a filesystem directory containing markdown asset files that define who the persona is (skill.md) and what it has learned (experience.md). These files are the priming material injected into agents at session startup, transforming anonymous Claude Code sessions into recognisable team members.

This PRD establishes the `data/personas/{slug}/` directory convention, defines the template structure for skill.md and experience.md files, and specifies the utility functions that downstream sprints (registration, injection, handoff) use to create, read, and check persona assets. The filesystem convention complements the Persona database model (E8-S1) — the DB stores identity and metadata; the filesystem stores behaviour and experience.

All architectural decisions for this sprint are resolved. The `data/` directory is a project convention (not a configurable setting), the slug format `{role}-{name}-{id}` provides natural filesystem sorting, and skill files are lightweight priming signals with no token budget management.

---

## 1. Context & Purpose

### 1.1 Context

The Persona database model (E8-S1) establishes persona identity in PostgreSQL — slug, name, role, status. But a persona's *behaviour* lives in markdown files: a skill file that defines core competencies and working style, and an experience log that accumulates learned knowledge over time. These files are read by the skill injection system (E8-S9) and sent to agents as their first-prompt priming message via the tmux bridge.

The filesystem needs a standard convention so that every downstream sprint — registration (E8-S6), injection (E8-S9), and handoff (E8-S14) — can locate, create, and read persona assets through a consistent interface.

### 1.2 Target User

- **Operator (Sam):** Curates skill.md files to shape persona behaviour. Edits files directly in the filesystem or via version control.
- **Downstream services:** Registration (E8-S6) creates directories and seeds templates. Injection (E8-S9) reads skill and experience content. Handoff (E8-S14) writes to the persona's handoff subdirectory.
- **Agents (future):** Agents may read and update their own experience.md through self-improvement loops.

### 1.3 Success Moment

A persona "Con" with role "developer" and slug "developer-con-1" has its asset directory at `data/personas/developer-con-1/` containing a skill.md that describes Con's identity and a blank experience.md ready for entries. Any service can resolve the slug to this path, read either file's content, or check whether the assets exist — all through a single utility module.

---

## 2. Scope

### 2.1 In Scope

- `data/personas/{slug}/` directory convention as the standard location for persona filesystem assets
- `skill.md` template file structure — seeded with persona name, role, and section scaffolding (Core Identity, Skills & Preferences, Communication Style)
- `experience.md` template file structure — seeded with header and append-only convention marker
- Utility function to resolve a persona slug to its filesystem directory path
- Utility function to read skill.md content given a persona slug
- Utility function to read experience.md content given a persona slug
- Utility function to check whether asset files exist for a given persona slug
- Utility function to create a persona's directory and seed template files
- New service module at `src/claude_headspace/services/persona_assets.py`

### 2.2 Out of Scope

- Persona database model creation (E8-S1 — prerequisite, not this sprint)
- Persona registration CLI/API (E8-S6 — consumes these utilities)
- Skill file injection into agent sessions (E8-S9 — consumes these utilities)
- Handoff file storage at `data/personas/{slug}/handoffs/` (E8-S14 — extends the directory convention)
- Token budget management for skill files (workshop decision 3.1: not needed — skill files are lightweight priming signals)
- Per-organisation skill extensions or overlays (workshop decision 3.1: deferred to Phase 2+)
- Config.yaml involvement in path resolution (workshop decision 1.2: path is a project convention, not a configurable setting)
- Writing to or appending entries to experience.md (future sprint concern — experience accumulation is a separate capability)
- Git tracking decisions for persona asset files (operator decides what to track — not an application concern)

---

## 3. Success Criteria

### 3.1 Functional Success Criteria

1. Given a persona slug (e.g., "developer-con-1"), the system resolves to the correct filesystem path (`data/personas/developer-con-1/`)
2. Persona directory and template files can be created programmatically in a single operation
3. Seeded skill.md contains the persona's name and role in the template headings
4. Seeded experience.md contains a header identifying the persona and the append-only convention
5. Reading skill.md returns the file content as a string, or indicates the file does not exist
6. Reading experience.md returns the file content as a string, or indicates the file does not exist
7. Existence check reports whether skill.md, experience.md, or both are present for a given slug
8. Path resolution works independently of whether the Persona DB record exists (pure filesystem operations based on slug string)
9. Missing parent directories are created automatically when seeding template files
10. All utility functions handle edge cases gracefully: missing files, missing directories, empty slugs

### 3.2 Non-Functional Success Criteria

1. Utility functions are stateless — no database dependency, no app context requirement for path resolution
2. File operations use the established codebase pattern (pathlib.Path, UTF-8 encoding)

---

## 4. Functional Requirements (FRs)

**FR1: Persona Asset Path Convention**
The system shall use `data/personas/{slug}/` as the standard filesystem location for persona assets, where `{slug}` is the persona's slug (format: `{role}-{name}-{id}`, e.g., "developer-con-1"). The `data/` directory is at the project root. This path is a project convention — not stored on the Persona model and not configurable via config.yaml.

**FR2: Path Resolution**
The system shall provide a function that accepts a persona slug and returns the resolved filesystem path to the persona's asset directory. The function shall work with the slug string alone — no database lookup required.

**FR3: Directory Creation**
The system shall provide a function that creates a persona's asset directory, including any missing parent directories (`data/`, `data/personas/`). If the directory already exists, the function shall not fail or overwrite existing content.

**FR4: Skill File Template Seeding**
The system shall provide a function that creates a `skill.md` file in a persona's asset directory, seeded with a template that includes:
- A heading with the persona's name and role (e.g., "# Con — developer")
- Section scaffolding: Core Identity, Skills & Preferences, Communication Style
- Placeholder guidance text in each section

The template structure:

```markdown
# {Persona Name} — {Role Name}

## Core Identity
[Who this persona is — 1-2 sentences]

## Skills & Preferences
[Key competencies and working style]

## Communication Style
[How this persona communicates]
```

**FR5: Experience File Template Seeding**
The system shall provide a function that creates an `experience.md` file in a persona's asset directory, seeded with a template that includes:
- A heading identifying the persona (e.g., "# Experience Log — Con")
- Convention markers indicating append-only format with newest entries at top

The template structure:

```markdown
# Experience Log — {Persona Name}

<!-- Append-only. New entries added at the top. -->
<!-- Periodically curated to remove outdated learnings. -->
```

**FR6: Combined Directory and Template Creation**
The system shall provide a single function that creates a persona's directory and seeds both template files (skill.md and experience.md) in one operation. This function accepts the persona slug, persona name, and role name as inputs. If template files already exist, they shall not be overwritten.

**FR7: Read Skill File**
The system shall provide a function that reads and returns the content of a persona's skill.md file given a slug. If the file does not exist, the function shall return a result indicating absence (not raise an exception).

**FR8: Read Experience File**
The system shall provide a function that reads and returns the content of a persona's experience.md file given a slug. If the file does not exist, the function shall return a result indicating absence (not raise an exception).

**FR9: Asset Existence Check**
The system shall provide a function that checks whether persona asset files exist on disk for a given slug. The check shall report the presence of skill.md and experience.md independently (both, one, or neither may exist).

**FR10: Service Module**
The system shall provide all persona asset utility functions in a single service module. The module shall follow codebase conventions for path management (pathlib.Path, relative paths from project root) and file operations (UTF-8 encoding).

---

## 5. Non-Functional Requirements (NFRs)

**NFR1: No Database Dependency**
All persona asset utility functions shall operate on the filesystem using the slug string only. No database session, Flask app context, or Persona model query is required for path resolution, file reading, or existence checking.

**NFR2: Idempotent Operations**
Directory creation and template seeding shall be idempotent. Calling create functions multiple times for the same slug shall not corrupt or overwrite existing files.

**NFR3: Graceful Failure Handling**
All read and existence-check functions shall handle missing files and directories gracefully — returning appropriate absence indicators rather than raising exceptions. Creation functions shall handle pre-existing directories without error.

---

## 6. Design Decisions (Resolved)

All design decisions for this sprint were resolved in the Agent Teams Design Workshop:

| Decision | Resolution | Source |
|----------|------------|--------|
| Asset location | Convention-based `data/` directory at project root | Workshop 1.2 |
| Slug format | `{role}-{name}-{id}` for natural filesystem sorting | Workshop 1.2 |
| Config.yaml involvement | None — path is a project convention, not a setting | Workshop 1.2 |
| Token budget management | None — skill files are lightweight priming signals | Workshop 3.1 |
| Per-org skill extensions | Deferred to Phase 2+ | Workshop 3.1 |
| Directory creation ownership | Application manages it on persona registration | Workshop 3.1 |
| Skill file path storage on model | Not stored — derived from slug convention | Workshop 2.1 |

---

## 7. Dependencies

### 7.1 Upstream Dependencies

- **E8-S1 (Role + Persona Models):** The slug format `{role}-{name}-{id}` is defined by the Persona model. This sprint implements the filesystem convention that maps slugs to directories. The utility functions accept slugs as strings and do not depend on the Persona model existing in the database.

### 7.2 Downstream Dependants

- **E8-S6 (Persona Registration):** Registration creates the DB record and calls the combined directory + template creation function from this sprint.
- **E8-S9 (Skill File Injection):** Injection reads skill.md and experience.md content using the read functions from this sprint.
- **E8-S14 (Handoff Execution):** Handoff writes to `data/personas/{slug}/handoffs/` — extends the directory convention established by this sprint.

---

## 8. Integration Points

- **New file:** `src/claude_headspace/services/persona_assets.py` — the utility module created by this sprint
- **Existing pattern:** Follows `waypoint_editor.py` and `path_constants.py` conventions for path management and file operations
- **.gitignore consideration:** The `data/` directory already has entries for `data/logs/`, `data/projects/*`, etc. The `data/personas/` directory may or may not be gitignored — this is an operator decision (skill files are intentionally version-controllable)
