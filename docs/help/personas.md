# Personas

Personas give your Claude Code agents persistent identities. Instead of anonymous session UUIDs, agents appear on the dashboard as named team members like "Con — developer" with accumulated skills and experience.

## What is a Persona?

A persona is a named identity assigned to a Claude Code agent. Each persona has:

- **Name** — A display name (e.g., "Con", "Robbo", "Verner")
- **Role** — A specialisation (e.g., developer, tester, architect, pm)
- **Slug** — An auto-generated identifier in the format `{role}-{name}-{id}` (e.g., `developer-con-1`)
- **Skill file** — A markdown document describing the persona's competencies, preferences, and working style
- **Experience log** — An append-only file capturing lessons learned across sessions

When an agent starts with a persona, its skill file is automatically injected into the session via the tmux bridge, giving the agent context about who it is and how it should work.

## Managing Personas

The **Personas** page (`/personas`) lets you browse, create, edit, and manage all your personas from the dashboard. Access it from the Personas tab in the main navigation.

### The Personas List

The list shows all personas in a table with:

- **Name** — Click to open the persona's detail page
- **Role** — The persona's specialisation
- **Status** — Active (green) or Archived (muted)
- **Agents** — Count of linked agents
- **Created** — Registration date

### Creating a Persona (UI)

Click **New Persona** to open the creation form:

1. **Name** (required) — The persona's display name
2. **Role** — Select an existing role from the dropdown, or choose "Create new role" to define one
3. **Description** (optional) — A brief summary of the persona's purpose

On save, the persona is registered in the database and its filesystem assets (skill.md, experience.md) are created automatically.

### Editing a Persona

Click the edit icon on any persona row to modify its name, description, or status. The role cannot be changed after creation.

### Archiving a Persona

Set a persona's status to "Archived" via the edit form. Archived personas:

- Appear muted in the list
- Do not appear in the agent creation persona selector
- Retain all their data and linked agents

### Deleting a Persona

Click the delete icon to remove a persona permanently. Deletion is only allowed for personas with **zero linked agents**. If agents are still linked, you'll see a message explaining which agents must be reassigned first.

## Registering a Persona (CLI & API)

You can also register personas without the UI.

### Via CLI

```bash
flask persona register --name "Con" --role "developer"
```

### Via API

```bash
curl -X POST https://your-server:5055/api/personas/register \
  -H "Content-Type: application/json" \
  -d '{"name": "Con", "role": "developer"}'
```

Both methods return the persona's slug, database ID, and filesystem path.

### What Registration Creates

1. **Role record** — If the role doesn't exist yet, it's created automatically (lowercased)
2. **Persona record** — Database entry with auto-generated slug
3. **Asset directory** — `data/personas/{slug}/` with two template files:
   - `skill.md` — Identity, skills, and communication style (edit this to define the persona)
   - `experience.md` — Append-only experience log (grows over time)

## Persona Detail Page

Click a persona's name in the list to open its detail page at `/personas/<slug>`. The detail page shows:

- **Header** — Persona name, role badge, and status badge
- **Metadata** — Slug (monospace), description, and creation date
- **Skill file** — Rendered markdown with an inline editor
- **Experience log** — Read-only rendered view with last-modified timestamp
- **Linked agents** — Table of agents currently using this persona

## Editing the Skill File

The skill file defines who the persona is. You can edit it in two ways:

### Via the Detail Page (Recommended)

On the persona's detail page, the skill section shows the rendered markdown content. Click **Edit** to switch to the inline editor:

- **Edit tab** — A monospace textarea for writing markdown
- **Preview tab** — Live rendered preview of your changes
- **Unsaved changes indicator** — Appears when you have unsaved edits
- **Save** — Writes the content to the filesystem
- **Cancel** — Discards changes and returns to view mode

### Via the Filesystem

Edit `data/personas/{slug}/skill.md` directly. The template provides three sections:

```markdown
# Con — developer

## Core Identity
A senior full-stack developer who prefers pragmatic solutions over abstractions.

## Skills & Preferences
- Python/Flask backend development
- PostgreSQL and SQLAlchemy
- Prefers targeted tests over full suite runs
- Favours simple, readable code

## Communication Style
Direct and concise. Shows code rather than describing it.
```

The skill file content is injected into the agent's session at startup. Be specific about preferences and working style — the agent will follow these instructions.

## Filesystem Layout

```
data/personas/
  developer-con-1/
    skill.md           # Core identity and competencies
    experience.md      # Append-only learning log
    handoffs/          # Handoff documents (created during handoffs)
  tester-robbo-2/
    skill.md
    experience.md
```

## Experience Log

The `experience.md` file is an append-only log of lessons learned. New entries are added at the top. Over time, the persona accumulates knowledge that persists across agent sessions.

On the persona detail page, the experience log is displayed as rendered markdown with its last-modified timestamp. The log is read-only in the UI — it is designed for manual or tool-assisted curation from the filesystem. Future versions may append entries automatically after each session.

## Starting an Agent with a Persona

### Via Dashboard

The dashboard's **New Agent** button uses a two-step flow:

1. **Select a project** — Choose which project the agent will work on
2. **Select a persona** (optional) — Choose from active personas, grouped by role. Each option shows the persona's name and description. Select **No persona** to create an anonymous agent.

If no active personas exist, the persona selection step is skipped automatically.

### Via API

```bash
curl -X POST https://your-server:5055/api/agents \
  -H "Content-Type: application/json" \
  -d '{"project_id": 1, "persona_slug": "developer-con-1"}'
```

Omit `persona_slug` to create an agent without a persona.

### Via CLI

```bash
claude-headspace start --persona con
```

The `--persona` flag accepts either the full slug (`developer-con-1`) or a short name. Short names are matched case-insensitively against persona names:

- **Single match** — The persona is used automatically (e.g., `--persona con` matches "Con")
- **Multiple matches** — An interactive prompt lists the options for you to choose from
- **No matches** — Available personas are displayed and the command exits with an error

## Listing Personas (CLI)

Use `flask persona list` to see all registered personas:

```bash
flask persona list
```

This displays a formatted table with Name, Role, Slug, Status, and agent count columns.

### Filtering

```bash
flask persona list --active          # Show only active personas
flask persona list --role developer  # Filter by role (case-insensitive)
```

## How Skill Injection Works

When an agent with a persona starts:

1. The session-start hook fires and registers the agent
2. The system reads the persona's `skill.md` from the filesystem
3. The skill content is sent to the agent's tmux pane via `tmux send-keys`
4. The agent receives its identity and competencies as part of its initial context

This happens automatically — no manual intervention needed. The agent begins its session knowing who it is and how it should work.

## Dashboard Identity

Agents with personas display differently on the dashboard:

- **Card header** — Shows "Con — developer" instead of "4b6f8a" (truncated UUID)
- **Agent info panel** — Shows persona name, role, and slug in the identity section
- **Sorting** — Persona agents are visually distinct, making it easy to identify team members

Anonymous agents (without personas) continue to display their session UUID as before. Personas are fully optional — existing workflows are unchanged.

## Validating a Persona

To check if a persona exists and is active:

```bash
curl https://your-server:5055/api/personas/{slug}/validate
```

Returns `{"valid": true, ...}` if active, or `{"valid": false, ...}` with guidance.

## Related Topics

- [Handoff](handoff) — Context transfer between persona agents
- [Dashboard](dashboard) — How agent cards display persona identity
- [Input Bridge](input-bridge) — Responding to persona agents from the dashboard
- [Getting Started](getting-started) — Initial setup and first session
