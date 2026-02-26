# External API

Claude Headspace provides an external API for creating and managing Claude Code agents from external applications. This API is designed for programmatic access by LLM-powered agents and automated systems.

## OpenAPI Specification

The complete machine-readable API specification is available as an OpenAPI 3.1 YAML file:

**URL:** `/api/remote_agents/openapi.yaml`

Fetch this file from your Claude Headspace instance to get full endpoint documentation, request/response schemas, authentication details, and error codes. The spec is optimised for LLM consumption with detailed field descriptions and realistic examples.

## Quick Start for LLM Consumers

1. **Fetch the spec:** `GET /api/remote_agents/openapi.yaml` from your Claude Headspace instance
2. **Parse the YAML** to discover endpoints, schemas, and authentication requirements
3. **Create an agent:** `POST /api/remote_agents/create` with a JSON body containing `project_slug`, `persona_slug`, and `initial_prompt`
4. **Save the session token** from the response — you need it for all subsequent requests
5. **Monitor the agent:** `GET /api/remote_agents/{agent_id}/alive` with the token in the Authorization header
6. **Shut down the agent:** `POST /api/remote_agents/{agent_id}/shutdown` when work is complete

## Authentication

The API uses session tokens for authentication. Tokens are generated when you create an agent and returned in the create response. Each token is scoped to a single agent.

**How to send the token:**
- **Header (preferred):** `Authorization: Bearer <token>`
- **Query parameter (for embed iframes):** `?token=<token>`

**Token lifecycle:**
- Generated on agent creation
- Scoped to one specific agent
- Revoked automatically on agent shutdown
- Does not survive server restarts

## Endpoints Overview

| Endpoint | Method | Auth Required | Description |
|----------|--------|---------------|-------------|
| `/api/remote_agents/create` | POST | No | Create a new remote agent |
| `/api/remote_agents/{id}/alive` | GET | Yes | Check if an agent is alive |
| `/api/remote_agents/{id}/shutdown` | POST | Yes | Initiate graceful shutdown |
| `/embed/{id}` | GET | Yes (query param) | Embeddable chat interface |

## Error Handling

All errors follow a standardised envelope format:

```json
{
  "error": {
    "code": "error_code_here",
    "message": "Human-readable description",
    "status": 400,
    "retryable": false,
    "retry_after_seconds": null
  }
}
```

**Error codes:** `missing_fields`, `invalid_feature_flags`, `invalid_session_token`, `project_not_found`, `persona_not_found`, `agent_not_found`, `agent_creation_timeout`, `server_error`, `service_unavailable`

When `retryable` is `true`, wait for `retry_after_seconds` before retrying.

## CORS

Cross-origin requests are supported. Allowed origins are configured on the server (in `config.yaml` under `remote_agents.allowed_origins`). Preflight OPTIONS requests are handled automatically for all API endpoints.

## Directory Convention for API Specs

API specification files are stored as static YAML files following this convention:

```
static/api/<api-name>.yaml
```

Each external API gets its own spec file named after the API. For example, the remote agents API spec is at `static/api/remote-agents.yaml`. Future external APIs should follow the same pattern.
