---
validation:
  status: valid
  validated_at: '2026-02-20T15:50:11+11:00'
---

## Product Requirements Document (PRD) — Persona Registration

**Project:** Claude Headspace v3.1
**Scope:** Epic 8, Sprint 6 (E8-S6) — Persona registration CLI command and optional API endpoint for end-to-end persona creation
**Author:** Sam (workshopped with Claude)
**Status:** Draft

---

## Executive Summary

Claude Headspace personas are first-class entities with a dual representation: a database record for identity and metadata, and a filesystem directory for skill and experience assets. Creating a persona currently requires manual coordination between these two systems — there is no single operation that creates both the DB record and the filesystem assets together.

This PRD specifies a persona registration operation that accepts a persona name, role name, and optional description, then executes the full creation flow in one invocation: looks up or creates the Role record, inserts the Persona record with an auto-generated slug, creates the filesystem directory at `data/personas/{slug}/`, and seeds the skill.md and experience.md template files. The operation is exposed primarily as a Flask CLI command (`flask persona register`) because CLI commands are agent-operable via tools without MCP context pollution. An optional REST API endpoint provides the same operation for programmatic access.

Persona registration is the operational gateway to the entire persona system. Every downstream sprint — persona-aware agent creation (E8-S7), session correlator assignment (E8-S8), skill injection (E8-S9), and dashboard identity display (E8-S10) — requires personas to exist in the database with filesystem assets on disk.

---

## 1. Context & Purpose

### 1.1 Context

The Persona database model (E8-S1) defines the schema for persona identity: slug, name, description, status, and role_id FK. The filesystem asset convention (E8-S5) defines the directory structure (`data/personas/{slug}/`) and provides utility functions for creating directories, seeding templates, and reading files. What's missing is the orchestration layer that coordinates both systems into a single, user-facing registration operation.

Without registration, creating a persona requires manually inserting DB records, generating the correct slug, creating the directory, and seeding template files — an error-prone, multi-step process. Registration makes persona creation a single command that any operator or agent can execute.

### 1.2 Target User

- **Operator (Sam):** Registers personas via CLI before launching persona-aware agent sessions. Primary user in v1.
- **Agents (future):** PM automation (Gavin v3) may register personas programmatically. CLI is agent-operable via tools.
- **Dashboard/API consumers:** Programmatic registration via REST endpoint for dashboard-initiated persona creation.

### 1.3 Success Moment

The operator runs `flask persona register --name Con --role developer --description "Backend Python developer"` and sees confirmation that persona "developer-con-1" was created with its filesystem directory and template files. The persona is immediately ready for agent assignment via `claude-headspace start --persona developer-con-1`.

---

## 2. Scope

### 2.1 In Scope

- A registration operation that creates a Persona end-to-end (DB record + filesystem assets) in a single invocation
- Role lookup-or-create: if the role exists (case-insensitive match), reuse it; if not, create it
- Persona record creation with auto-generated slug (`{role}-{name}-{id}`, all lowercase)
- Filesystem directory creation at `data/personas/{slug}/` via E8-S5 asset utilities
- Seeding of skill.md and experience.md template files via E8-S5 asset utilities
- Flask CLI command: `flask persona register --name <name> --role <role> [--description <desc>]`
- Input validation: name required, role required; role name lowercased on input
- Clear output on success: created persona slug, database ID, and filesystem path
- Clear error reporting on failure (including partial failures where DB succeeds but filesystem fails)
- Optional REST API endpoint for programmatic persona registration

### 2.2 Out of Scope

- Persona listing, updating, archiving, or deletion operations
- Persona-aware agent creation (E8-S7 — separate PRD)
- Skill file content editing or curation
- Skill file injection into agent sessions (E8-S9)
- Dashboard display of personas (E8-S10/S11)
- Role management CLI (roles are created implicitly through persona registration)
- Bulk registration or import operations
- The `data/personas/` directory convention and asset utility functions themselves (E8-S5 — consumed, not created)

---

## 3. Success Criteria

### 3.1 Functional Success Criteria

1. `flask persona register --name Con --role developer --description "Backend Python developer"` creates a Role "developer", a Persona "developer-con-1", directory `data/personas/developer-con-1/`, and seeds both template files
2. Running the same command again creates a second persona with a unique slug (e.g., `developer-con-2`) — no collision, no error
3. If a Role "developer" already exists, the registration reuses it rather than creating a duplicate
4. `--role Developer` (any case) matches an existing `developer` role — role name is lowercased on input
5. Missing `--name` or `--role` produces a clear error message without creating any records
6. Registration output displays the created persona's slug, database ID, and filesystem path
7. If filesystem creation fails after DB insert, the error is reported clearly with the persona ID for manual remediation — the DB record is not rolled back
8. Optional API endpoint accepts the same parameters and returns the created persona as JSON

### 3.2 Non-Functional Success Criteria

1. The registration service function is testable without CLI or HTTP — callable directly with name, role, and description parameters
2. Persona name preserves original case in the `name` field; slug is fully lowercase

---

## 4. Functional Requirements (FRs)

**FR1: Registration Service Function**
The system shall provide a registration function that accepts a persona name (required), role name (required), and description (optional) and performs the full persona creation flow: role lookup/create, persona insert with auto-generated slug, filesystem directory creation, and template file seeding. The function shall return the created persona's slug, database ID, and filesystem path.

**FR2: Role Lookup or Create**
The registration operation shall look up an existing Role by name using case-insensitive matching (input is lowercased before lookup). If the role exists, it shall be reused. If it does not exist, a new Role record shall be created with the lowercased name.

**FR3: Persona Record Creation**
The registration operation shall create a new Persona record with the provided name (original case preserved), optional description, the resolved role_id FK, status "active", and an auto-generated slug. The slug shall follow the format `{role_name}-{persona_name}-{id}` with all components lowercased.

**FR4: Slug Generation**
The persona slug shall be generated as `{role_name}-{persona_name}-{id}` where role_name and persona_name are lowercased, and id is the Persona's database primary key. Since the id is part of the slug, each registration produces a unique slug even for duplicate name + role combinations.

**FR5: Filesystem Asset Creation**
After creating the Persona DB record, the registration operation shall create the persona's filesystem directory and seed template files by calling the E8-S5 asset utility functions. The directory path is `data/personas/{slug}/`. Template files (skill.md and experience.md) are seeded with the persona's name and role name.

**FR6: Input Validation**
The registration operation shall validate that persona name and role name are provided and non-empty. Missing or empty values shall produce a clear error message. No DB records shall be created if validation fails.

**FR7: Flask CLI Command**
The system shall provide a Flask CLI command `flask persona register` with the following options:
- `--name` (required): Persona name (e.g., "Con")
- `--role` (required): Role name (e.g., "developer") — lowercased on input
- `--description` (optional): Persona description

The command shall output the created persona's slug, database ID, and filesystem path on success, or a clear error message on failure.

**FR8: API Endpoint (Optional)**
The system shall provide a REST endpoint for programmatic persona registration. The endpoint shall accept the same parameters as the CLI command (name, role, description) and return the created persona as a JSON response including slug, id, and filesystem path. Appropriate HTTP status codes shall be used for success (201) and error cases (400 for validation, 500 for server errors).

**FR9: Error Reporting for Partial Failures**
If the Persona DB record is created successfully but filesystem creation fails, the system shall report the error clearly, including the persona's database ID and slug so the operator can remediate. The DB record shall not be rolled back.

**FR10: Duplicate Handling**
Registering a persona with the same name and role as an existing persona shall succeed, producing a new Persona record with a unique slug (different database ID ensures slug uniqueness). This is not an error condition.

---

## 5. Non-Functional Requirements (NFRs)

**NFR1: Testable Service Layer**
The registration logic shall be implemented as a service function callable without CLI or HTTP context. The CLI command and API endpoint shall be thin wrappers that call the service function and format the output.

**NFR2: Case Handling**
Role names shall be lowercased on input for storage and lookup. Persona names shall preserve original case in the `name` database field. The generated slug shall be fully lowercase.

**NFR3: Idempotency-Safety**
Registration does not need to be idempotent (each call creates a new persona). However, it shall not corrupt existing data — re-registering the same name and role shall produce a new unique record without affecting the existing one.

---

## 6. Design Decisions (Resolved)

All design decisions for this sprint were resolved in the Agent Teams Design Workshop:

| Decision | Resolution | Source |
|----------|------------|--------|
| Preferred interface | CLI — agent-operable via tools, no MCP context pollution | Workshop 3.1 |
| Directory creation ownership | Application creates directory on persona registration | Workshop 3.1 |
| Config.yaml involvement | None — persona definitions are domain data, not app config | Workshop 1.2 |
| Atomicity on partial failure | Report error, leave DB record; no rollback | Workshop (this PRD) |
| Role name normalisation | Lowercase on input for matching and storage | Workshop (this PRD) |
| Slug normalisation | Fully lowercase; name field preserves original case | Workshop 1.2, 2.1 |

---

## 7. Dependencies

### 7.1 Upstream Dependencies

- **E8-S1 (Role + Persona Models):** Role and Persona database tables with slug generation logic. Registration creates records in these tables.
- **E8-S5 (Persona Filesystem Assets):** Asset utility functions for directory creation, template seeding, and path resolution. Registration calls these functions after creating the DB record.

### 7.2 Downstream Dependants

- **E8-S7 (Persona-Aware Agent Creation):** Personas must be registered before they can be referenced in agent creation. Validates persona slug against the DB.
- **E8-S8 (SessionCorrelator Persona Assignment):** Looks up Persona by slug during session registration — persona must exist in DB.
- **E8-S9 (Skill File Injection):** Reads skill.md and experience.md from the filesystem path established at registration time.

---

## 8. Integration Points

- **Consumed service:** E8-S5 `persona_assets` utility module for filesystem operations
- **Consumed models:** E8-S1 `Role` and `Persona` SQLAlchemy models
- **New service:** Registration service function (core logic, callable without CLI/HTTP)
- **New CLI module:** Flask CLI command group for `flask persona register`
- **New route (optional):** REST endpoint for programmatic registration
- **Existing pattern:** Follows codebase conventions for CLI commands (`cli/launcher.py`), service registration (`app.extensions`), and route blueprints (`routes/`)
