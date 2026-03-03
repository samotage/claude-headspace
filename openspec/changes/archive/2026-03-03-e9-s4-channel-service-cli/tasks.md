# Tasks: e9-s4-channel-service-cli

## 1. Planning (Phase 1)

- [x] 1.1 Create OpenSpec proposal files
- [x] 1.2 Validate proposal with openspec validate
- [x] 1.3 Review and get approval

## 2. Implementation (Phase 2)

### 2.1 Caller Identity Module
- [x] 2.1.1 Create `src/claude_headspace/services/caller_identity.py` with `CallerResolutionError` exception and `resolve_caller()` function
- [x] 2.1.2 Implement env var override strategy (`HEADSPACE_AGENT_ID`)
- [x] 2.1.3 Implement tmux pane detection fallback strategy
- [x] 2.1.4 Write unit tests for caller identity resolution (both strategies, fallback, error case)

### 2.2 ChannelService Error Hierarchy
- [x] 2.2.1 Define `ChannelError` base exception and 7 subclasses in `channel_service.py`
- [x] 2.2.2 Ensure all exceptions carry human-readable messages with actionable guidance

### 2.3 ChannelService — Channel CRUD
- [x] 2.3.1 Implement `__init__(self, app)` following HandoffExecutor pattern
- [x] 2.3.2 Implement `create_channel()` — capability check, Channel + ChannelMembership creation, optional member addition
- [x] 2.3.3 Implement `list_channels()` — member-scoped and all-visible modes
- [x] 2.3.4 Implement `get_channel()` — slug lookup with ChannelNotFoundError
- [x] 2.3.5 Implement `update_channel()` — chair/operator validation, field update
- [x] 2.3.6 Implement `complete_channel()` — chair validation, status transition, system message
- [x] 2.3.7 Implement `archive_channel()` — chair/operator validation, complete-state check, status transition

### 2.4 ChannelService — Membership Management
- [x] 2.4.1 Implement `list_members()` — return all memberships with persona details
- [x] 2.4.2 Implement `add_member()` — validation cascade, one-agent-one-channel check, spin-up, context briefing
- [x] 2.4.3 Implement `leave_channel()` — status transition, auto-complete check with advisory lock
- [x] 2.4.4 Implement `transfer_chair()` — chair validation, is_chair swap, system message
- [x] 2.4.5 Implement `mute_channel()` and `unmute_channel()` — status transitions, system messages

### 2.5 ChannelService — Messages
- [x] 2.5.1 Implement `send_message()` — validation, Message creation, pending-to-active transition, SSE broadcast
- [x] 2.5.2 Implement `get_history()` — member validation (active/left/muted), cursor pagination, chronological ordering
- [x] 2.5.3 Implement `_post_system_message()` — internal helper for system message creation
- [x] 2.5.4 Implement `_generate_context_briefing()` — last N messages formatted as text block

### 2.6 ChannelService — Internal Helpers
- [x] 2.6.1 Implement `_check_membership()` — membership validation with optional active-only flag
- [x] 2.6.2 Implement `_check_chair()` — chair status validation
- [x] 2.6.3 Implement `_check_agent_channel_conflict()` — one-agent-one-channel proactive check
- [x] 2.6.4 Implement `_transition_to_active()` — pending-to-active state change
- [x] 2.6.5 Implement `_auto_complete_if_empty()` — last-member-leave check with advisory lock
- [x] 2.6.6 Implement `_spin_up_agent_for_persona()` — async agent creation using create_agent

### 2.7 ChannelService — SSE Broadcasting
- [x] 2.7.1 Implement `_broadcast_message()` — broadcast channel_message SSE event after message persistence
- [x] 2.7.2 Implement `_broadcast_update()` — broadcast channel_update SSE event after state changes

### 2.8 Channel CLI
- [x] 2.8.1 Create `src/claude_headspace/cli/channel_cli.py` with AppGroup("channel")
- [x] 2.8.2 Implement `create` subcommand with --type, --description, --intent, --org, --project, --members options
- [x] 2.8.3 Implement `list` subcommand with --all, --status, --type options
- [x] 2.8.4 Implement `show` subcommand
- [x] 2.8.5 Implement `members` subcommand
- [x] 2.8.6 Implement `add` subcommand with --persona option
- [x] 2.8.7 Implement `leave` subcommand
- [x] 2.8.8 Implement `complete` subcommand
- [x] 2.8.9 Implement `transfer-chair` subcommand with --to option
- [x] 2.8.10 Implement `mute` and `unmute` subcommands
- [x] 2.8.11 Add ChannelError and CallerResolutionError exception handling to all commands

### 2.9 Msg CLI
- [x] 2.9.1 Create `src/claude_headspace/cli/msg_cli.py` with AppGroup("msg")
- [x] 2.9.2 Implement `send` subcommand with --type and --attachment options
- [x] 2.9.3 Implement `history` subcommand with --format, --limit, --since options
- [x] 2.9.4 Implement conversational envelope formatter
- [x] 2.9.5 Implement YAML output formatter

### 2.10 App Factory Registration
- [x] 2.10.1 Register ChannelService in `create_app()` as `app.extensions["channel_service"]`
- [x] 2.10.2 Register channel_cli and msg_cli in `register_cli_commands()`

### 2.11 Agent-to-Membership Linking (FR14/FR14a)
- [x] 2.11.1 Add ChannelMembership agent_id update logic to `process_session_start()` in hook_receiver.py
- [x] 2.11.2 Add context briefing delivery after membership linking
- [x] 2.11.3 Write unit tests for membership linking and briefing delivery

## 3. Testing (Phase 3)

### 3.1 Service Tests
- [x] 3.1.1 Test channel creation with capability check (SC-1)
- [x] 3.1.2 Test channel creation with member_slugs (SC-6)
- [x] 3.1.3 Test channel listing — member-scoped and all-visible (SC-2, SC-3)
- [x] 3.1.4 Test channel show/get (SC-4)
- [x] 3.1.5 Test channel update — chair and non-chair (FR4a)
- [x] 3.1.6 Test channel completion — chair and non-chair (SC-9, SC-18)
- [x] 3.1.7 Test archive channel — complete state requirement (FR15)
- [x] 3.1.8 Test add member — success, already member, channel closed, no capability (SC-5, SC-16)
- [x] 3.1.9 Test add member — agent spin-up when no running agent (SC-6)
- [x] 3.1.10 Test one-agent-one-channel conflict (SC-16)
- [x] 3.1.11 Test leave channel — normal and last-member auto-complete (SC-7, SC-8)
- [x] 3.1.12 Test chair transfer — success and non-chair (SC-10, SC-18)
- [x] 3.1.13 Test mute/unmute (SC-11)
- [x] 3.1.14 Test send message — success, first-message activation, closed channel (SC-12, SC-13, SC-19)
- [x] 3.1.15 Test message history — active, left, non-member, pagination (SC-14, SC-15, SC-19)
- [x] 3.1.16 Test system message generation (SC-17)
- [x] 3.1.17 Test no-creation-capability error (SC-17)
- [x] 3.1.18 Test context briefing generation
- [x] 3.1.19 Test SSE broadcasting calls

### 3.2 CLI Tests
- [x] 3.2.1 Test `flask channel create` with various options (SC-1)
- [x] 3.2.2 Test `flask channel list` with --all, --status, --type (SC-2, SC-3)
- [x] 3.2.3 Test `flask channel show` (SC-4)
- [x] 3.2.4 Test `flask channel members` (FR5b)
- [x] 3.2.5 Test `flask channel add` — success and error cases (SC-5)
- [x] 3.2.6 Test `flask channel leave` (SC-7)
- [x] 3.2.7 Test `flask channel complete` — chair and non-chair (SC-9)
- [x] 3.2.8 Test `flask channel transfer-chair` (SC-10)
- [x] 3.2.9 Test `flask channel mute` and `unmute` (SC-11)
- [x] 3.2.10 Test `flask msg send` (SC-12)
- [x] 3.2.11 Test `flask msg history` — envelope and yaml formats (SC-14, SC-15)
- [x] 3.2.12 Test caller identity resolution errors in CLI (SC-20)
- [x] 3.2.13 Test ChannelError display in CLI

### 3.3 Integration Tests
- [x] 3.3.1 Test agent-to-membership linking on session start (FR14)
- [x] 3.3.2 Test context briefing delivery on post-registration (FR14a)

## 4. Final Verification

- [x] 4.1 All tests passing
- [x] 4.2 No linter errors
- [x] 4.3 Service isolation verified — no CLI/HTTP dependencies in ChannelService
- [x] 4.4 All 20 functional success criteria verified
