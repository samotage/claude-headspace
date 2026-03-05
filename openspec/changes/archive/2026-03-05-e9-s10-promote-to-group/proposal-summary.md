# Proposal Summary: e9-s10-promote-to-group

## Architecture Decisions

1. **Spawn-and-merge pattern, not conversion**: The original 1:1 agent chat remains intact. A new group channel is created alongside it. This avoids disrupting the foundational tmux/Claude Code connection.

2. **Always spin up a fresh agent**: Even if the selected persona already has a running agent in the same project, a new instance is created. Existing agents may be mid-task on unrelated work and should not be hijacked.

3. **Private context seeding via tmux**: The last 20 turns are delivered as a private tmux briefing to the new agent, not posted as visible messages in the channel. This avoids cluttering the channel history while giving the new agent full context.

4. **Transactional cleanup on failure**: If agent spin-up fails after channel creation, the channel is cleaned up rather than left orphaned. The original 1:1 chat is never affected by errors.

5. **`spawned_from_agent_id` with SET NULL**: The FK uses ON DELETE SET NULL to avoid coupling the channel's lifecycle to the agent's. If the originating agent is deleted, the channel persists.

## Implementation Approach

The implementation chains together existing building blocks with minimal new code:

- **Data model**: Single new column on the existing Channel model + Alembic migration
- **Backend orchestration**: A new method on ChannelService that sequences existing operations (channel creation, membership management, agent lifecycle, context briefing) with transactional cleanup
- **API endpoint**: Single new POST endpoint on channels_api blueprint
- **Frontend**: Kebab menu item addition in `_agent_card.html` + persona picker modal in `agent-lifecycle.js` following existing IIFE patterns

The orchestration is server-side. The frontend makes a single API call and receives the result. No complex client-side state management.

## Files to Modify

### Data Model & Migration
- `src/claude_headspace/models/channel.py` — add `spawned_from_agent_id` column (nullable FK to Agent, ON DELETE SET NULL) and relationship
- `migrations/versions/` — new Alembic migration script

### Backend Services
- `src/claude_headspace/services/channel_service.py` — add `promote_to_group()` orchestration method, `get_agent_conversation_history()` method for retrieving last N turns

### API Routes
- `src/claude_headspace/routes/channels_api.py` — add `POST /api/agents/<agent_id>/promote-to-group` endpoint

### Frontend Templates
- `templates/partials/_agent_card.html` — add "Create Group Channel" menu item to kebab menu (after Handoff, before divider)

### Frontend JavaScript
- `static/js/agent-lifecycle.js` — persona picker modal dialog, promote-to-group API call, loading/success/error toast handling

### Tests
- `tests/services/test_channel_service.py` — unit tests for orchestration logic, conversation history retrieval, transactional cleanup
- `tests/routes/test_channels_api.py` — route tests for the new endpoint

## Acceptance Criteria

1. Agent card kebab menu shows "Create Group Channel" for active agents with persona
2. Menu item is disabled (with tooltip) when agent has no persona
3. Persona picker dialog opens with searchable list of active personas (excluding original agent's persona and operator persona)
4. Confirming triggers orchestration: channel creation + membership + agent spin-up + context briefing + system message
5. New channel card appears in dashboard via SSE
6. Original 1:1 chat remains fully functional
7. System message in channel indicates origin
8. Error handling cleans up partial state
9. Full flow completes within 30 seconds

## Constraints and Gotchas

- **Agent lifecycle service**: The `create_agent()` function in `agent_lifecycle.py` creates agent records but actual tmux/Claude Code session spin-up is asynchronous. Context briefing delivery may need to handle the case where the new agent's tmux pane is not immediately available.
- **Operator persona**: The system needs to identify the "operator" persona. This may require a convention (e.g., a persona with a specific role or a config setting). Verify how the existing codebase identifies the operator.
- **Channel membership via persona**: The existing `add_member()` and related methods work through persona IDs. The new agent must have its persona_id set before being added as a channel member.
- **Context briefing format**: The existing `_generate_context_briefing` method formats channel messages. For promote-to-group, we need to format agent turns (Turn model) instead. This requires a similar but distinct formatting method.
- **SSE broadcasting**: The existing `channel_update` SSE event should be sufficient for the new channel card to appear. Verify the dashboard's channel card rendering handles the `spawned_from_agent_id` field gracefully.

## Git Change History

### Related Files (from git_context)
- `src/claude_headspace/routes/channels_api.py` — actively modified (e95afbdc, 3324266a, 975d8cf5, 8319dee4)
- `src/claude_headspace/services/channel_service.py` — actively modified (e95afbdc, ffb8d530, 8319dee4, 975d8cf5, 8f1953f0)
- `src/claude_headspace/services/channel_delivery.py` — modified in recent fixes (c50cc3ed, 8319dee4, 8f1953f0)
- `templates/channels.html` — exists for channel page
- `tests/routes/test_channels_api.py` — test file exists and actively maintained
- `tests/services/test_channel_service.py` — test file exists and actively maintained

### OpenSpec History
- `e9-s8-voice-bridge-channels` (archived 2026-03-03): channel-context-tracking, channel-intent-detection, channel-name-matching, voice-formatter-channels, voice-pwa-channels

### Patterns Detected
- Modules + tests + templates structure (no standalone main modules, no static, no bin, no config changes expected)
- Service method pattern: ChannelService methods with db.session management and SSE broadcasting
- Route pattern: Blueprint endpoints with JSON request/response, error handling returning appropriate HTTP status codes

## Q&A History

No clarification questions were raised during the proposal phase. The PRD was clear and internally consistent with all open decisions resolved.

## Dependencies

- **No new Python packages** required
- **No new npm packages** required
- **Alembic migration** required for `spawned_from_agent_id` column
- **Existing services used**: ChannelService, agent_lifecycle.create_agent(), TmuxBridge, Broadcaster
- **Existing API used**: `/api/personas/active` for persona list in the picker dialog

## Testing Strategy

- **Unit tests** (tests/services/test_channel_service.py):
  - Conversation history retrieval: empty, < 20, = 20, > 20 turns
  - Promote-to-group happy path: channel creation, membership, agent spin-up, context seeding
  - Transactional cleanup: agent spin-up failure after channel creation
  - Persona filtering: exclude original agent's persona, operator persona

- **Route tests** (tests/routes/test_channels_api.py):
  - POST promote-to-group: success (201), agent not found (404), no persona (400), persona slug not found (404)
  - Verify response includes channel details

- **Manual verification**:
  - Full promote-to-group flow via dashboard kebab menu
  - Original 1:1 chat unaffected
  - Channel card appears and chat panel opens
  - System origin message visible in channel

## OpenSpec References

- **Proposal**: `openspec/changes/e9-s10-promote-to-group/proposal.md`
- **Tasks**: `openspec/changes/e9-s10-promote-to-group/tasks.md`
- **Spec**: `openspec/changes/e9-s10-promote-to-group/specs/promote-to-group/spec.md`
- **PRD**: `docs/prds/channels/e9-s10-promote-to-group-prd.md`
