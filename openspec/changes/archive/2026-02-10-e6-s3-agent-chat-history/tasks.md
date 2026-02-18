## 1. Planning (Phase 1)

- [x] 1.1 Create OpenSpec proposal files
- [x] 1.2 Validate proposal with openspec validate
- [x] 1.3 Review and get approval

## 2. Implementation (Phase 2)

### Backend: Intermediate Message Capture

- [x] 2.1 Add intermediate PROGRESS turn capture in `hook_lifecycle_bridge.py` `process_post_tool_use()` — read transcript incrementally from last known position, create PROGRESS turn for new agent text blocks
- [x] 2.2 Add transcript position tracking per agent in `hook_receiver.py` — store last-read file position to enable incremental reads across hook calls
- [x] 2.3 Add deduplication logic in `hook_lifecycle_bridge.py` `process_stop()` — when creating the final turn, skip text already captured as PROGRESS turns during the same agent response
- [x] 2.4 Filter empty/whitespace-only text blocks from being captured as PROGRESS turns

### Backend: Agent-Lifetime Transcript Endpoint

- [x] 2.5 Modify transcript endpoint in `voice_bridge.py` to query turns across ALL tasks for an agent (join through Task to get all turns for agent_id), ordered chronologically
- [x] 2.6 Add cursor-based pagination to transcript endpoint — accept `before` (turn ID cursor) and `limit` (default 50) query params, return `has_more` flag
- [x] 2.7 Include `command_id`, `command_instruction`, and `task_state` in each turn response for client-side command boundary rendering
- [x] 2.8 Support ended agents in transcript endpoint — return full history regardless of agent.ended_at status

### Frontend: Chat UI Enhancements (voice-app.js)

- [x] 2.9 Update `_showChatScreen()` to use paginated transcript endpoint (load most recent 50 turns)
- [x] 2.10 Implement scroll-up pagination — detect scroll to top, fetch older page using cursor (oldest turn ID), prepend turns while preserving scroll position
- [x] 2.11 Add loading indicator at top during page fetch and "All history loaded" indicator when `has_more` is false
- [x] 2.12 Implement smart message grouping — group consecutive agent turns within 2 seconds into single bubbles with line breaks; break groups on intent change or user turns
- [x] 2.13 Implement iMessage-style timestamps — show on first message and after 5+ minute gaps; format: time-only today, "Yesterday HH:MM", day-of-week this week, date for older
- [x] 2.14 Add command boundary separators — detect command_id changes between consecutive turns, render centered separator with command instruction text
- [x] 2.15 Add ended agent support — detect ended agent state, hide input bar, show "Agent ended" banner, disable typing indicator

### Frontend: Chat Links (voice-api.js, project_show.js, activity.js)

- [x] 2.16 Add `getTranscript(agentId, options)` method to voice-api.js supporting pagination params (`before`, `limit`)
- [x] 2.17 Add chat links to project show page agent list — render chat icon/link for each agent row (active and ended)
- [x] 2.18 Add chat links to activity page agent references — render chat link where individual agents are displayed

### Frontend: Styles (voice.css)

- [x] 2.19 Add CSS for command boundary separators (centered text with horizontal rules, subtle/unobtrusive)
- [x] 2.20 Add CSS for scroll-up loading indicator
- [x] 2.21 Add CSS for ended agent banner and disabled input bar state
- [x] 2.22 Add CSS for smart-grouped bubble variant (multiple texts with line break separators)

## 3. Testing (Phase 3)

- [x] 3.1 Test intermediate PROGRESS turn capture — verify post-tool-use creates PROGRESS turns with correct text
- [x] 3.2 Test deduplication — verify stop hook doesn't duplicate text already captured as PROGRESS turns
- [x] 3.3 Test transcript endpoint pagination — verify cursor-based pagination returns correct pages, has_more flag, boundary conditions
- [x] 3.4 Test agent-lifetime query — verify turns from multiple tasks returned chronologically with task metadata
- [x] 3.5 Test ended agent transcript — verify endpoint returns full history for ended agents
- [x] 3.6 Test empty/whitespace filtering — verify empty text blocks are not captured as PROGRESS turns
- [x] 3.7 Test transcript position tracking — verify incremental reads don't re-read already captured content

## 4. Final Verification

- [x] 4.1 All tests passing
- [ ] 4.2 No linter errors
- [ ] 4.3 Manual verification complete
