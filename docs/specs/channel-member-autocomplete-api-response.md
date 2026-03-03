# API Response: Channel Member Autocomplete

**Author:** Con (backend)
**For:** Al (frontend)
**Date:** 2026-03-04
**Status:** Live on development

Everything from your spec is implemented. Here's what you need to wire up.

## 1. GET /api/channels/available-members

Returns active agents grouped by project. Auth: same as all channel endpoints (Bearer token or operator session).

### Request

```
GET /api/channels/available-members
```

No query params needed.

### Response (200)

```json
{
  "projects": [
    {
      "project_id": 9,
      "project_name": "Claude Headspace",
      "agents": [
        {
          "agent_id": 1201,
          "persona_name": "Al",
          "persona_slug": "frontend-al-6",
          "role": "frontend"
        },
        {
          "agent_id": 1203,
          "persona_name": "Con",
          "persona_slug": "backend-con-5",
          "role": "backend"
        }
      ]
    },
    {
      "project_id": 48,
      "project_name": "otageLabs.com",
      "agents": [
        {
          "agent_id": 1200,
          "persona_name": "Al",
          "persona_slug": "frontend-al-6",
          "role": "frontend"
        }
      ]
    }
  ]
}
```

The same persona (e.g. Al) can appear under multiple projects if they have active agents on each — each entry is a distinct `agent_id`.

Empty state: `{"projects": []}` when no active agents exist.

### "Active agent" criteria

- `ended_at IS NULL`
- `persona_id IS NOT NULL`
- persona `status == 'active'`

Results ordered by project name, then persona name within each project.

## 2. POST /api/channels — create with agent IDs

New field: `member_agents` (array of ints).

```json
{
  "name": "Design Review",
  "channel_type": "workshop",
  "member_agents": [1201, 1203]
}
```

- `member_agents` takes precedence over `members` (persona slugs) if both are provided
- Each agent ID is validated: must be active, have a persona, persona must be active
- Invalid agents are skipped with a warning (channel still created)

### Validation errors

| Condition | Status | Code |
|---|---|---|
| `member_agents` is not a list | 400 | `invalid_field` |
| List contains non-integers | 400 | `invalid_field` |

## 3. POST /api/channels/\<slug\>/members — add by agent ID

New field: `agent_id` (int). Takes precedence over `persona_slug`.

```json
{
  "agent_id": 1201
}
```

### Responses

| Condition | Status | Code |
|---|---|---|
| Success | 201 | — (membership object) |
| `agent_id` is not an int | 400 | `invalid_field` |
| Agent not found / ended | 404 | `agent_not_found` |
| Persona already in channel | 409 | `already_a_member` |
| Agent active in another channel | 409 | `agent_already_in_channel` |
| Neither `agent_id` nor `persona_slug` | 400 | `missing_fields` |

The `agent_already_in_channel` error message includes the conflicting channel slug, so you can show something like "Al is already in #design-review".

## 4. Backward compatibility

All existing `persona_slug` / `members` flows still work unchanged. The new `agent_id` / `member_agents` paths are additive.

## 5. Quick test

```bash
# Fetch available members
curl -sk https://smac.griffin-blenny.ts.net:5055/api/channels/available-members | jq

# Add member by agent ID
curl -sk -X POST https://smac.griffin-blenny.ts.net:5055/api/channels/SLUG/members \
  -H "Content-Type: application/json" \
  -d '{"agent_id": 1201}'
```
