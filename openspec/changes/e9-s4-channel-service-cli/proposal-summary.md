# Proposal Summary: e9-s4-channel-service-cli

## Architecture Decisions
- `ChannelService` is the single point of truth for all channel operations — CLI, API, voice bridge, and dashboard all delegate to it
- Service follows the `__init__(self, app)` pattern (same as HandoffExecutor, HeadspaceMonitor)
- Caller identity resolution is shared infrastructure in its own module (not channel-specific) — used by both CLI groups, reusable by future API
- Error hierarchy uses a `ChannelError` base with 7 typed subclasses carrying actionable human-readable messages
- `CallerResolutionError` is standalone (not a ChannelError subclass) because it's shared CLI infrastructure
- Message send is fire-and-forget: write to DB, broadcast SSE, return immediately. Fan-out delivery is Sprint 6
- Agent spin-up on member add uses existing `create_agent()` from agent_lifecycle (same as RemoteAgentService and HandoffExecutor)
- Advisory locks protect concurrent operations (chair transfer, last-member-leave auto-complete)

## Implementation Approach
- Create 4 new files: channel_service.py, caller_identity.py, channel_cli.py, msg_cli.py
- Modify 2 existing files: app.py (service + CLI registration), hook_receiver.py (agent-to-membership linking)
- ChannelService exposes 14 public methods and 8 internal helpers
- CLI groups are thin wrappers: resolve caller identity, delegate to service, format output, handle errors
- SSE broadcasting via existing broadcaster for `channel_message` and `channel_update` events
- Context briefing delivered via tmux_bridge at two points: immediately during add_member (if agent exists), or deferred to session-start hook (if agent was spun up async)

## Files to Modify

### New Files
- `src/claude_headspace/services/channel_service.py` — ChannelService class with 14 public methods, 8 internal helpers, 7 exception classes
- `src/claude_headspace/services/caller_identity.py` — CallerResolutionError exception, resolve_caller() function (env var + tmux detection)
- `src/claude_headspace/cli/channel_cli.py` — `flask channel` AppGroup with 10 subcommands (create, list, show, members, add, leave, complete, transfer-chair, mute, unmute)
- `src/claude_headspace/cli/msg_cli.py` — `flask msg` AppGroup with 2 subcommands (send, history), conversational envelope + YAML formatters

### Modified Files
- `src/claude_headspace/app.py` — Register ChannelService in create_app(), register channel_cli and msg_cli in register_cli_commands()
- `src/claude_headspace/services/hook_receiver.py` — After persona assignment in process_session_start(), link agent to pending ChannelMembership records and deliver context briefings

### Test Files (New)
- `tests/services/test_channel_service.py` — Service unit tests (~19 test functions)
- `tests/services/test_caller_identity.py` — Caller identity unit tests (~4 test functions)
- `tests/cli/test_channel_cli.py` — Channel CLI tests (~13 test functions)
- `tests/cli/test_msg_cli.py` — Msg CLI tests (~4 test functions)
- `tests/integration/test_channel_membership_linking.py` — FR14/FR14a integration tests (~2 test functions)

## Acceptance Criteria
1. `flask channel create "test" --type workshop` creates a channel with auto-generated slug, pending status, and creator as chair
2. `flask channel list` returns only the caller's active channels; `--all` returns all non-archived
3. `flask channel show <slug>` displays channel details with members and message count
4. `flask channel add <slug> --persona <slug>` adds a member with system message; spins up agent if needed
5. `flask channel leave <slug>` sets status to left; auto-completes if last active member
6. `flask channel complete <slug>` transitions to complete (chair only)
7. `flask channel transfer-chair <slug> --to <slug>` transfers chair role (chair only)
8. `flask channel mute/unmute <slug>` toggles membership status
9. `flask msg send <slug> "content"` creates a Message record (fire-and-forget); first non-system message activates pending channel
10. `flask msg history <slug>` displays conversational envelope format; `--format yaml` for machine output
11. One-agent-one-channel enforcement returns actionable error with leave command
12. Caller identity resolves via HEADSPACE_AGENT_ID env var (priority) or tmux pane detection (fallback)
13. All error messages are actionable and human-readable
14. Agent-to-membership linking works on session-start hook when agent spins up for a channel invitation

## Constraints and Gotchas
- Channel slug is auto-generated after insert (after_insert event) — must flush/commit to get the real slug
- The partial unique index `uq_active_agent_one_channel` prevents agent active in two channels — service check is proactive UX, index is the backstop
- Context briefing delivery requires tmux_bridge — agents not in tmux sessions won't receive briefings
- Agent spin-up is async — membership created with NULL agent_id, linked on session-start hook
- `PersonaType` (S2) must be in place for `can_create_channel` to work correctly
- S1's handoff detection also modifies session_correlator after persona assignment — both modifications append sequentially

## Git Change History

### Related Files
- `openspec/specs/channel-data-model/spec.md` — S3 data model spec (foundation for this change)
- `src/claude_headspace/models/channel.py` — Channel model (S3, already exists)
- `src/claude_headspace/models/channel_membership.py` — ChannelMembership model (S3, already exists)
- `src/claude_headspace/models/message.py` — Message model (S3, already exists)
- `src/claude_headspace/models/persona.py` — Persona model with `can_create_channel` property (S2, already exists)

### OpenSpec History
- `e9-s3-channel-data-model` (archived) — Created the Channel, ChannelMembership, Message tables
- `e9-s2-persona-type-system` (archived) — Added PersonaType and can_create_channel capability

### Implementation Patterns
- Service class: Follow HandoffExecutor pattern (`__init__(self, app)`, registered in extensions)
- CLI: Follow persona_cli.py pattern (AppGroup, Click decorators, error handling)
- Agent spin-up: Follow RemoteAgentService pattern (create_agent from agent_lifecycle)
- SSE: Use broadcaster.broadcast() for channel_message and channel_update events
- Advisory locks: Use existing advisory_lock module for concurrent operation safety

## Q&A History
- No clarifications needed — all design decisions resolved in Workshop Section 2 (Decisions 2.1-2.2)

## Dependencies

### Internal Dependencies (Already Implemented)
- Channel, ChannelMembership, Message models (S3)
- PersonaType and can_create_channel (S2)
- Persona and Agent models (E8)
- Session correlator and hook receiver (E8)
- Tmux bridge (E5-S4)
- Agent lifecycle create_agent (E5)
- SSE broadcaster (E1-S7)
- Advisory lock module

### No External Dependencies
- No new pip packages required
- No new npm packages required

## Testing Strategy

### Unit Tests
- Channel CRUD operations with mocked database
- Membership management (add, leave, mute, unmute, transfer)
- Message send and history with pagination
- Error hierarchy and actionable messages
- Capability checks
- Status transitions (pending->active->complete->archived)
- One-agent-one-channel enforcement
- Context briefing generation

### CLI Tests
- All 12 CLI commands with Click test runner
- Error display to stderr
- Output format verification (envelope and YAML)

### Integration Tests
- Agent-to-membership linking on session start (FR14)
- Context briefing delivery (FR14a)

## OpenSpec References
- proposal.md: openspec/changes/e9-s4-channel-service-cli/proposal.md
- tasks.md: openspec/changes/e9-s4-channel-service-cli/tasks.md
- specs:
  - openspec/changes/e9-s4-channel-service-cli/specs/channel-service/spec.md
  - openspec/changes/e9-s4-channel-service-cli/specs/caller-identity/spec.md
  - openspec/changes/e9-s4-channel-service-cli/specs/channel-cli/spec.md
  - openspec/changes/e9-s4-channel-service-cli/specs/msg-cli/spec.md
  - openspec/changes/e9-s4-channel-service-cli/specs/channel-membership-linking/spec.md
