# Proposal: api-call-logging

## Why

Claude Headspace exposes external APIs for remote agents, voice bridge, and embed chat, but there is no persistent, inspectable record of HTTP traffic when these integrations fail. Developers cannot see what arrived on the wire or what was sent back, making cross-system debugging blind guesswork.

## What Changes

- **New database model** (`ApiCallLog`) to persist external API request/response records with full payloads, HTTP metadata, timing, source IP, and authentication status
- **New Alembic migration** to create the `api_call_logs` table with appropriate indexes
- **New middleware/decorator** (`api_call_logger`) that intercepts requests to designated external route prefixes (`/api/remote_agents/*`, `/api/voice_bridge/*`, `/embed/*`) and captures request + response data non-blockingly
- **New "API" tab** in the logging subsystem (`/logging/api`) positioned after the Inference tab, with filterable paginated table, click-to-expand rows, text search, and real-time SSE updates
- **New API endpoints**: `GET /api/logging/api-calls` (paginated list), `GET /api/logging/api-calls/filters` (distinct filter values), `DELETE /api/logging/api-calls` (clear all with destructive confirmation)
- **New JavaScript module** (`logging-api.js`) following the existing `logging-inference.js` pattern
- **New Jinja2 template** (`logging_api.html`) following the existing `logging_inference.html` pattern
- **Updated tab navigation** (`_logging_tabs.html`) to include the API tab with a distinct icon
- **SSE integration**: new `api_call_logged` event type broadcast when a call is persisted

## Impact

- Affected specs: logging
- Affected code:
  - New: `src/claude_headspace/models/api_call_log.py`, `src/claude_headspace/services/api_call_logger.py`, `templates/logging_api.html`, `static/js/logging-api.js`, `tests/routes/test_logging_api.py`, `tests/services/test_api_call_logger.py`
  - Modified: `src/claude_headspace/routes/logging.py`, `src/claude_headspace/app.py`, `templates/partials/_logging_tabs.html`
  - Migration: new Alembic migration for `api_call_logs` table
- OpenSpec history: extends `e1-s10-logging-tab` (archived 2026-01-29) which established the logging subsystem with Events and Inference tabs
- No breaking changes to existing functionality
