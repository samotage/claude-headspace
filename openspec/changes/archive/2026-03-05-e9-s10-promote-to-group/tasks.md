## 1. Planning (Phase 1)

- [x] 1.1 Create OpenSpec proposal files
- [x] 1.2 Validate proposal with openspec validate
- [x] 1.3 Review and get approval

## 2. Data Model & Migration (Phase 2a)

- [x] 2.1 Add `spawned_from_agent_id` column to Channel model (nullable FK to Agent, ON DELETE SET NULL)
- [x] 2.2 Add relationship accessor on Channel model (`spawned_from_agent`)
- [x] 2.3 Generate and apply Alembic migration

## 3. Backend Orchestration (Phase 2b)

- [x] 3.1 Add conversation history retrieval method to ChannelService — fetch last N turns from an agent's full conversation history across all commands
- [x] 3.2 Add promote-to-group orchestration method to ChannelService:
  - Create channel (type=workshop, status=active, spawned_from_agent_id set)
  - Add operator persona as member and chair
  - Add original agent's persona as member
  - Spin up new agent for selected persona (same project as original)
  - Add new agent's persona as member
  - Format last 20 turns as context briefing, deliver privately via tmux
  - Post system origin message in channel
  - Broadcast channel_update SSE event
- [x] 3.3 Add transactional cleanup — if agent spin-up fails after channel creation, remove the channel
- [x] 3.4 Add `POST /api/agents/<agent_id>/promote-to-group` API endpoint accepting `{persona_slug: "..."}`, returning channel details on success

## 4. Frontend — Kebab Menu & Persona Picker (Phase 2c)

- [x] 4.1 Add "Create Group Channel" menu item to agent card kebab menu in `_agent_card.html` (after Handoff, before divider)
- [x] 4.2 Implement visibility logic: only show for active agents with tmux connection
- [x] 4.3 Implement disabled state: greyed out with tooltip when agent has no persona
- [x] 4.4 Create persona picker modal dialog in `agent-lifecycle.js`:
  - Fetch active personas from `/api/personas/active`
  - Filter out original agent's persona and operator persona
  - Searchable list showing persona name, role, active status
  - Confirm button (disabled until selection), Cancel button
- [x] 4.5 Wire confirm action to POST `/api/agents/<agent_id>/promote-to-group`
- [x] 4.6 Add loading indicator (toast: "Creating group channel with [persona]...")
- [x] 4.7 Handle success response (toast: "Group channel created with [names]")
- [x] 4.8 Handle error response (toast with error message)

## 5. Testing (Phase 3)

- [x] 5.1 Unit tests for conversation history retrieval (empty history, < 20 turns, exactly 20, > 20)
- [x] 5.2 Unit tests for promote-to-group orchestration (happy path, transactional cleanup on failure)
- [x] 5.3 Route tests for `POST /api/agents/<agent_id>/promote-to-group` (success, missing persona, agent not found, agent without persona)
- [x] 5.4 Unit tests for persona filtering logic (exclude original agent's persona, exclude operator persona)

## 6. Final Verification (Phase 4)

- [x] 6.1 All tests passing
- [x] 6.2 No linter errors
- [ ] 6.3 Manual verification: full promote-to-group flow via dashboard
- [ ] 6.4 Verify original 1:1 chat unaffected after promotion
- [ ] 6.5 Verify channel card appears and chat panel opens correctly
