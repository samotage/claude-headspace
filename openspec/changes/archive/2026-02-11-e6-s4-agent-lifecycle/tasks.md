## 1. Planning (Phase 1)

- [x] 1.1 Create OpenSpec proposal files
- [x] 1.2 Validate proposal with openspec validate
- [x] 1.3 Review and get approval

## 2. Backend Services (Phase 2a)

- [x] 2.1 Create `context_parser.py` service — parse `[ctx: XX% used, XXXk remaining]` from tmux pane text using `tmux_bridge.capture_pane()`; return structured data `{percent_used: int, remaining_tokens: str, raw: str}` or `None` if not found
- [x] 2.2 Create `agent_lifecycle.py` service — `create_agent(project_id)`: validates project exists, invokes `claude-headspace start` in project directory via `subprocess.Popen` in a new tmux session, waits for session registration (poll `/api/sessions` or watch for hook), returns agent ID
- [x] 2.3 Create `agent_lifecycle.py` — `shutdown_agent(agent_id)`: validates agent is active with tmux pane, sends `/exit` via `tmux_bridge.send_text()`, returns success/error
- [x] 2.4 Create `agent_lifecycle.py` — `get_context_usage(agent_id)`: validates agent has tmux pane, calls `capture_pane()` + `context_parser.parse()`, returns structured context data

## 3. API Routes (Phase 2b)

- [x] 3.1 Create `routes/agents.py` blueprint — `POST /api/agents` (create agent: accepts `project_id`, returns agent ID and status)
- [x] 3.2 Add to agents blueprint — `DELETE /api/agents/<id>` (graceful shutdown: sends `/exit`, returns confirmation)
- [x] 3.3 Add to agents blueprint — `GET /api/agents/<id>/context` (on-demand context query: returns `{percent_used, remaining_tokens}` or unavailable indicator)
- [x] 3.4 Register agents blueprint in `app.py`

## 4. Voice/Text Bridge Extensions (Phase 2c)

- [x] 4.1 Add `POST /api/voice/agents/create` endpoint — accepts `project_name` or `project_id`, invokes `agent_lifecycle.create_agent()`, returns voice-formatted response
- [x] 4.2 Add `POST /api/voice/agents/<id>/shutdown` endpoint — invokes `agent_lifecycle.shutdown_agent()`, returns voice-formatted response
- [x] 4.3 Add `GET /api/voice/agents/<id>/context` endpoint — invokes `agent_lifecycle.get_context_usage()`, returns voice-formatted response
- [x] 4.4 Update `voice-api.js` — add `createAgent()`, `shutdownAgent()`, `getContext()` API functions
- [x] 4.5 Update `voice-app.js` — add create/kill/context command handling in chat interface

## 5. Dashboard UI (Phase 2d)

- [x] 5.1 Add "New Agent" control to dashboard — project selector dropdown + create button, JS to call `POST /api/agents`
- [x] 5.2 Add kill button to agent card partial (`_agent_card.html`) — small button/icon, JS to call `DELETE /api/agents/<id>`, confirm before sending
- [x] 5.3 Add context indicator to agent card partial — "Check context" button, displays `XX% used · XXXk remaining` inline when clicked, JS to call `GET /api/agents/<id>/context`
- [x] 5.4 Handle SSE updates — new agent cards appear via existing card_refresh SSE; removed agents disappear when hooks fire session-end

## 6. Testing (Phase 3)

- [x] 6.1 Unit tests for `context_parser.py` — test regex parsing with various statusline formats, missing data, ANSI codes
- [x] 6.2 Unit tests for `agent_lifecycle.py` — test create (mock subprocess + registration), shutdown (mock tmux send), context (mock capture_pane + parse)
- [x] 6.3 Route tests for `routes/agents.py` — test create/shutdown/context endpoints with mocked services, error cases
- [x] 6.4 Route tests for voice bridge extensions — test create/shutdown/context voice endpoints with mocked services
- [x] 6.5 Update existing voice bridge tests if any fixtures need adjustment

## 7. Final Verification (Phase 4)

- [x] 7.1 All tests passing
- [ ] 7.2 No linter errors
- [ ] 7.3 Manual verification: create agent from dashboard, check context, kill agent
- [ ] 7.4 Manual verification: create/kill/context from voice bridge chat
