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

## Registering a Persona

Before using a persona, you need to register it. Registration creates a database record and seeds the filesystem assets.

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

## Editing the Skill File

After registration, edit `data/personas/{slug}/skill.md` to define who the persona is. The template provides three sections:

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

## Starting an Agent with a Persona

### Via Dashboard

When creating a new agent from the dashboard, select a persona from the dropdown. Only active personas appear.

### Via API

```bash
curl -X POST https://your-server:5055/api/agents \
  -H "Content-Type: application/json" \
  -d '{"project_id": 1, "persona_slug": "developer-con-1"}'
```

### Via CLI

```bash
claude-headspace start --persona con
```

The `--persona` flag accepts either the full slug or a short name that uniquely matches.

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

## Experience Log

The `experience.md` file is an append-only log of lessons learned. New entries are added at the top. Over time, the persona accumulates knowledge that persists across agent sessions.

The experience log is not currently auto-updated — it is designed for manual or tool-assisted curation. Future versions may append entries automatically after each session.

## Related Topics

- [Handoff](handoff) — Context transfer between persona agents
- [Dashboard](dashboard) — How agent cards display persona identity
- [Input Bridge](input-bridge) — Responding to persona agents from the dashboard
- [Getting Started](getting-started) — Initial setup and first session
