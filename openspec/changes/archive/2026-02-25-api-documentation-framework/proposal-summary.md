# Proposal Summary: api-documentation-framework

## Architecture Decisions

1. **Static file serving over dynamic generation.** The OpenAPI spec is a hand-authored YAML file served from `static/api/`. This was chosen over auto-generation (Flask-RESTX, decorators) because: the PRD explicitly marks auto-generation as out of scope; hand-authored specs allow LLM-optimised descriptions that auto-generated docs cannot match; and static files are simpler to version-control, review, and maintain.

2. **OpenAPI 3.1 (not 3.0).** OpenAPI 3.1 aligns with JSON Schema 2020-12, providing better type expressiveness (e.g., `type: ["integer", "null"]` for nullable fields). The PRD specifies 3.1 explicitly.

3. **Relative paths in the spec.** The spec does not hardcode a server URL. A `servers` description instructs consumers to supply the base URL of their Claude Headspace instance. This makes the spec portable across environments (dev, staging, production, Tailscale network).

4. **Directory convention `static/api/<api-name>.yaml`.** Future external API specs (if any) follow the same pattern. This is documented in the help topic so the convention is discoverable.

5. **Help system integration via existing TOPICS registry.** The help topic is added by appending to the TOPICS list in `help.py` — the same pattern used by all 17 existing help topics. No new routes or infrastructure needed.

## Implementation Approach

The implementation is purely additive — no existing code is modified beyond adding a topic entry to the help route's TOPICS list. The work consists of:

1. Create the OpenAPI 3.1 spec YAML file with all endpoint, schema, auth, error, and CORS documentation
2. Create the help topic markdown file with human-readable API documentation and cross-links
3. Register the help topic in the TOPICS list
4. Add a navigation link to the help index
5. Write tests to validate the spec and verify serving

The spec content is derived directly from the existing route code (`remote_agents.py`) and service code (`remote_agent_service.py`). All request/response shapes, error codes, and authentication behaviour are already implemented — this change documents them.

## Files to Modify

### New Files
- `static/api/remote-agents.yaml` — OpenAPI 3.1 specification (YAML)
- `docs/help/external-api.md` — Help topic for the external API

### Modified Files
- `src/claude_headspace/routes/help.py` — Add `external-api` topic to TOPICS list (1 line)
- `docs/help/index.md` — Add navigation link to external API topic (1 line)

### New Test Files
- `tests/routes/test_help.py` — Verify new topic is served (may extend existing test file)
- `tests/services/test_openapi_spec.py` — Validate spec against OpenAPI 3.1 standard; verify all paths match actual routes; verify schema fields match actual response shapes

## Acceptance Criteria

From the PRD's Success Criteria:

1. OpenAPI 3.1 spec file served at `/static/api/remote-agents.yaml` and accessible to consumers on the network
2. Spec documents all remote agent API endpoints: create, alive check, shutdown, and embed
3. Spec includes complete request/response schemas with realistic example payloads
4. Spec documents session token authentication mechanism (obtain, send, scope, error)
5. Spec documents standardised error envelope with all error codes and retryable semantics
6. Spec documents CORS behaviour
7. Help topic exists that describes the API and provides the spec URL
8. Cross-links: help references spec, spec references help
9. An LLM can parse the spec and generate valid API calls without supplementary documentation
10. Spec validates against OpenAPI 3.1 standard
11. Directory convention documented for future API specs

## Constraints and Gotchas

1. **No Swagger UI.** Explicitly out of scope. Do not add any browser-based API explorer.
2. **No npm dependencies.** Do not add openapi-related npm packages. The spec is a static YAML file.
3. **No Python dependencies for spec validation in production.** Test-time validation (e.g., `openapi-spec-validator` pip package) is acceptable for the test suite only.
4. **No CORS changes.** The spec documents existing CORS behaviour — it does not modify it.
5. **No auth changes.** Session token mechanism is documented as-is.
6. **Tailwind CSS not involved.** No UI components in this change; no CSS rebuild needed.
7. **Static file path must be stable.** Once published, `/static/api/remote-agents.yaml` becomes a contract URL. Do not move or rename it without versioning considerations.
8. **LLM-first descriptions.** Every field description must be self-contained, explicit, and avoid Claude Headspace jargon. An LLM with zero project context must understand each field from its description alone.

## Git Change History

### Related Recent Commits
- `e2f9cf7e` (2026-02-26) — "feat: remote agent API contract refinements, exception reporter, and API docs PRD" — the commit that introduced this PRD and refined the remote agent API contract
- `d8cd3cf2` (2026-02-25) — "feat(remote-agent-integration): implementation (#83)" — the original remote agent integration implementation that created the API being documented

### OpenSpec History
- `remote-agent-integration` (archived 2026-02-25) — created the remote agent API endpoints, session token auth, embed view, CORS, and error envelope that this spec documents

### Patterns Detected
- The codebase has integration tests (`tests/integration/`) but this change primarily needs route-level and validation tests
- The help system uses markdown files in `docs/help/` with a TOPICS registry in `routes/help.py`
- Static files are served from `static/` directory by Flask's built-in handler

## Q&A History

No clarifications were needed. The PRD was unambiguous.

## Dependencies

### Python Packages (test-only)
- `openapi-spec-validator` or `prance` — for programmatic OpenAPI 3.1 validation in tests. These are test-time dependencies only; not needed in production. Check if already present in `pyproject.toml` dev dependencies.

### No Other Dependencies
- No npm packages
- No database migrations
- No external APIs
- No new Flask extensions

## Testing Strategy

1. **Spec validation test** — parse `static/api/remote-agents.yaml` and validate it against the OpenAPI 3.1 JSON Schema using `openapi-spec-validator` or equivalent
2. **Static file serving test** — HTTP GET `/static/api/remote-agents.yaml` returns 200 with YAML content
3. **Help topic serving test** — HTTP GET `/api/help/topics/external-api` returns 200 with topic content
4. **Help topic listing test** — HTTP GET `/api/help/topics` includes `external-api` in the list
5. **Schema accuracy tests** — programmatically verify that:
   - All endpoint paths in the spec match registered Flask routes
   - All request body fields match the actual route parameter extraction
   - All response fields match the actual JSON response shapes
6. **Cross-link verification** — spec's `info.description` mentions `/help/external-api`; help topic mentions `/static/api/remote-agents.yaml`

## OpenSpec References

- **Proposal:** `openspec/changes/api-documentation-framework/proposal.md`
- **Tasks:** `openspec/changes/api-documentation-framework/tasks.md`
- **Spec:** `openspec/changes/api-documentation-framework/specs/api-docs/spec.md`
- **PRD:** `docs/prds/integration/api-documentation-framework-prd.md`
