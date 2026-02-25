## Why

External consumers (LLM agents, AI-powered systems) currently have zero machine-readable documentation for the remote agent API. They must be manually briefed on endpoints, authentication, payloads, and error handling. As more external APIs are built, this does not scale. An OpenAPI 3.1 spec provides a stable, discoverable, self-contained resource that LLMs can parse and act on without human guidance.

## What Changes

- **OpenAPI 3.1 spec file** (`static/api/remote-agents.yaml`) — complete machine-readable documentation of all remote agent API endpoints (create, alive, shutdown, embed) with reusable schema components, session token auth documentation, error envelope definitions, CORS behaviour, and realistic examples optimised for LLM comprehension
- **Help topic** (`docs/help/external-api.md`) — human-readable documentation explaining the external API, how to use the spec, and the directory convention for future API specs; cross-linked to the spec file
- **Help system registration** — new topic added to the TOPICS list in the help route so it appears in the help sidebar and search index
- **Spec-to-help cross-link** — the spec's `info.description` references the help topic URL for additional human-readable context
- **Directory convention** — established pattern (`static/api/<api-name>.yaml`) documented for future external API specs

## Impact

- Affected specs: none (this is purely additive documentation)
- Affected code:
  - **New files:** `static/api/remote-agents.yaml`, `docs/help/external-api.md`
  - **Modified files:** `src/claude_headspace/routes/help.py` (add topic to TOPICS list)
  - **Test files:** `tests/routes/test_help.py` (verify new topic is served), `tests/services/test_openapi_spec.py` (validate spec against OpenAPI 3.1 standard)
- No database migrations required
- No changes to existing API endpoints — this documents existing behaviour only
- No npm or Python package dependencies added
- Static file serving uses Flask's built-in static file handler (already configured)
