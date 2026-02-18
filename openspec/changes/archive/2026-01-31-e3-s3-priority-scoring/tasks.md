# Commands: e3-s3-priority-scoring

## Phase 1: Schema & Model

- [x] 1. Add priority fields to Agent model (`priority_score`, `priority_reason`, `priority_updated_at`)
- [x] 2. Create Alembic migration `e7f8a9b0c1d2_add_priority_fields_to_agents` chaining from `d6e7f8a9b0c1`
- [x] 3. Write integration test for priority field persistence on Agent model

## Phase 2: Priority Scoring Service

- [x] 4. Create `src/claude_headspace/services/priority_scoring.py` with PriorityScoringService class
- [x] 5. Implement `_get_scoring_context()` — fallback chain: objective → waypoint → default
- [x] 6. Implement `_build_scoring_prompt()` — batch prompt with context and agent metadata
- [x] 7. Implement `_parse_scoring_response()` — JSON parsing with error handling for malformed responses
- [x] 8. Implement `score_all_agents()` — main entry: gather agents, build prompt, call inference, parse, persist
- [x] 9. Implement `score_all_agents_async()` — background thread wrapper with Flask app context
- [x] 10. Implement `trigger_scoring()` — rate-limited trigger with 5-second debounce (thread-safe)
- [x] 11. Implement `trigger_scoring_immediate()` — bypass debounce for objective changes
- [x] 12. Write unit tests for PriorityScoringService (prompt building, response parsing, fallback chain, debounce)

## Phase 3: API Endpoints

- [x] 13. Create `src/claude_headspace/routes/priority.py` with priority_bp blueprint
- [x] 14. Implement POST `/api/priority/score` — trigger batch scoring and return results
- [x] 15. Implement GET `/api/priority/rankings` — return current priority rankings
- [x] 16. Write unit tests for priority API endpoints

## Phase 4: Dashboard Integration

- [x] 17. Update `dashboard.py` — replace hardcoded `"priority": 50` with `agent.priority_score or 50`
- [x] 18. Update `sort_agents_by_priority()` to use `priority_score` as primary sort key
- [x] 19. Update `get_recommended_next()` to use highest `priority_score`
- [x] 20. Update `_agent_card.html` to display `priority_reason`

## Phase 5: Trigger Integration

- [x] 21. Add scoring trigger in HookLifecycleBridge on state transitions
- [x] 22. Add SSE broadcast for `priority_update` events in PriorityScoringService
- [x] 23. Write unit tests for hook integration and SSE broadcast

## Phase 6: App Registration & Wiring

- [x] 24. Register PriorityScoringService in app.py (app.extensions)
- [x] 25. Register priority_bp blueprint in app.py
- [x] 26. Run full test suite and verify no regressions
