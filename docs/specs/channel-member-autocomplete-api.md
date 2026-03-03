# API Spec: Channel Member Autocomplete

**Author:** Al (frontend)
**For:** Con (backend)
**Date:** 2026-03-04

## Context

The channel creation form currently requires typing comma-separated persona slugs to add members. We're replacing this with an autocomplete picker that lets you search by persona name and select a specific **agent** (persona + project). The agent is the channel member.

## 1. New Endpoint: GET /api/channels/available-members

Returns all active agents grouped by project, for the autocomplete picker.

### Definition of "active agent"

- `Agent.ended_at IS NULL` (session has not ended)
- `Agent.persona_id IS NOT NULL` (agent has an assigned persona)
- The linked `Persona.status == "active"`

### Response Shape

```json
{
  "projects": [
    {
      "project_id": 1,
      "project_name": "claude-headspace",
      "agents": [
        {
          "agent_id": 7,
          "persona_name": "Al",
          "persona_slug": "frontend-al-3",
          "role": "frontend"
        },
        {
          "agent_id": 12,
          "persona_name": "Con",
          "persona_slug": "developer-con-1",
          "role": "developer"
        }
      ]
    },
    {
      "project_id": 3,
      "project_name": "other-project",
      "agents": [
        {
          "agent_id": 15,
          "persona_name": "Al",
          "persona_slug": "frontend-al-3",
          "role": "frontend"
        }
      ]
    }
  ]
}
```

Note: The same persona (e.g. Al) can appear under multiple projects if they have active agents on each.

### Query Logic

```
SELECT agent.id, persona.name, persona.slug, role.name, project.id, project.name
FROM agent
JOIN persona ON agent.persona_id = persona.id
JOIN role ON persona.role_id = role.id
JOIN project ON agent.project_id = project.id
WHERE agent.ended_at IS NULL
  AND agent.persona_id IS NOT NULL
  AND persona.status = 'active'
ORDER BY project.name, persona.name
```

Group results by project in Python before returning.

### Auth

Same dual auth as other channel endpoints (Bearer token or operator session). No special permissions needed — this is a read-only lookup.

## 2. Modified: Accept agent_id for Member Addition

### POST /api/channels (create channel)

Current `members` field accepts persona slugs: `["frontend-al-3", "developer-con-1"]`

Add support for `member_agents` field accepting agent IDs: `[7, 12]`

- If `member_agents` is provided, use it (preferred path from autocomplete)
- If `members` is provided (persona slugs), keep existing behaviour for backward compat
- If both provided, `member_agents` wins

For each agent_id in `member_agents`:
1. Look up the Agent, confirm `ended_at IS NULL`
2. Get the `persona_id` from the agent
3. Create `ChannelMembership` with both `persona_id` and `agent_id`
4. If persona already in channel (unique constraint), skip or return error

### POST /api/channels/\<slug\>/members (add member)

Currently accepts `persona_slug`. Add support for `agent_id`.

- If `agent_id` is provided, resolve persona from agent and create membership with both IDs
- If `persona_slug` is provided, keep existing behaviour
- If both, `agent_id` wins

### Validation

- Agent must exist and be active (`ended_at IS NULL`)
- Agent must have a persona (`persona_id IS NOT NULL`)
- Respect existing unique constraint `uq_channel_persona` (channel_id, persona_id)
- Respect existing partial unique index `uq_active_agent_one_channel` (agent can only be active in one channel)

## 3. Existing Constraints to Be Aware Of

| Constraint | Effect |
|---|---|
| `uq_channel_persona` | A persona can only appear once per channel |
| `uq_active_agent_one_channel` | An active agent can only be in one channel at a time |

The `uq_active_agent_one_channel` constraint means: if agent 7 is already an active member of another channel, adding them to a new channel should return an error. The frontend will need to handle this gracefully (I'll show a message like "Al is already in channel X").

## 4. What I Need From This

The frontend autocomplete will:
1. Fetch `GET /api/channels/available-members` when the input is focused
2. Filter client-side as the user types (matching against persona_name)
3. Display results grouped by project, showing: `persona_name — role` under each project heading
4. On selection, collect the `agent_id` and display `persona_name (project)` as a tag
5. Submit `member_agents: [agent_id, ...]` in the create channel payload

I'll build the frontend once this endpoint is live.
