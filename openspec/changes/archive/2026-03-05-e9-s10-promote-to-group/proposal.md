## Why

The operator needs to bring additional expertise into an ongoing 1:1 agent conversation without breaking flow. Currently this requires leaving the chat, manually creating a channel, adding members, and briefing the new agent on context. This sprint enables a contextual, in-the-moment "Create Group Channel" action from the agent card kebab menu that orchestrates the entire spawn-and-merge flow automatically.

## What Changes

- **New kebab menu action**: "Create Group Channel" added to the agent card kebab menu for active agents with assigned personas
- **Persona picker dialog**: Modal with searchable list of active personas, filtering out the original agent's persona and the operator's persona
- **Promote-to-group orchestration endpoint**: `POST /api/agents/<agent_id>/promote-to-group` that chains channel creation, membership, agent spin-up, and context seeding
- **Channel `spawned_from_agent_id` column**: New nullable FK on Channel model linking back to the originating agent (Alembic migration)
- **Conversation history retrieval**: Service method to fetch the last 20 turns from an agent's full conversation history across all commands
- **Context seeding via private tmux briefing**: Last 20 turns formatted and delivered privately to the new agent using the existing `_deliver_context_briefing` pattern
- **System origin message**: Posted in the group channel indicating its origin
- **Operator auto-join**: Operator's persona added as member and chair automatically
- **Transactional cleanup**: If agent spin-up fails after channel creation, the channel is cleaned up

## Impact

- Affected specs: channel data model, channel service, agent lifecycle, kebab menu actions, persona picker UI
- Affected code:
  - `src/claude_headspace/models/channel.py` — add `spawned_from_agent_id` column
  - `src/claude_headspace/services/channel_service.py` — promote-to-group orchestration logic, conversation history retrieval
  - `src/claude_headspace/routes/channels_api.py` — new promote-to-group API endpoint
  - `templates/partials/_agent_card.html` — add "Create Group Channel" menu item
  - `static/js/agent-lifecycle.js` — persona picker dialog, promote-to-group trigger
  - `migrations/versions/` — new Alembic migration for `spawned_from_agent_id`
  - `tests/routes/test_channels_api.py` — endpoint tests
  - `tests/services/test_channel_service.py` — orchestration logic tests
- Related git context:
  - Recent channel delivery and service fixes (c50cc3ed, e95afbdc, ffb8d530)
  - Existing `_deliver_context_briefing` / `_generate_context_briefing` pattern in channel_service.py
  - Existing `/api/personas/active` endpoint for persona list
  - Prior OpenSpec: e9-s8-voice-bridge-channels (channel-context-tracking, channel-intent-detection patterns)
