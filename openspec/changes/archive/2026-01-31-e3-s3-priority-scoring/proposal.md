# Proposal: e3-s3-priority-scoring

## Summary

Add an LLM-driven cross-project priority scoring service that evaluates all active agents (0-100) in a single batch inference call, replacing the hardcoded placeholder priority of 50 on the dashboard.

## Motivation

The dashboard currently hardcodes `"priority": 50` for every agent and uses state-based sorting (AWAITING_INPUT > PROCESSING > IDLE). This provides no differentiation when multiple agents share the same state. With the inference infrastructure from E3-S1 and task summaries from E3-S2, we can now score agents based on objective alignment, state urgency, task duration, and project context — giving the user actionable guidance on where to focus attention.

## Impact

### Files Modified

**Models:**
- `src/claude_headspace/models/agent.py` — Add priority_score, priority_reason, priority_updated_at fields

**Migrations:**
- `migrations/versions/e7f8a9b0c1d2_add_priority_fields_to_agents.py` — New migration adding priority columns

**Services (New):**
- `src/claude_headspace/services/priority_scoring.py` — New PriorityScoringService with batch scoring, prompt building, response parsing, rate-limited triggers, fallback chain

**Routes (New):**
- `src/claude_headspace/routes/priority.py` — New blueprint: POST /api/priority/score, GET /api/priority/rankings

**Routes (Modified):**
- `src/claude_headspace/routes/dashboard.py` — Replace hardcoded priority=50 with real scores; update sort_agents_by_priority() and get_recommended_next() to use priority_score

**Services (Modified):**
- `src/claude_headspace/services/hook_lifecycle_bridge.py` — Add scoring trigger on state transitions
- `src/claude_headspace/app.py` — Register PriorityScoringService and priority blueprint

**Templates (Modified):**
- `templates/partials/_agent_card.html` — Display priority_reason; adjust priority badge display

### Integration Points

- **E3-S1 InferenceService:** Uses `infer(level="objective", purpose="priority_scoring", ...)` for batch scoring
- **E3-S2 SummarisationService:** Uses task summaries as scoring context (graceful degradation if unavailable)
- **Objective model:** Reads `current_text` and `constraints` for primary scoring context
- **Waypoint editor:** Uses `load_waypoint()` to read project waypoint Next Up/Upcoming sections as fallback
- **HookLifecycleBridge:** Triggers rate-limited re-scoring on state changes
- **SSE Broadcaster:** Broadcasts score updates via `priority_update` event

### Recent Changes (from E3-S2)

- Agent model has no priority fields yet — clean addition
- SummarisationService provides task summaries accessible via `turn.summary`
- Latest migration is `d6e7f8a9b0c1` — new migration chains from this

## Approach

### Architecture

1. **PriorityScoringService** — Core service class:
   - `score_all_agents()` — Main entry point; gathers context, builds prompt, calls inference, parses response, persists scores
   - `_build_scoring_prompt()` — Constructs the batch prompt with objective/waypoint context and agent metadata
   - `_parse_scoring_response()` — Parses structured JSON from LLM response with error handling
   - `_get_scoring_context()` — Fallback chain: objective → waypoint → default
   - `score_all_agents_async()` — Background thread wrapper for non-blocking triggers
   - `trigger_scoring()` — Rate-limited trigger entry point with 5-second debounce

2. **Priority routes blueprint** — Two API endpoints for manual scoring and ranking queries

3. **Dashboard integration** — Replace hardcoded priority with `agent.priority_score`, update sort/recommend functions

4. **Hook integration** — Add scoring trigger call in HookLifecycleBridge after state transitions

### Fallback Chain

```
Objective set? → Use objective text + constraints as primary context
  ↓ No
Waypoint exists? → Use Next Up + Upcoming sections as context
  ↓ No
Default → Score = 50, reason = "No scoring context available"
```

### Rate Limiting

- 5-second debounce timer for state-change-triggered scoring
- Thread-safe (threading.Timer with lock)
- Objective changes bypass debounce for immediate re-scoring

## Definition of Done

- [ ] Agent model has priority_score (int, nullable), priority_reason (text, nullable), priority_updated_at (datetime, nullable)
- [ ] Migration adds priority fields and passes upgrade/downgrade
- [ ] PriorityScoringService scores all active agents in a single batch inference call
- [ ] Scoring prompt includes objective/waypoint context and agent metadata
- [ ] LLM response parsed as structured JSON with error handling
- [ ] Fallback chain: objective → waypoint → default(50)
- [ ] Rate-limited triggers on state changes (5-second debounce)
- [ ] Immediate re-score on objective changes
- [ ] POST /api/priority/score triggers batch scoring
- [ ] GET /api/priority/rankings returns current rankings
- [ ] Dashboard shows real priority scores on agent cards
- [ ] Recommended next panel uses highest priority score
- [ ] sort_agents_by_priority() sorts by priority_score
- [ ] SSE broadcasts priority_update events
- [ ] All tests pass (unit + integration + existing suite)
