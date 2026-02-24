## 1. Planning (Phase 1)

- [x] 1.1 Create OpenSpec proposal files
- [x] 1.2 Validate proposal with openspec validate
- [x] 1.3 Review and get approval

## 2. Implementation (Phase 2)

### 2.1 CLI Transcript Command

- [ ] 2.1.1 Add `transcript` subcommand to CLI argument parser in `launcher.py`
- [ ] 2.1.2 Implement transcript extraction logic: query Agent -> Commands (ordered by `started_at` ASC) -> Turns (ordered by `timestamp` ASC), filtering out turns with empty/null text
- [ ] 2.1.3 Format output as structured markdown: command instruction as `##` headings, turns prefixed with `**User:**` / `**Agent:**` and timestamps
- [ ] 2.1.4 Handle edge cases: agent not found (exit code 1 with error message), no commands/turns found (informational message to stdout)
- [ ] 2.1.5 Implement as a Flask CLI command (Click) for database access within app context

### 2.2 Revival Service

- [ ] 2.2.1 Create `src/claude_headspace/services/revival_service.py` with `revive_agent(dead_agent_id: int) -> RevivalResult`
- [ ] 2.2.2 Validate preconditions: agent exists, agent has `ended_at` set (is dead), agent has a project
- [ ] 2.2.3 Call `create_agent(project_id, persona_slug, previous_agent_id=dead_agent_id)` to create successor
- [ ] 2.2.4 Store revival metadata on the successor agent so `hook_receiver` can detect it at session_start (use `previous_agent_id` — revival and handoff both use this field; distinguish by checking whether a Handoff record exists)

### 2.3 Revival Instruction Injection

- [ ] 2.3.1 Add revival injection logic in `hook_receiver.process_session_start()` — after skill injection (for persona agents) or immediately (for anonymous agents)
- [ ] 2.3.2 Compose the revival instruction message: tell the new agent to run `claude-headspace transcript <predecessor-agent-id>` and use the output to understand the predecessor's context
- [ ] 2.3.3 Inject via `tmux_bridge.send_text()` following the same pattern as skill_injector
- [ ] 2.3.4 Ensure revival injection only fires for agents created via the revive flow (check for absence of Handoff record on predecessor, since handoff uses the same `previous_agent_id` field)

### 2.4 Revive API Endpoint

- [ ] 2.4.1 Add `POST /api/agents/<int:agent_id>/revive` route to `routes/agents.py`
- [ ] 2.4.2 Validate request: agent exists, agent is dead (`ended_at` is not null)
- [ ] 2.4.3 Call `revival_service.revive_agent()` and return appropriate status codes (201 success, 400 validation failure, 404 not found, 409 already being revived)

### 2.5 Dashboard UI

- [ ] 2.5.1 Add "Revive" button to dead agent cards (visible only when `ended_at` is set)
- [ ] 2.5.2 Add click handler that calls `POST /api/agents/<id>/revive` and shows feedback
- [ ] 2.5.3 Add predecessor link on successor agent cards (informational, showing the `previous_agent_id` chain)

## 3. Testing (Phase 3)

- [ ] 3.1 Unit tests for transcript extraction logic (formatting, edge cases, chronological ordering)
- [ ] 3.2 Unit tests for revival service (precondition validation, successor creation, metadata)
- [ ] 3.3 Route tests for revive endpoint (success, not found, already alive, missing project)
- [ ] 3.4 Unit tests for revival injection in hook_receiver (persona vs anonymous agents, idempotency)
- [ ] 3.5 Integration test: full revival flow (create dead agent, revive, verify successor has correct project/persona/previous_agent_id)

## 4. Final Verification

- [ ] 4.1 All tests passing
- [ ] 4.2 No linter errors
- [ ] 4.3 Manual verification: trigger revival from dashboard, verify new agent receives transcript command
- [ ] 4.4 Visual verification: screenshot of revive button on dead agent card
