# Proposal Summary: api-call-logging

## Architecture Decisions

1. **Middleware-based capture via Flask `before_request`/`after_request` hooks** rather than per-route decorators. This approach is centralized, requires no changes to existing route handlers, and automatically captures all future external-facing routes that match the prefix list.

2. **New `ApiCallLog` database model** (not reusing `Event` or `InferenceCall`). API call logs have fundamentally different fields (HTTP method, status code, request/response bodies, source IP, auth status) that don't fit the existing event or inference schemas. A dedicated model provides clean indexes and avoids schema pollution.

3. **Same-process, synchronous DB write** with fault-tolerant try/except. The logging write happens in `after_request` within the same request cycle. While an async queue would eliminate any latency impact, the expected overhead (<50ms for a single INSERT) does not justify the complexity. If logging fails, the API response is unaffected.

4. **SSE broadcast pattern** matching existing `inference_call` event pattern. A new `api_call_logged` SSE event is broadcast after successful persistence, enabling real-time table updates on the API log tab.

5. **UI follows the Inference tab pattern** exactly: same filter bar layout, same pagination structure, same expand/collapse interaction, same state management (loading/empty/no-results/error). This ensures consistency and leverages tested patterns.

## Implementation Approach

The implementation follows the same layered approach used for the Inference log tab:

1. **Model layer**: Create `ApiCallLog` model with SQLAlchemy Mapped columns, appropriate indexes, and nullable foreign keys to Project and Agent.
2. **Migration**: Generate and apply Alembic migration.
3. **Service layer**: Create `ApiCallLogger` service that registers `before_request` and `after_request` hooks on the Flask app, filtering by route prefix. The `before_request` records the start time; `after_request` builds and persists the log record.
4. **Route layer**: Add three new endpoints and one page route to the existing `logging_bp` blueprint (no new blueprint needed).
5. **Template layer**: Create `logging_api.html` extending `base.html` with the standard logging layout.
6. **JavaScript layer**: Create `logging-api.js` following the `InferenceLogPage` controller pattern.
7. **Tab navigation**: Update `_logging_tabs.html` to add the third tab.

## Files to Modify (organized by type)

### New Files
| File | Purpose |
|------|---------|
| `src/claude_headspace/models/api_call_log.py` | ApiCallLog SQLAlchemy model |
| `src/claude_headspace/services/api_call_logger.py` | Capture middleware service |
| `templates/logging_api.html` | API log tab Jinja2 template |
| `static/js/logging-api.js` | API log tab JavaScript controller |
| `migrations/versions/xxxx_add_api_call_logs.py` | Alembic migration |
| `tests/services/test_api_call_logger.py` | Middleware unit tests |
| `tests/routes/test_logging_api.py` | Route/API endpoint tests |

### Modified Files
| File | Change |
|------|--------|
| `src/claude_headspace/routes/logging.py` | Add 3 new API endpoints + 1 page route |
| `src/claude_headspace/app.py` | Import model, register ApiCallLogger service |
| `templates/partials/_logging_tabs.html` | Add API tab (third tab) |

## Acceptance Criteria

1. Every external API call to `/api/remote_agents/*`, `/api/voice_bridge/*`, `/embed/*` is captured with full request/response payloads
2. The API log tab displays captured calls in a paginated, filterable table at `/logging/api`
3. Developers can filter by endpoint, HTTP method, status code category, and authentication status
4. Developers can search across request and response payload content
5. Expanding a row shows complete request payload, response payload, and HTTP metadata
6. New API calls appear in real-time via SSE without page refresh
7. The clear-all function removes all API log records with destructive confirmation
8. Logging adds no more than 50ms latency and never breaks API responses
9. Authorization header values are never stored — only auth_status is recorded
10. All tests pass (unit + route)

## Constraints and Gotchas

1. **Flask `after_request` cannot access the response body after streaming**. Since the target endpoints return JSON (not streaming SSE), this is not an issue. If future endpoints use streaming responses, they would need special handling.

2. **Request body reading**: `request.get_data()` must be called carefully. For routes that use `request.json` or `request.form`, the data is already consumed. The middleware should use `request.get_data(as_text=True)` which returns the cached body.

3. **Payload size**: Bodies up to 1MB are stored without truncation. The `Text` column type in PostgreSQL has no practical length limit, but very large payloads could impact query performance. The 1MB truncation threshold prevents pathological cases.

4. **Auth status detection**: Different API subsystems use different auth mechanisms:
   - Remote agents: session token in query params or headers
   - Voice bridge: Bearer token or localhost bypass
   - Embed: session token in query params
   The middleware needs to detect the auth mechanism used and determine the status without re-implementing auth logic. Reading from `request` attributes set by auth decorators or checking response status is the preferred approach.

5. **SSE event size**: The `api_call_logged` SSE event should NOT include full request/response bodies (which could be large). It should include only the metadata fields visible in the table (timestamp, method, endpoint, status, latency, source IP, auth status) plus the record ID for potential detail fetching.

6. **CSS source-of-truth**: All styling uses Tailwind utility classes. No custom CSS additions needed for `input.css`. The existing `.logging-subtab` styles in `input.css` already cover the tab navigation.

7. **Test database**: All tests must use `claude_headspace_test` via the existing `_force_test_database` fixture. The migration must be tested with `db.create_all()` in the test setup.

## Git Change History

### Related OpenSpec History
- `e1-s10-logging-tab` (archived 2026-01-29): Established the logging subsystem with Events tab, Inference tab, `_logging_tabs.html` partial, and the `logging_bp` blueprint. This change extends that foundation.

### Related Files Recently Modified
- `src/claude_headspace/routes/logging.py` — last modified in adversarial code review (2026-02-05, sha `a63677ee`)
- `templates/logging.html`, `templates/logging_inference.html`, `templates/partials/_logging_tabs.html` — stable since logging subsystem creation
- `static/js/logging.js`, `static/js/logging-inference.js` — stable since logging subsystem creation

### Detected Patterns
- Routes, tests, templates, and static JS files follow consistent naming and structure
- Existing logging tab pair (Events + Inference) provides exact patterns to replicate
- No active development conflicts in the logging subsystem area

## Q&A History

No clarifications were needed. The PRD is well-specified with clear functional requirements, scope boundaries, and UI description.

## Dependencies

- **Python packages**: None new. Uses existing Flask, SQLAlchemy, Alembic stack.
- **JavaScript libraries**: None new. Uses vanilla JS following existing patterns.
- **Database**: Requires new `api_call_logs` table via Alembic migration.
- **APIs**: No external API dependencies.
- **Other systems**: No new system dependencies.

## Testing Strategy

### Unit Tests (`tests/services/test_api_call_logger.py`)
- Middleware route prefix matching (capture vs. ignore)
- Request/response data extraction
- Header sanitization (Authorization stripping)
- Fault tolerance (DB write failure)
- Payload truncation (>1MB)
- Entity resolution (project_id, agent_id)
- SSE event broadcast

### Route Tests (`tests/routes/test_logging_api.py`)
- Page route rendering
- API endpoint pagination
- Filter combinations (endpoint, method, status category, auth status)
- Text search across payloads
- Destructive clear-all with/without confirmation header
- Empty state handling
- Filter options endpoint

### Manual Verification
- Make real API calls to remote agents / voice bridge endpoints
- Confirm calls appear in the API log tab in real-time
- Verify expanded rows show formatted JSON
- Verify filters narrow results correctly

## OpenSpec References

- **Proposal**: `openspec/changes/api-call-logging/proposal.md`
- **Tasks**: `openspec/changes/api-call-logging/tasks.md`
- **Spec**: `openspec/changes/api-call-logging/specs/logging/spec.md`
- **Related archived change**: `openspec/changes/archive/2026-01-29-e1-s10-logging-tab/`
