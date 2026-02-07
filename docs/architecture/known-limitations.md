# Known Limitations

## In-Memory Summarisation Queue

**Component:** `TaskLifecycleManager.pending_summarisation_requests`

Summarisation requests (turn and task summaries) are queued in-memory and processed asynchronously after hook events complete. If the server restarts while requests are queued, those pending summarisations are lost.

**Impact:** Some turns or tasks may not receive AI-generated summaries after a server restart. The underlying data (turns, tasks, events) is fully persisted in PostgreSQL -- only the summary text is missing.

**Why this is acceptable:**
- Claude Headspace is a single-server deployment; restarts are infrequent
- Summaries are a display enhancement, not a data integrity concern
- Missing summaries can be regenerated manually via the `/api/summarise/turn/<id>` and `/api/summarise/task/<id>` endpoints
- The queue is typically drained within seconds of each hook event

**Potential future improvement:** Persist pending summarisation requests to the database and process them on startup. This would add complexity for a marginal benefit in the current single-server architecture.
